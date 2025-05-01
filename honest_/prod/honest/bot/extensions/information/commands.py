from asyncio import create_subprocess_shell
from contextlib import suppress
from datetime import datetime
from io import BytesIO
from typing import List, Optional, Union
from time import monotonic

from git import Repo
from discord.http import Route

from aiohttp import ClientSession
from color_processing.models import SearchResult  # type: ignore
from data.config import CONFIG
from discord import (AuditLogEntry, ButtonStyle, Client, Color, Embed, File,
                     Guild, Invite, Member, Message, Object, Permissions, Role,
                     TextChannel, Thread, User, __version__, app_commands,
                     utils)
from discord.abc import GuildChannel
from discord.ext.commands import (Author, Cog, ColorInfo, Command,
                                  CommandConverter, CommandError, Converter,
                                  Group, command, group, has_permissions,
                                  hybrid_command, hybrid_group)
from discord.ui import Button, View
from discord.utils import chunk_list
from discord.utils import escape_markdown as escape_md
from discord.utils import format_dt, oauth_url, utcnow
from humanize import precisedelta
from jishaku.math import natural_size
from psutil import AccessDenied, virtual_memory
from pytz import timezone
from system.classes.builtins import human_timedelta, plural
from system.classes.converters.color import COLOR
from system.classes.database import Record
from system.classes.exceptions import ConcurrencyLimit, NSFWDetection
from system.managers import DiscordStatus
from system.managers.flags.screenshot import ScreenshotFlags
from system.patch.context import Context
from system.patch.help import Help
from system.services.bot.browser import screenshot

from .utils import Timezone, get_timezone
from .views import Banners, UserBanner

try:
    from importlib.metadata import distribution, packages_distributions
except ImportError:
    from importlib_metadata import distribution, packages_distributions

import httpx
import psutil

distributions: List[str] = [
    dist
    for dist in packages_distributions()["discord"]  # type: ignore
    if any(
        file.parts == ("discord", "__init__.py")  # type: ignore
        for file in distribution(dist).files  # type: ignore
    )
]

LIBRARY = distributions[0]


class AuditLogParser:
    def __init__(self, bot: Client, logs: List[AuditLogEntry]):
        self.bot = bot
        self.logs = logs

    def do_parse(self):
        embeds = []
        embed = Embed(
            title="Audit Logs", color=self.bot.color, url=f"https://{CONFIG['domain']}"
        )

        i = 0
        previous_author_id = (
            None  # Track the previous author ID to check for duplicates
        )

        for log in self.logs:
            if not log.user:
                continue
            if log.target is not None:
                if "Object" in str(log.target):
                    t = f"Unknown (`{str(log.target.id)}`)"
                else:
                    t = f"{str(log.target)} (`{log.target.id}`)"
                if "<" in t:
                    target = ""
                else:
                    target = f"**Target:** {t}\n"
            else:
                target = ""

            # Set field name to zero-width space if the author matches the previous one
            field_name = (
                "\u200b"
                if log.user.id == previous_author_id
                else f"{log.user} ({log.user.id})"
            )

            embed.add_field(
                name=field_name,
                value=(
                    f">>> **Action:** `{str(log.action).split('.')[1].replace('_', ' ')}`\n"
                    f"**Reason:** `{log.reason or 'No reason provided'}`\n"
                    f"{target}**Created:** <t:{round(log.created_at.timestamp())}:R>"
                ),
                inline=False,
            )

            # Update the previous author ID for the next iteration
            previous_author_id = log.user.id

            i += 1
            if i == 5:
                embeds.append(embed)
                embed = Embed(
                    title="Audit Logs",
                    color=self.bot.color,
                    url=f"https://{CONFIG['domain']}",
                )
                previous_author_id = None
                i = 0

        # Append the last embed if it has fields and is not already in embeds
        if len(embed.fields) > 0 and embed not in embeds:
            embeds.append(embed)

        return embeds


class CommandorGroup(Converter):
    async def convert(self, ctx: Context, argument: str):
        try:
            command = await CommandConverter().convert(ctx, argument)
            if not command:
                raise CommandError(f"No command found named **{argument[:25]}**")
        except Exception:
            raise CommandError(f"No command found named **{argument[:25]}**")
        return command


class Information(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @hybrid_command(
        name="dstatus", description="get information on discord's current status"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def dstatus(self, ctx: Context):
        data = await DiscordStatus.from_response()
        embed = data.to_embed(self.bot, False)
        return await ctx.send(embed=embed)

    @hybrid_command(
        name="screenshot",
        description="screenshot a webpage",
        example=",screenshot https://google.com -wait 3",
        aliases=["ss"],
    )
    async def screenshot(self, ctx: Context, url: str, *, flags: ScreenshotFlags):
        kwargs = {}
        safe = True if not ctx.channel.is_nsfw() else False
        message = await ctx.normal("Please wait while we fulfill this request...")
        if flags.wait:
            kwargs["wait"] = flags.wait

        if flags.wait_for:
            kwargs["wait_until"] = flags.wait_for

        if flags.full_page:
            kwargs["full_page"] = flags.full_page
        async with ClientSession() as session:
            async with session.request(
                "HEAD", f"https://{url.replace('https://', '').replace('http://', '')}"
            ) as response:
                if int(
                    response.headers.get("Content-Length", 5)
                ) > 52428800 or url.endswith(".txt"):
                    raise CommandError("Content Length Too Large")
        try:
            ss = await screenshot(url, safe, **kwargs)
            embed = Embed(
                title=f"{url.split('://')[1] if '://' in url else url}",
                url=f"https://{url.split('://')[1] if '://' in url else url}",
            ).set_image(url="attachment://screenshot.png")
            return await message.edit(attachments=[ss], embed=embed)
        except NSFWDetection as e:
            embed = await ctx.fail(str(e), return_embed=True)
            return await message.edit(embed=embed)
        except ConcurrencyLimit as e:
            embed = await ctx.fail(str(e), return_embed=True)
            return await message.edit(embed=embed)

    async def patch_help(self, ctx: Context):
        cogs = tuple(
            cog
            for cog in ctx.bot.cogs.values()
            if cog.get_commands() and cog.qualified_name not in ["jishaku", "developer"]
        )

        embeds = []
        new_line = "\n"  # noqa: F841

        # Iterate over each cog to create an embed
        for i, cog in enumerate(cogs, start=1):

            def format_command(command):
                if isinstance(command, Group):
                    return f"{command.qualified_name}{utils.escape_markdown('*')}"
                else:
                    return f"{command.qualified_name}"

            # Create the description for the current cog
            description = ", ".join(format_command(c) for c in cog.walk_commands())

            # Create the embed for the current cog
            embed = (
                Embed(
                    title=cog.qualified_name.replace("_", " ")
                    .replace("Events", "")
                    .replace("Commands", "")
                    .title(),
                    color=ctx.bot.color,
                    url="https://honest.rocks/commands",
                    description=description,
                )
                .set_author(
                    name=ctx.author.name,
                    icon_url=ctx.author.display_avatar.url,
                )
                .set_thumbnail(url=ctx.bot.user.display_avatar.url)
                .set_footer(
                    text=f"Page {i}/{len(cogs)} | {len(tuple(cog.walk_commands()))} commands"
                )
            )

            # Append the embed to the embeds list
            embeds.append(embed)

        return await ctx.paginate(embeds)

    @hybrid_command(
        name="help",
        aliases=["cmds", "commands", "h"],
        description="get information regarding a group or command",
        example=",help antinuke",
    )
    async def help_(
        self, ctx: Context, *, command_or_group: Optional[CommandorGroup] = None
    ):
        try:
            h = Help()
            h.context = ctx
            if (
                "--simple" in ctx.message.content.lower()
                or "-simple" in ctx.message.content.lower()
            ):
                return await self.patch_help(ctx)
            if not command_or_group:
                return await h.send_bot_help()

            elif isinstance(command_or_group, Group):
                return await h.send_group_help(command_or_group)
            else:
                return await h.send_command_help(command_or_group)
        except Exception as exception:
            return await self.bot.errors.handle_exceptions(ctx, exception)

    @group(
        name="color",
        aliases=["dominant", "pfpcolor", "avcolor"],
        description="get information about a color, image color, or avatar color",
        example=",color @alwayshurting",
        invoke_without_command=True,
    )
    async def color(
        self, ctx: Context, *, query: Optional[Union[str, Color, Member, User]] = None
    ):
        if query is None:
            if len(ctx.message.attachments) > 0:
                query = ctx.message.attachments[0].url
            else:
                raise CommandError("you must provide a query or attachment")
        return await ColorInfo().convert(ctx, query)

    @color.command(
        name="search", description="search for a color by name", example=",color purple"
    )
    async def color_search(self, ctx: Context, *, query: str):
        results = await COLOR.search(query)
        if not results:
            raise CommandError(f"No results found for query `{query[:20]}`")

        async def to_embed(result: SearchResult):
            color = await COLOR.detail(result)
            return color.dict_embed

        embeds = []
        for num, result in enumerate(results.results, start=1):
            if num == 1:
                e = await to_embed(result)
            else:
                e = await to_embed(result)
                e = {"attachments": e["files"], "embed": e["embed"]}
            embeds.append(e)
        for i, embed in enumerate(embeds, start=1):
            embed["embed"].set_footer(text=f"Page {i}/{len(embeds)} of Color Search")
        return await ctx.paginate(embeds)

    @command(name="donate", description="support honest thru various payment methods")
    async def donate(self, ctx: Context) -> Message:
        await ctx.send(
            embed=Embed(
                color=self.bot.color,
                title="donate to honest development",
                description=f">>> LTC: `LeoHCALmywyuXe7NHQpDMsWSueva1tLmsF`\nSOL: `AGX8nsfJJkcP77ePEdGmXy4gdsDHbCuxm4PMDiv19LmE`\nCashApp: [`$nxyyfr`](<https://cash.app/$nxyyfr>)\nOr boost our [**`support server 2x`**]({CONFIG['support_url']})",
            )
        )

    @command(name="perks", description="get information on honest's perks")
    async def perks(self, ctx: Context) -> Message:
        await ctx.send(
            embed=Embed(
                color=self.bot.color,
                title="honest perks",
                description=f">>> makemp3\nreskin\nvideotogif\nmore coming soon, give ideas in our [support server]({CONFIG['support_url']})",
            )
        )

    @hybrid_command(
        name="ping",
        aliases=["latency"],
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ping(self, ctx: Context) -> Message:
        ws = self.bot.latency

        start = monotonic()
        #await ctx.channel.typing() 
        await ctx.bot.http.request(Route("GET", "/users/@me")) 
        rest = monotonic() - start

        return await ctx.send(f"iykyk ws:{ws*1000:.2f}ms (rest:{rest*1000:.2f}ms)")

    @hybrid_command(
        name="support",
        aliases=["discord"],
        description="Get an invite link for the bot's support server.",
    )
    async def support(self, ctx: Context) -> Message:
        return await ctx.reply(CONFIG["support_url"])

    @hybrid_command(
        name="credits",
        aliases=["creds", "devs", "developers" "dev"],
        description="Get credits on the bot's contributor's team",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def credits_(self, ctx: Context):
        embed = (
            Embed()
            .set_footer(
                text=f"{self.bot.user.name} credits â€¢ {self.bot.user.name}.rocks"
            )
            .set_thumbnail(url=self.bot.user.avatar)
        )
        embed.add_field(
            name="Credits",
            value=f"`1` **{await self.bot.fetch_user(1294487023272595511)}** - founder & developer (`1294487023272595511`)\n`2` **{await self.bot.fetch_user(1137846765576540171)}** - developer (`1137846765576540171`)\n`2` **{await self.bot.fetch_user(1341140745796452473)}** - developer (`1341140745796452473`)",
        )
        view = View().add_item(
            Button(style=ButtonStyle.grey, label="owners", disabled=True)
        )
        await ctx.reply(embed=embed, view=view)

    @hybrid_command(
        name="botinfo",
        aliases=["bi", "bot", "info", "about"],
        description="get information on the bot",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def botinfo(self, ctx: Context):
        repo = Repo(".git")
        commit = repo.head.commit
        commit_hash = commit.hexsha[:7]
        embed = Embed(
            color=self.bot.color,
            title="invite",
            url=f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot",
        )
        usage = psutil.disk_usage("/")
        #
        percent_used = usage.percent
        free_space = int(usage.free / (1024**3))  # Convert bytes to GB
        total_space = usage.total / (1024**3)  # Convert bytes to GB

        embed.add_field(
            name="bot:",
            value=f""">>> ping: {round(self.bot.latency * 1000, 2)} \ncpu: {
				self.bot.process.cpu_percent()}% \ndisk: `{percent_used}%({free_space}GB free)`""",
        )
        embed.add_field(
            name="stats:",
            value=f""">>> users: {await self.bot.user_count():,} \nguilds: {len(self.bot.guilds):,}""",
            inline=False,
        )
        embed.set_footer(
        text=f"commit hash: {commit_hash}"
      )
        embed.description = f"{self.bot.config['emojis']['uptime']} started: {utils.format_dt(self.bot.startup_time, style='R')}"
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar)
        embed.set_thumbnail(url=self.bot.user.avatar)
        await ctx.send(embed=embed)

    @command(
        name="audit",
        aliases=["auditlogs"],
        description="view the most recent audit logs for the guild",
    )
    @has_permissions(view_audit_log=True)
    async def audit(self, ctx: Context):
        def format_action(action: str):
            if action == "kick":
                return "kicked"

            arr = action.split("_")
            if arr[-1].endswith("e"):
                return f"{arr[-1]}d {' '.join(arr[:-1])}"
            elif arr[-1].endswith("n"):
                if len(arr) == 1:
                    return f"{arr[0]}ned"
                else:
                    return f"{arr[-1]}ned {' '.join(arr[:-1])}"
            else:
                return f"{arr[-1]} {' '.join(arr[:-1])}"

        def format_object(target):
            if isinstance(target, (Member, User)):
                return f"[@{target.name}]({target.url})"

            elif isinstance(target, GuildChannel):
                return f"[#{target.name}]({target.jump_url})"

            elif isinstance(target, Role):
                return f"@{target.name}"

            elif isinstance(target, Invite):
                return f"[{target.code}]({target.url})"

            elif isinstance(target, Object):
                if target.type == Role:
                    return f"{f'@{ctx.guild.get_role(target.id).name}' if ctx.guild.get_role(target.id) else f'**{target.id}**'}"
                else:
                    return f"**{target.id}**"

        parser = AuditLogParser(
            self.bot, [entry async for entry in ctx.guild.audit_logs()]
        )
        embeds = parser.do_parse()
        log_count = len(parser.logs)

        def style(embed: Embed, footer: str):
            embed.set_footer(text=footer)
            embed.set_author(
                name=str(ctx.author), icon_url=ctx.author.display_avatar.url
            )
            return embed

        embeds = [
            style(
                e,
                f"Page {i}/{len(embeds)} ({log_count} {'entry' if log_count < 1 else 'entries'})",
            )
            for i, e in enumerate(embeds, start=1)
        ]
        return await ctx.alternative_paginate(embeds)

    @command(name="bans", description="view the list of the bans for the guild")
    @has_permissions(ban_members=True)
    async def bans(self, ctx: Context):
        bans = [
            f"{entry.user} ({entry.user.id}) - {entry.reason or 'No reason provided'}"
            async for entry in ctx.guild.bans()
        ]

        if not bans:
            raise CommandError("No bans found in this server")

        return await ctx.paginate(
            Embed(title=f"Bans in {ctx.guild} ({len(bans)})"), bans, True
        )

    @hybrid_group(name="boosters", description="view the list of boosters")
    async def boosters(self, ctx: Context):
        if not (
            boosters := sorted(
                filter(
                    lambda member: member.premium_since,
                    ctx.guild.members,
                ),
                key=lambda member: member.premium_since,
                reverse=True,
            )
        ):
            raise CommandError("No boosters found in this server")
        if not (
            rows := [
                f"{member.mention} {format_dt(member.premium_since, style='R')}"
                for member in boosters
            ]
        ):
            raise CommandError("There are no boosters in this server")

        return await ctx.paginate(Embed(title="Boosters"), rows, True)

    @boosters.command(name="lost", description="view a list of lost boosters")
    async def boosters_lost(self, ctx: Context):
        if not (
            boosters_lost := await self.bot.db.fetch(
                """
			SELECT *
			FROM boosters_lost
			ORDER BY expired_at DESC
			"""
            )
        ):
            raise CommandError("No **boosters** have been lost recently!")

        def get_user(user_id: int):
            if user := self.bot.get_user(user_id):
                return f"{str(user)}"
            else:
                return f"Unknown (`{user_id}`)"

        return await ctx.paginate(
            Embed(
                title="Recently lost boosters",
            ),
            [
                (
                    f"**{user}** stopped "
                    + format_dt(
                        row["expired_at"],
                        style="R",
                    )
                    + " (lasted "
                    + human_timedelta(
                        row["started_at"], accuracy=1, brief=True, suffix=False
                    )
                    + ")"
                )
                for row in boosters_lost
                if (user := get_user(row["user_id"]))
            ],
            True,
        )

    @command(name="bots", description="view the list of bots in the server")
    async def bots(self, ctx: Context):
        if not (
            bots := sorted(
                filter(
                    lambda member: member.bot,
                    ctx.guild.members,
                ),
                key=lambda x: x.joined_at,
                reverse=True,
            )
        ):
            raise CommandError(f"No bots have been found in {ctx.guild.name}!")

        return await ctx.paginate(
            Embed(title=f"Bots in {ctx.guild.name.shorten(25)}"),
            [f"{bot.mention}" for bot in bots],
            True,
        )

    @command(name="members", description="view the list of members")
    async def members(self, ctx: Context):
        members = sorted(
            filter(lambda member: not member.bot, ctx.guild.members),
            key=lambda x: x.joined_at,
            reverse=True,
        )
        return await ctx.paginate(
            Embed(title=f"Members in {ctx.guild.name.shorten(25)}"),
            [
                f"{member.mention} - {format_dt(member.joined_at, style='R')}"
                for member in members
            ],
            True,
        )

    @command(name="roles", description="get a list of the roles in the guild")
    async def roles(self, ctx: Context):
        if not (roles := reversed(ctx.guild.roles[1:])):
            raise CommandError(f"No roles have been found in {ctx.guild.name}!")
        return await ctx.paginate(
            Embed(title=f"Roles in {ctx.guild.name.shorten(25)}"),
            [f"{role.mention}" for role in roles],
        )

    @command(
        name="emojis",
        aliases=["emotes"],
        description="view the emojis in the current guild",
    )
    async def emojis(self, ctx: Context):
        if not ctx.guild.emojis:
            raise CommandError(f"No emojis have been found in {ctx.guild.name}!")

        return await ctx.paginate(
            Embed(title=f"Emojis in {ctx.guild.name}"),
            [f"{emoji} [`{emoji.name}`]({emoji.url})" for emoji in ctx.guild.emojis],
            True,
        )

    @command(name="stickers", description="view a list of the stickers in this server")
    async def stickers(self, ctx: Context):
        if not ctx.guild.stickers:
            return await ctx.alert(f"No stickers have been found in {ctx.guild.name}!")

        return await ctx.paginate(
            Embed(title=f"Stickers in {ctx.guild.name}"),
            [f"[`{sticker.name}`]({sticker.url})" for sticker in ctx.guild.stickers],
            True,
        )

    @command(name="invites", description="view a list of the server invites")
    async def invites(self, ctx: Context):
        if not (
            invites := sorted(
                [invite for invite in await ctx.guild.invites() if invite.expires_at],
                key=lambda invite: invite.expires_at,
                reverse=True,
            )
        ):
            raise CommandError(f"No invites have been found in {ctx.guild.name}!")

        return await ctx.paginate(
            Embed(title=f"Invite in {ctx.guild.name}"),
            [
                (
                    f"[`{invite.code}`]({invite.url}) expires "
                    + format_dt(
                        invite.expires_at,
                        style="R",
                    )
                )
                for invite in invites
            ],
            True,
        )

    @command(
        name="avatar",
        description="View a user's avatar",
        example=",avatar @alwayshurting",
        aliases=["av"],
    )
    async def avatar(self, ctx: Context, *, user: Optional[Union[Member, User]] = None):
        user = user or ctx.author
        view = View()

        view.add_item(
            Button(
                style=ButtonStyle.link,
                label="PNG",
                url=str(user.display_avatar.replace(size=4096, format="png")),
            )
        )
        view.add_item(
            Button(
                style=ButtonStyle.link,
                label="JPG",
                url=str(user.display_avatar.replace(size=4096, format="jpg")),
            )
        )
        view.add_item(
            Button(
                style=ButtonStyle.link,
                label="WEBP",
                url=str(user.display_avatar.replace(size=4096, format="webp")),
            )
        )

        return await ctx.send(
            embed=Embed(
                title=f"{user.name}'s avatar",
                description=f"[Click here to download]({user.display_avatar})",
                url=user.display_avatar,
            )
            #   .set_author(name=f"{user.name}'s avatar")
            .set_image(url=user.display_avatar.url),
            #   view=view
        )

    @command(
        name="banner", description="View a user's banner", example=",banner @aiohttp"
    )
    async def banner(self, ctx: Context, *, user: Optional[Union[Member, User]] = None):
        user = user or ctx.author
        user = await self.bot.fetch_user(user.id)

        if not user.banner:
            raise CommandError(
                "You don't have a banner set!"
                if user == ctx.author
                else f"{user} does not have a banner set!"
            )

        embed = Embed(title=f">>> {user.name}'s banner").set_image(url=user.banner)

        view = Banners(embed=embed, author=ctx.author.id, member=user)

        if isinstance(user, Member):
            if user.display_banner:
                view.add_item(UserBanner())

        return await ctx.send(embed=embed, view=view)

    @hybrid_command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def getbotinvite(self: "Information", ctx: Context, *, user: User):
        """
        Get an invite of a bot
        """

        if not user.bot:
            return await ctx.alert("This is not a bot")

        invite_url = oauth_url(user.id, permissions=Permissions(8))
        return await ctx.reply(f"Invite [{user}]({invite_url})")

    @hybrid_command(name="invite", aliases=["inv"])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def invite(self: "Information", ctx: Context):
        """
        Get the invite for honest
        """
        invite_url = oauth_url(
            self.bot.user.id,
            permissions=Permissions(permissions=8),
        )
        return await ctx.reply(invite_url)

    @hybrid_command(
        name="uptime", aliases=["ut", "up"], description="View the bot's uptime"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def uptime(self: "Information", ctx: Context) -> Message:
        return await ctx.reply(
            embed=Embed(
                description=f"**{self.bot.user.display_name}** has been up for: {precisedelta(datetime.now() - self.bot.startup_time, format='%0.0f')}"
            )
	)

    @hybrid_command(
        name="membercount",
        aliases=["mc"],
        description="Get the amount of members in this server",
    )
    async def membercount(self, ctx: Context):
        users = [m for m in ctx.guild.members if not m.bot]
        bots = [m for m in ctx.guild.members if m.bot]

        def percentage(a):
            return round(a / ctx.guild.member_count * 100, 2)

        embed = Embed(
            description="\n".join(
                (
                    f"**members:** `{ctx.guild.member_count:,}`",
                    f"**users:**: `{len(users):,}` ({percentage(len(users))}%)",
                    f"**bots:** `{len(bots):,}` ({percentage(len(bots))}%)",
                )
            )
        )

        new_joined = sorted(
            filter(
                lambda m: (utcnow() - m.joined_at).total_seconds() < 600,
                ctx.guild.members,
            ),
            key=lambda m: m.joined_at,
            reverse=True,
        )

        if new_joined:
            embed.add_field(
                name=f"New members ({len(new_joined)})",
                value=(
                    ", ".join(map(str, new_joined[:5])) + f" + {len(new_joined)-5} more"
                    if len(new_joined) > 5
                    else ""
                ),
                inline=False,
            )

        return await ctx.reply(embed=embed)

    @command(
        name="image", description="Search Google for an image", example=",image purple"
    )
    async def image(self, ctx: Context, *, query: str):
        safe = "moderate" if not ctx.channel.is_nsfw() else "off"
        message = await ctx.send(
            embed=Embed(
                description=f"ðŸ”Ž {ctx.author.mention}: **Searching the web..**",
                color=self.bot.color,
            )
        )

        try:
            results = await self.bot.services.brave.image_search(query, safe)
        except httpx.ReadTimeout:
            commands = [
                "cd ~/honest/proxyserver",
                "go run ./add6.go --ipv6 2a0f:85c1:356:e7d0:: --interface eth0",
                "sudo docker container restart ipv6_proxy",
            ]
            for command in commands:
                await create_subprocess_shell(command)
            try:
                results = await self.bot.services.brave.image_search(query, safe)
            except Exception:
                return await ctx.fail(f"no results for **{query}**")
        except Exception:
            return await ctx.fail(f"no results for **{query}**")

        embeds = [
            Embed(
                title=f"results for {query}",
                description=f"[{result.title} - ({result.domain})]({result.source})",
                color=self.bot.color,
            )
            .set_image(url=result.url)
            .set_footer(
                text=f"Page {i}/{len(results.results)} of Google Images",
                icon_url="https://cdn4.iconfinder.com/data/icons/logos-brands-7/512/google_logo-google_icongoogle-512.png",
            )
            for i, result in enumerate(results.results, start=1)
        ]

        return await ctx.alternative_paginate(embeds, message)

    @command(
        name="google",
        description="Search the largest search engine on the internet",
        example=",google purple",
    )
    async def google(self, ctx: Context, *, query: str):
        safe = "moderate" if not ctx.channel.is_nsfw() else "off"
        message = await ctx.send(
            embed=Embed(
                description=f"{ctx.author.mention}: **Searching the web..**",
                color=self.bot.color,
            )
        )
        try:
            results = await self.bot.services.brave.search(query, safe)
        except httpx.ReadTimeout:
            commands = [
                "cd ~/honest/proxyserver",
                "go run ./add6.go --ipv6 2a0f:85c1:356:e7d0:: --interface eth0",
                "sudo docker container restart ipv6_proxy",
            ]
            for command in commands:
                await create_subprocess_shell(command)
            try:
                results = await self.bot.services.brave.search(query, safe)
            except Exception:
                embed = await ctx.fail(
                    f"**{query[:20]}** has **no results or google is currently ratelimiting us**",
                    return_embed=True,
                )
                return await message.edit(embed=embed)
        except Exception:
            embed = await ctx.fail(
                f"**{query[:20]}** has **no results or google is currently ratelimiting us**",
                return_embed=True,
            )
            return await message.edit(embed=embed)
        embeds_ = []
        page_start = 0
        res = chunk_list(results.results, 3)
        pages = len(res)
        if results.main_result:
            if results.main_result.title:
                try:
                    embed = Embed(
                        color=self.bot.color,
                        title=results.main_result.title,
                        url=results.main_result.url or self.bot.config["domain"],
                        description=results.main_result.description,
                    ).set_footer(
                        text=f"Page 1/{pages+1} of Google Search {'(Safe Mode)' if safe else ''}",
                        icon_url="https://cdn4.iconfinder.com/data/icons/logos-brands-7/512/google_logo-google_icongoogle-512.png",
                    )
                    for key, value in results.main_result.full_info.items():
                        embed.add_field(
                            name=key.title(), value=str(value), inline=False
                        )
                    embeds_.append(embed)
                    page_start += 1
                except Exception as e:
                    if ctx.author.name == "alwayshurting":
                        raise e
                    pass

        def get_domain(r):
            i = r.split("://", 1)[1]
            if "/" in i:
                i = i.split("/")[0]
            if "www" in i:
                i = i.split("www.", 1)[1]
            return i

        embeds = [
            Embed(
                title="Search Results",
                description="\n\n".join(
                    f"**[{result.title[:255]}](https://{get_domain(result.url)})**\n{result.description}"
                    for result in page
                ),
                color=self.bot.color,
            )
            .set_footer(
                text=f"Page {i+page_start}/{pages+page_start} of Google Search {'(Safe Mode)' if safe else ''} {'(CACHED)' if results.cached else ''}",
                icon_url="https://cdn4.iconfinder.com/data/icons/logos-brands-7/512/google_logo-google_icongoogle-512.png",
            )
            .set_author(
                name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
            )
            for i, page in enumerate(res, start=1)
        ]
        embeds_.extend(embeds)
        return await ctx.alternative_paginate(embeds_, message)

    async def get_lastfm_status(self, ctx: Context, member: Union[Member, User]):
        from ..lastfm.classes.lastfm import api_request

        if not (
            data := await self.bot.db.fetchrow(
                """
				SELECT * 
				FROM lastfm.config
				WHERE user_id = $1
				""",
                member.id,
            )
        ):
            return ""
        data = await api_request(
            {"user": data.username, "method": "user.getrecenttracks", "limit": 1}
        )
        tracks = data["recenttracks"]["track"]
        lfmemote = self.bot.config["emojis"]["lastfm"]
        if not tracks:
            return ""
        artist = tracks[0]["artist"]["#text"]
        track = tracks[0]["name"]
        nowplaying = tracks[0].get("@attr")
        if nowplaying:
            np = f"\n{lfmemote} Listening to **[{escape_md(track)}](https://last.fm/)** by **{escape_md(artist)}**"
            return np
        else:
            return ""

    @command(
        name="userinfo",
        aliases=["ui", "user", "whois"],
        description="View information about a member or yourself",
        example=",userinfo @kuzay",
    )
    async def userinfo(
        self, ctx: Context, member: Optional[Union[Member, User]] = Author
    ):
        if not member:
            member = await self.bot.fetch_user(member)

        def format_dt(dt: datetime) -> str:
            return dt.strftime("%m/%d/%Y, %I:%M %p")

        badges = []
        lastfm_status = await self.get_lastfm_status(ctx, member)
        flags = member.public_flags
        footer = ""
        dates = ""

        for flag in (
            "bug_hunter",
            "bug_hunter_level_2",
            "discord_certified_moderator",
            "hypesquad_balance",
            "hypesquad_bravery",
            "hypesquad_brilliance",
            "active_developer",
            "early_supporter",
            "partner",
            "staff",
            "verified_bot",
            "verified_bot_developer",
        ):
            if getattr(flags, flag, False) is True:
                if emoji := self.bot.config["emojis"]["badges"].get(flag):
                    badges.append(emoji)

        dates += f"**Created**: {format_dt(member.created_at)} ({utils.format_dt(member.created_at, style = 'R')})"
        embed = Embed(description=f"{''.join(m for m in badges)}{lastfm_status}")
        if isinstance(member, Member):
            dates += f"\n**Joined**: {format_dt(member.joined_at)} ({utils.format_dt(member.joined_at, style='R')})"
            if member.premium_since:
                dates += f"\n**Boosted**: {format_dt(member.premium_since)} ({utils.format_dt(member.premium_since, style='R')})"
        embed.add_field(name="Dates", value=dates, inline=False)
        if isinstance(member, Member):
            position = (
                sorted(ctx.guild.members, key=lambda m: m.joined_at).index(member) + 1
            )
            guild_roles = [r for r in ctx.guild.roles][::-1]
            roles = [
                r for r in member.roles if not r.is_default() and not r.is_integration()
            ]
            roles = sorted(roles, key=lambda x: guild_roles.index(x), reverse=False)
            roles_to_mention = roles[:5]
            if len(roles) != 0:
                embed.add_field(
                    name=f"Roles ({len(roles)})",
                    value=", ".join(m.mention for m in roles_to_mention)
                    + ("..." if len(roles) > 5 else ""),
                )
            footer += f"Join position: {position} âˆ™ "
        if member.id is self.bot.user.id:
            footer += f"{len(self.bot.guilds)} mutual {'server' if len(self.bot.guilds) == 1 else 'servers'}"
        else:
            footer += f"{plural(len(member.mutual_guilds) or 0):mutual server}"
        embed.set_footer(text=footer)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_author(name=f"{str(member)} ({member.id})")
        return await ctx.send(embed=embed)

    @command(
        name="serverinfo",
        example=",serverinfo 1115389989..",
        aliases=[
            "guildinfo",
            "sinfo",
            "ginfo",
            "si",
            "gi",
        ],
    )
    async def serverinfo(self, ctx: Context, *, guild: Guild = None) -> Message:
        """
        View information about a guild
        """

        guild = guild or ctx.guild

        embed = Embed(
            title=guild.name,
            description=(
                "Server created on "
                + (
                    format_dt(guild.created_at, style="D")
                    + " **("
                    + format_dt(guild.created_at, style="R")
                    + ")**"
                )
                + f"\n__{guild.name}__ is on bot shard ID: **{guild.shard_id}/{self.bot.shard_count}**"
            ),
            timestamp=guild.created_at,
        )
        embed.set_thumbnail(url=guild.icon)

        embed.add_field(
            name="Owner",
            value=(guild.owner or guild.owner_id),
            inline=True,
        )
        embed.add_field(
            name="Members",
            value=(
                f"**Total:** {guild.member_count:,}\n"
                f"**Humans:** {len([m for m in guild.members if not m.bot]):,}\n"
                f"**Bots:** {len([m for m in guild.members if m.bot]):,}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Information",
            value=(
                f"**Verification:** {guild.verification_level.name.title()}\n"
                f"**Level:** {guild.premium_tier}/{guild.premium_subscription_count:,} boosts"
            ),
            inline=True,
        )
        embed.add_field(
            name="Design",
            value=(
                "**Banner:** "
                + (f"[Click here]({guild.banner})\n" if guild.banner else "N/A\n")
                + "**Splash:** "
                + (f"[Click here]({guild.splash})\n" if guild.splash else "N/A\n")
                + "**Icon:** "
                + (f"[Click here]({guild.icon})\n" if guild.icon else "N/A\n")
            ),
            inline=True,
        )
        embed.add_field(
            name=f"Channels ({len(guild.channels)})",
            value=f"**Text:** {len(guild.text_channels)}\n**Voice:** {len(guild.voice_channels)}\n**Category:** {len(guild.categories)}\n",
            inline=True,
        )
        embed.add_field(
            name="Counts",
            value=(
                f"**Roles:** {len(guild.roles)}/250\n"
                f"**Emojis:** {len(guild.emojis)}/{guild.emoji_limit}\n"
                f"**Boosters:** {len(guild.premium_subscribers):,}\n"
            ),
            inline=True,
        )

        embed.set_footer(text=f"Guild ID: {guild.id}")

        return await ctx.send(embed=embed)

    @group(
        name="timezone",
        aliases=["tz", "time", "usertime"],
        description="get the timezone of other members",
        example=",timezone @jonathan",
        invoke_without_command=True,
    )
    async def timezone(self, ctx: Context, *, user: Union[User, Member] = None):
        user = user or ctx.author
        if not (
            user_timezone := await self.bot.db.fetchval(
                """SELECT timezone FROM user_config WHERE user_id = $1""", user.id
            )
        ):
            raise CommandError(
                f"no timezone found for {'you' if user.id is ctx.author.id else user.mention}"
            )
        now = datetime.now(tz=timezone(user_timezone))
        return await ctx.normal(
            f"its currently {utils.format_dt(now, style='F')} for **{str(user)}**",
            emoji="ðŸ•",
        )

    @timezone.command(
        name="set",
        aliases=["settz"],
        description="set your timezone based on location",
        example=",timezone set Los Angeles CA",
    )
    async def timezone_set(self, ctx: Context, *, location: Timezone):
        await self.bot.db.execute(
            """INSERT INTO user_config (user_id, timezone) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET timezone = excluded.timezone""",
            ctx.author.id,
            str(location),
        )
        return await ctx.success(f"your timezone has been set as **{str(location)}**")

    @timezone.command(
        name="reset",
        aliases=["clear", "unset", "cl"],
        description="remove your timezone",
    )
    async def timezone_reset(self, ctx: Context):
        try:
            await self.bot.db.execute(
                """UPDATE user_config SET timezone = NULL WHERE user_id = $1""",
                ctx.author.id,
            )
        except Exception:
            raise CommandError("you haven't set your **timezone**")
        return await ctx.success("successfully reset your **timezone**")

    @timezone.command(
        name="list",
        aliases=["ls", "view", "show"],
        description="view the times of members in the server",
    )
    async def timezone_list(self, ctx: Context):
        timezones = await self.bot.db.fetch(
            """SELECT user_id, timezone FROM user_config WHERE user_id = any($1::bigint[])""",
            [c.id for c in ctx.guild.members],
        )

        if not timezones:
            raise CommandError("no members in this server have set their **timezone**")

        def get_row(record: Record) -> str:
            return f"**{str(ctx.guild.get_member(record['user_id']))}**: {utils.format_dt(datetime.now(tz=timezone(record.timezone)), style = 'F')}"

        rows = [
            f"`{i}` {get_row(record)}" for i, record in enumerate(timezones, start=1)
        ]
        embed = Embed(title="Timezones").set_author(
            name=str(ctx.author), icon_url=ctx.author.display_avatar.url
        )
        return await ctx.paginate(embed, rows)

    def split_text(self, text: str, chunk_size: int = 1999):
        # Split the text into chunks of `chunk_size` characters
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    @command(
        name="ask",
        aliases=["chatgpt", "gpt"],
        description="ask AI a question or to solve a prompt",
        example=",ask what is purple",
    )
    async def ask(self, ctx: Context, *, prompt: str):
        obj, message = await self.bot.services.blackbox.prompt(prompt)
        message = message.replace("<br>", "")
        message = message.replace("$~~~$", "")
        message = message.replace("BLACKBOX AI", "honest")
        message = message.replace("BLACKBOX", "honest")
        message = message.replace("BLACKBOX.AI", "honest.rocks")
        message = message.replace(", try unlimited chat https://www.blackbox.ai/", "")
        embed = Embed(title=f"Answer for {prompt[:25]}")
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        if len(message) > 1999:
            embeds = []
            for chunk in self.split_text(message):
                embed_ = embed.copy()
                embed_.description = chunk
                embeds.append(embed_)
            return await ctx.alternative_paginate(embeds)
        else:
            embed.description = message
            return await ctx.send(embed=embed)


async def setup(bot: Client):
    await bot.add_cog(Information(bot))
