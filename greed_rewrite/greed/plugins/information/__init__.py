import math
import time
import pytz
import aiohttp
import psutil
import logging
import matplotlib
import matplotlib.pyplot as plt
import discord

from .config.emojis import EMOJIS
from .config.classes import (
    Image,
    CommandTransformer,
    CategoryTransformer,
    UrbanDefinition,
)
from .utils import plural, get_timezone

from greed.framework.pagination import Paginator
from greed.shared.config import Colors, Authentication
from greed.framework import Context, Greed
from greed.framework.tools.formatter import shorten

from discord import (
    Member,
    User,
    Role,
    Interaction,
    app_commands,
    Color,
    Embed,
    utils,
    Guild,
    ButtonStyle,
    Status,
    TextChannel,
    File,
)
from discord.ui import Button, View
from discord.ext import commands
from discord.ext.commands import (
    command,
    group,
    CommandError,
    param,
    Cog,
    Author,
    has_permissions,
)

from difflib import get_close_matches
from io import BytesIO
from datetime import datetime
from aiohttp import ContentTypeError
from typing import Union, Optional, Annotated
from munch import DefaultMunch
from matplotlib.patches import PathPatch, Path
from cashews import cache
from color_processing import ColorInfo


logger = logging.getLogger("greed/plugins/information")

cache.setup("mem://")


class Information(Cog):
    def __init__(self, bot: Greed):
        self.bot = bot
        self.command_count = len(
            [
                cmd
                for cmd in list(self.walk_commands())
                if cmd.cog_name not in ("Jishaku", "events", "Owner")
            ]
        )

    async def update_server_stats(self, guild_id: int, column: str):
        await self.bot.db.execute(
            f"""
            INSERT INTO guilds_stats (guild_id, {column})
            VALUES ($1, 1)
            ON CONFLICT (guild_id)
            DO UPDATE SET {column} = guilds_stats.{column} + 1
            """,
            guild_id,
        )

    async def get_time(self, timezone: str):
        try:
            tz = pytz.timezone(timezone)
            logger.info(tz)
            return datetime.now(tz=tz).strftime("%-I:%M%p").lower()
        except pytz.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {timezone}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.update_server_stats(member.guild.id, "joins")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.update_server_stats(member.guild.id, "leaves")

    async def lf(self, member: Union[Member, User]):
        """
        Fetch Last.FM user data from database.
        """
        if not (
            conf := await self.bot.db.fetchrow(
                """
            SELECT * FROM lastfm.conf 
            WHERE user_id = $1
            """,
                member.id,
            )
        ):
            return None

        try:
            data = await self.requester.get(
                method="user.getrecenttracks", user=conf["username"]
            )
            if "error" in data:
                return None

            track_data = data.get("recenttracks", {}).get("track", [])
            if track_data:
                track_name = track_data[0]["name"]
                track_url = track_data[0]["url"]
                artist_name = track_data[0]["artist"]["#text"]
                return f"<a:{EMOJIS['lastfm']}> Listening to **{track_name}**"

        except Exception as e:
            print(f"Error fetching LastFM data: {e}")

        return None

    @command(aliases=["mc", "membercount"])
    async def guildstats(self, ctx: Context):
        """
        Displays the number of joins, leaves, and total members for the server.
        """
        total_users = len(ctx.guild.members)
        total_members = len([member for member in ctx.guild.members if not member.bot])
        total_bots = total_users - total_members

        record = await self.bot.db.fetchrow(
            """
            SELECT joins, leaves 
            FROM guilds_stats 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        joins = record["joins"] if record else 0
        leaves = record["leaves"] if record else 0

        embed = Embed(
            title=f"**{ctx.guild.name}**",
            color=Colors().information,
        )

        embed.add_field(
            name="> Total",
            value=f"<:{EMOJIS['line']}> **`{total_users}`** <:{EMOJIS['person']}>",
            inline=False,
        )

        embed.add_field(
            name="> Joins",
            value=f"<:{EMOJIS['line']}> **`{joins}`** <:{EMOJIS['join']}>",
            inline=False,
        )

        embed.add_field(
            name="> Leaves",
            value=f"<:{EMOJIS['line']}> **`{leaves}`** <:{EMOJIS['leave']}>",
            inline=False,
        )

        embed.add_field(
            name="> Bots",
            value=f"<:{EMOJIS['line']}> **`{total_bots}`** <:{EMOJIS['bot']}>",
            inline=True,
        )

        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

        embed.set_footer(
            text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar
        )

        await ctx.send(embed=embed)

    @command(aliases=["lvl", "rank", "rnk", "activity"])
    async def level(self, ctx: Context, *, member: Optional[Member] = Author):
        """
        See the level of a user.
        """
        enabled = bool(
            await self.bot.db.fetchrow(
                """
                SELECT 1 
                FROM text_level_settings 
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
        )
        if not enabled:
            return await ctx.embed(
                message="Leveling has not been enabled!", message_type="warned"
            )

        data = await self.bot.db.fetchrow(
            """
            SELECT xp, msgs FROM text_levels 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            ctx.guild.id,
            member.id,
        )

        if not data:
            return await ctx.embed(message="No data found yet!", message_type="warned")

        xp = int(data["xp"])
        messages = int(data["msgs"])

        current_level = math.floor(0.05 * (1 + math.sqrt(5)) * math.sqrt(xp)) + 1
        needed_xp = math.ceil(
            math.pow((current_level) / (0.05 * (1 + math.sqrt(5))), 2)
        )

        percentage = min(100, int((xp / needed_xp) * 100))

        async with ctx.typing():
            matplotlib.use("Agg")

            bar_width = 10
            height = 1
            corner_radius = 0.2

            fig, ax = plt.subplots(figsize=(bar_width, height))

            width_1 = (percentage / 100) * bar_width
            width_2 = ((100 - percentage) / 100) * bar_width

            if width_1 > 0:
                path_data = [
                    (Path.MOVETO, [corner_radius, 0]),
                    (Path.LINETO, [width_1, 0]),
                    (Path.LINETO, [width_1, height]),
                    (Path.LINETO, [corner_radius, height]),
                    (Path.CURVE3, [0, height]),
                    (Path.CURVE3, [0, height - corner_radius]),
                    (Path.LINETO, [0, corner_radius]),
                    (Path.CURVE3, [0, 0]),
                    (Path.CURVE3, [corner_radius, 0]),
                ]
                codes, verts = zip(*path_data)
                path = Path(verts, codes)
                patch = PathPatch(path, facecolor="#2f4672", edgecolor="none")
                ax.add_patch(patch)

            if width_2 > 0:
                path_data = [
                    (Path.MOVETO, [width_1, 0]),
                    (Path.LINETO, [bar_width - corner_radius, 0]),
                    (Path.CURVE3, [bar_width, 0]),
                    (Path.CURVE3, [bar_width, corner_radius]),
                    (Path.LINETO, [bar_width, height - corner_radius]),
                    (Path.CURVE3, [bar_width, height]),
                    (Path.CURVE3, [bar_width - corner_radius, height]),
                    (Path.LINETO, [width_1, height]),
                    (Path.LINETO, [width_1, 0]),
                ]
                codes, verts = zip(*path_data)
                path = Path(verts, codes)
                patch = PathPatch(path, facecolor="black", edgecolor="none")
                ax.add_patch(patch)

            ax.set_xlim(0, bar_width)
            ax.set_ylim(0, height)
            ax.axis("off")

            bar_img = BytesIO()
            plt.savefig(
                bar_img,
                format="png",
                bbox_inches="tight",
                pad_inches=0,
                transparent=True,
            )
            plt.close(fig)
            bar_img.seek(0)

            bar = File(fp=bar_img, filename="bar.png")

            embed = (
                Embed(
                    title=f"{member}'s text Level",
                    url=f"{self.bot.domain}",
                    color=0x2F4672,
                )
                .add_field(name="Messages", value=messages, inline=True)
                .add_field(name="Level", value=current_level, inline=True)
                .add_field(name="XP", value=f"{xp} / {needed_xp}", inline=True)
                .set_image(url=f"attachment://{bar.filename}")
            )

            await ctx.send(embed=embed, file=bar)

    @app_commands.command()
    async def help(
        self,
        interaction: Interaction,
        category: Optional[Annotated[commands.Cog, CategoryTransformer]] = None,
        command: Optional[Annotated[commands.Command, CommandTransformer]] = None,
    ):
        if category is not None:
            pass
        elif command is not None:
            pass
        else:
            pass

        ctx = await self.bot.get_context(interaction)
        return await ctx.send_help()

    @command(aliases=["reversesearch"])
    async def reverse(
        self,
        ctx: Context,
        *,
        image: Image = param(
            default=Image.fallback,
            description="The image to search.",
        ),
    ):
        """
        Reverse image search using TinEye.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    "POST",
                    "https://tineye.com/api/v1/result_json/",
                    params={
                        "sort": "score",
                        "order": "desc",
                    },
                    data={
                        "image": image.fp,
                    },
                ) as response:
                    data = DefaultMunch.fromDict(await response.json())
                    logger.info(data)
                    if not data.matches:
                        return await ctx.embed(
                            message=f"Couldn't find any matches for [`{data.query.hash}`]({image.url})!",
                            message_type="warned",
                        )

        except ContentTypeError:
            return await ctx.embed(
                message=f"Couldn't find any matches for [`this image`]({image.url})!",
                message_type="warned",
            )

        embed = Embed(
            title="Reverse Image Lookup",
            description=(
                f"Found {plural(data.num_matches, md='`'):match|matches} for [`{image.filename}`]({image.url})."
            ),
        )

        embed.set_thumbnail(url=image.url)

        for match in data.matches[:4]:
            backlink = match.backlinks[0]

            embed.add_field(
                name=match.domain,
                value=f"[`{shorten(backlink.backlink.replace('https://', '').replace('http://', ''))}`]({backlink.url})",
                inline=False,
            )

        return await ctx.send(embed=embed)

    @group(
        name="timezone",
        aliases=["tz", "time"],
        invoke_without_command=True,
    )
    async def timezone(
        self, ctx: Context, member: Optional[Union[Member, User]] = Author
    ):
        """
        Get the time.
        """
        if record := await self.bot.db.fetchval(
            """
            SELECT tz FROM timezone 
            WHERE user_id = $1
            """,
            member.id,
        ):
            return await ctx.embed(
                message=f"{member.mention}'s current time is ``{await self.get_time(record)}``",
                message_type="neutral",
            )
        else:
            return await ctx.embed(
                message=f"{member.mention} does not have their timezone set!",
                message_type="warned",
            )

    @timezone.command(name="set")
    async def timezone_set(self, ctx: Context, *, timezone: str):
        """
        Set your time via location or timezone.
        """
        current_time = await self.get_time(data)

        try:
            data = await get_timezone(timezone)

        except ValueError:
            return await ctx.embed(
                message="Please provide a valid location!", message_type="warned"
            )

        except Exception:
            return await ctx.embed(
                message="An unexpected error occurred while setting your timezone!",
                message_type="warned",
            )

        await self.bot.db.execute(
            """
            INSERT INTO timezone (user_id, tz) VALUES($1, $2) 
            ON CONFLICT(user_id) DO UPDATE SET tz = excluded.tz
            """,
            ctx.author.id,
            data,
        )
        return await ctx.embed(
            message=f"Your timezone has been set to ``{current_time}``.",
            message_type="approved",
        )

    @command()
    async def ping(self, ctx: Context):
        """
        Shows the current latency of the bot.
        """
        latency = round(self.bot.latency * 1000)
        start_time = time.time()
        message = await ctx.send("ping...")
        end_time = time.time()
        edit_latency = round((end_time - start_time) * 1000)

        embed = Embed(description=f"`{latency}ms` (edit: `{edit_latency}ms`)")

        await message.edit(content=None, embed=embed)

    @command()
    @has_permissions(moderate_members=True)
    async def bans(self, ctx: Context):
        """
        See the bans in the server.
        """
        bans = [ban async for ban in ctx.guild.bans(limit=500)]
        rows = [f"`{i}` {self.try_escape(ban)}" for i, ban in enumerate(bans, start=1)]

        if not rows:
            return await ctx.embed(
                message="No bans found in this server!", message_type="warned"
            )

        return await ctx.paginate(entries=rows, embed=Embed(title="Bans"))

    @command(aliases=["clr", "hex"])
    async def color(
        self, ctx: Context, *, query: Optional[Union[str, User, Member, Color]] = None
    ):
        """
        See the color of a user or hex code.
        """
        if query is None:
            if len(ctx.message.attachments) > 0:
                query = ctx.message.attachments[0].url
            else:
                raise CommandError("You must provide a query or attachment")

        return await ColorInfo().convert(ctx, query)

    @command(name="botinfo", aliases=["bot", "info"])
    async def botinfo(self, ctx):
        """
        View information about the bot.
        """
        guilds = await self.bot.guild_count()
        users = await self.bot.user_count()
        total_guilds = sum(guilds) if isinstance(guilds, list) else guilds

        regular_cogs = len(self.bot.cogs)
        extensions = len(self.bot.extensions)
        total_modules = regular_cogs + extensions
        process = psutil.Process()

        embed = Embed(
            description=(
                f"Developed and maintained by [adam](https://discord.com/users/930383131863842816), [x](https://discord.com/users/585689685771288600), [lego](https://discord.com/users/320288667329495040), [b](https://discord.com/users/442626774841556992)\n"
                f"Utilizing `{len(list(self.bot.walk_commands()))}` commands across `{len(self.bot.cogs)}` cogs (`{total_modules}` total modules)"
            ),
        )

        embed.set_author(
            name=self.bot.user.name,
            icon_url=self.bot.user.display_avatar.url,
            url=Authentication().support_url,
        )

        embed.add_field(
            name="**Bot**",
            inline=True,
            value="\n".join(
                [
                    f"**Users:** `{users:,}`",
                    f"**Servers:** `{total_guilds:,}`",
                    f"**Created:** <t:{int(self.bot.user.created_at.timestamp())}:R>",
                ]
            ),
        )

        embed.add_field(
            name="**System**",
            inline=True,
            value="\n".join(
                [
                    f"**CPU:** `{process.cpu_percent()}%`",
                    f"**Memory:** `{process.memory_info().rss / (1024 * 1024 * 1024):.1f}GB`",
                    f"**Launched:** {discord.utils.format_dt(self.bot.startup_time, 'R')}",
                ]
            ),
        )

        button1 = Button(
            label="Support",
            style=ButtonStyle.gray,
            # emoji=f"<:{EMOJIS['discord']}>",
            url="https://discord.gg/greedbot",
        )

        button2 = Button(
            label="Website",
            style=ButtonStyle.gray,
            emoji=EMOJIS["globe"],
            url="https://greed.best",
        )

        view = View()
        view.add_item(button1)
        view.add_item(button2)

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        return await ctx.send(embed=embed, view=view)

    @command(aliases=["guildinfo", "sinfo", "ginfo", "si", "gi"])
    async def serverinfo(self, ctx: Context, *, guild: Guild = None):
        """
        View information about a server.
        """
        guild = guild or ctx.guild

        responses = await self.bot.ipc.broadcast("get_guild", {"guild_id": guild.id})
        guild_data = next(
            (data for data in responses.values() if data is not None), None
        )

        if not guild_data:
            await ctx.send("Could not fetch guild information.")
            return

        invite = (
            f"[{guild_data['vanity_url_code']}]({guild_data['vanity_url']})"
            if guild_data["vanity_url_code"]
            else "None"
        )

        embed = Embed(
            title=f"{guild_data['name']}",
            description=f'** __Created: __ ** \n{utils.format_dt(datetime.fromisoformat(guild_data['created_at']), style="F")}',
        )

        embed.add_field(
            name="**__Server__**",
            value=f">>> **Members:** {guild_data['member_count']}\n**Level:** {guild_data['premium_tier']}/3\n**Vanity:** {invite}",
            inline=False,
        )

        embed.add_field(
            name="**__Channels__**",
            value=f">>> **Text:** {len(guild_data['text_channels'])}\n**Voice:** {len(guild_data['voice_channels'])}\n**Categories:** {len(guild_data['categories'])}",
            inline=False,
        )

        embed.add_field(
            name="**__Utility__**",
            value=f">>> **Roles:** {len(guild_data['roles'])}\n**Emotes:** {len(guild_data['emojis'])}\n**Boosts:** {guild_data['premium_subscription_count']}",
            inline=False,
        )

        embed.add_field(
            name="**__Design__**",
            value=f">>> **Icon:** {f'[Here]({guild_data["icon"]})' if guild_data['icon'] else 'None'}\n**Splash:** {f'[Here]({guild_data["splash"]})' if guild_data['splash'] else 'None'}\n**Banner:** {f'[Here]({guild_data["banner"]})' if guild_data['banner'] else 'None'}",
        )
        embed.set_footer(
            text=f"Owner: @{guild_data['owner']} | Guild id: {guild_data['id']}"
        )
        embed.set_author(name=f"{ctx.author.name}", icon_url=ctx.author.avatar)

        if guild_data["icon"]:
            embed.set_thumbnail(url=guild_data["icon"])

        await ctx.send(embed=embed)

    @command()
    async def invite(self, ctx: Context):
        """
        Invite the bot to your server.
        """
        invite = self.bot.invite_url
        embed = Embed(description=f"Click **[here]({invite})** to invite the bot.")
        await ctx.send(embed=embed)

    @command(aliases=["ui", "user", "whois"])
    async def userinfo(self, ctx, user: Union[User, Member] = None):
        """
        View some information on a user.
        """
        user = user or ctx.author

        if isinstance(user, User):
            embed = Embed(
                color=Colors().information,
                title=f"{user.name}",
            )
            embed.add_field(
                name="**Created**",
                value=f"**{utils.format_dt(user.created_at, style='D')}**",
                inline=True,
            )
            embed.set_thumbnail(url=user.display_avatar)
            return await ctx.send(embed=embed)

        member_data = await self.bot.ipc.broadcast(
            "get_member", {"guild_id": ctx.guild.id, "user_id": user.id}
        )

        member_info = None
        for cluster_id, data in member_data.items():
            if data is not None:
                member_info = data
                break

        if not member_info:
            return await ctx.send("Could not find member information.")

        mutual_guilds = tuple(g for g in self.bot.guilds if g.get_member(user.id))
        position = sorted(ctx.guild.members, key=lambda m: m.joined_at).index(user) + 1

        badges = []
        staff = []

        emojis = {
            "staff2": EMOJIS["badgediscordstaff"],
            "nitro": EMOJIS["Nitro_badge"],
            "hypesquad_brilliance": EMOJIS["Icon_Hypesquad_Brilliance"],
            "hypesquad_bravery": EMOJIS["hmubravery"],
            "hypesquad_balance": EMOJIS["HypeSquad_Balance"],
            "bug_hunter": EMOJIS["bug_hunter"],
            "bug_hunter_level_2": EMOJIS["bug_hunter_level_2"],
            "discord_certified_moderator": EMOJIS["certified_moderator"],
            "early_supporter": EMOJIS["EarlySupport"],
            "verified_bot_developer": EMOJIS["discord_developer"],
            "partner": EMOJIS["Partner_server_owner"],
            "staff": EMOJIS["Verified_badge_1_staff"],
            "verified_bot": EMOJIS["6_bot"],
            "server_boost": EMOJIS["boost_badge"],
            "active_developer": EMOJIS["ActiveDeveloper"],
            "pomelo": EMOJIS["pomelo"],
            "web_idle": EMOJIS["IconStatusWebIdle"],
            "web_dnd": EMOJIS["IconStatusWebDND"],
            "web_online": EMOJIS["IconStatusWebOnline"],
            "desktop_dnd": EMOJIS["hmudnd"],
            "desktop_idle": EMOJIS["hmuIdle"],
            "desktop_online": EMOJIS["online2"],
            "mobile_dnd": EMOJIS["dndphone"],
            "mobile_idle": EMOJIS["idlephone"],
            "mobile_online": EMOJIS["onlinephone"],
            "web_offline": "",
            "mobile_offline": "",
            "desktop_offline": "",
        }

        devices = (
            ", ".join(
                k
                for k, v in {
                    "desktop": user.desktop_status,
                    "web": user.web_status,
                    "mobile": user.mobile_status,
                }.items()
                if v != Status.offline
            )
            or "none"
        )

        badges = " ".join(badges)
        staff = " ".join(staff)

        status_emoji = ""

        if devices != "none":
            status_emoji = " ".join(
                emojis.get(f"{device}_{user.status.name.lower()}", "")
                for device in devices.split(", ")
            )

        status = ""

        if user.activity:
            start = user.activity.type.name.capitalize()

            if start == "Custom":
                start = ""

            if start == "Listening":
                start = "Listening to"

            status = f"{start} {user.activity.name}"

        if status == "":
            status = ""

        lastfm_status = await self.lf(user)

        if lastfm_status:
            lastfm_status = f"{lastfm_status}"
        else:
            lastfm_status = ""

        embed = Embed(
            color=Colors().information,
            title=f"{staff}\n{user.name} {badges}",
            description=f"{status_emoji} {status}\n{lastfm_status}",
        )

        embed.add_field(
            name="**Created**",
            value=f"**{utils.format_dt(user.created_at, style='D')}**",
            inline=True,
        )

        embed.add_field(
            name="**Joined**",
            value=f"**{utils.format_dt(datetime.fromisoformat(member_info['joined_at']), style='D')}**",
            inline=True,
        )

        if user.premium_since:
            embed.add_field(
                name="**Boosted server**",
                value=f"**{utils.format_dt(user.premium_since, style='D')}**",
            )

        if member_info["roles"]:
            roles = ", ".join(
                [f"<@&{role_id}>" for role_id in member_info["roles"][:5]]
            ) + (
                f" + {len(member_info['roles']) - 5} more"
                if len(member_info["roles"]) > 5
                else ""
            )

            embed.add_field(name="**__Roles__**", value=f"{roles}", inline=False)

        embed.set_thumbnail(url=user.display_avatar)

        embed.set_footer(
            text=f"{len(mutual_guilds)} mutuals, Join position: {position}"
        )

        await ctx.send(embed=embed)

    @command(
        aliases=["sav"],
    )
    async def serveravatar(self, ctx, *, user: Member = None):
        """
        View the server avatar of a user.
        """
        embed = Embed(
            title=f"{user.name}'s server avatar",
            url=user.guild_avatar if user.guild_avatar else user.display_avatar,
        )
        embed.set_image(
            url=user.guild_avatar if user.guild_avatar else user.display_avatar
        )
        embed.set_author(name=f"{ctx.author.display_name}", icon_url=ctx.author.avatar)
        await ctx.send(embed=embed)

    @command(aliases=["userbanner", "ub"])
    async def banner(self, ctx: Context, *, user: Member = None):
        """
        View the banner of a user.
        """
        member = user or ctx.author
        user = await self.bot.fetch_user(member.id)

        if not user.banner:
            return await ctx.embed(
                message=f"{user.mention if user != ctx.author else 'You'} do not have a banner!",
                message_type="warned",
            )

        embed = Embed(
            title=f"{user.name if user != ctx.author.name else 'Your'} banner",
            url=user.banner,
        )
        embed.set_author(
            name=f"{ctx.author.display_name}", icon_url=ctx.author.display_avatar
        )
        embed.set_image(url=user.banner)
        await ctx.send(embed=embed)

    @command(
        name="serverbanner",
        brief="View the server banner of a user",
        example=",serverbanner @lim",
        aliases=["sb"],
    )
    async def serverbanner(self, ctx, *, user: Member = None):
        user = user or ctx.author
        banner_url = user.guild_banner
        if banner_url is None:
            return await ctx.embed(f"{user.mention} **has no server banner**", "warned")
        e = discord.Embed(
            title=f"{user.name}'s server banner",
            url=banner_url,
            color=Colors().information,
        )
        e.set_author(
            name=f"{ctx.author.display_name}", icon_url=ctx.author.display_avatar
        )
        e.set_image(url=banner_url)
        await ctx.send(embed=e)

    @command(
        name="guildicon",
        brief="View the icon of a server",
        example=",guildicon",
        aliases=["icon", "servericon", "sicon", "gicon"],
    )
    async def servericon(self, ctx, *, guild: Guild = None):
        guild = guild or ctx.guild
        e = discord.Embed(
            title=f"{guild.name}'s icon", url=guild.icon, color=Colors().information
        )
        e.set_author(
            name=f"{ctx.author.display_name}", icon_url=ctx.author.display_avatar
        )
        e.set_image(url=guild.icon)
        await ctx.send(embed=e)

    @command(
        name="guildbanner",
        brief="View the banner of a server using its ID or vanity URL.",
        usage=",guildbanner [server_id | vanity_url]",
        aliases=["gb"],
    )
    async def guildbanner(self, ctx, *, input_value: str = None):
        guild = None

        if input_value is None:
            guild = ctx.guild
        else:
            if input_value.isdigit():
                guild = self.bot.get_guild(int(input_value))

            if guild is None:
                try:
                    invite = await self.bot.fetch_invite(input_value)
                    guild = invite.guild
                except discord.NotFound:
                    return await ctx.embed("Invalid server ID or vanity URL.", "warned")
                except discord.Forbidden:
                    return await ctx.embed(
                        "I do not have permission to fetch this invite.", "warned"
                    )
                except discord.HTTPException:
                    return await ctx.embed(
                        "An error occurred while fetching the invite.", "warned"
                    )

        if guild is None:
            return await ctx.embed("Unable to find the server.", "warned")

        if not guild.banner:
            return await ctx.embed("This server does not have a banner.", "warned")

        total_guilds = len(self.bot.guilds)

        embed = discord.Embed(
            title=f"{guild.name}'s Banner",
            url=guild.banner.url,
            color=Colors().information,
        )
        embed.set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar
        )
        embed.set_image(url=guild.banner.url)

        await ctx.send(embed=embed)

    @command(
        name="guildsplash",
        brief="View the splash of a server",
        example="guildsplash",
        aliases=["splash", "serversplash"],
    )
    async def serversplash(self, ctx, *, guild: Guild = None):
        guild = guild or ctx.guild
        e = discord.Embed(
            color=Colors().information, title=f"{guild.name}'s splash", url=guild.splash
        )
        e.set_author(
            name=f"{ctx.author.display_name}", icon_url=ctx.author.display_avatar
        )
        e.set_image(url=guild.splash)
        await ctx.send(embed=e)

    @command(
        name="roles",
        brief="View the server roles",
        example=",roles",
        aliases=["rolelist"],
    )
    async def roles(self, ctx):
        await ctx.typing()
        embeds = []
        ret = []
        num = 0
        pagenum = 0
        if ctx.guild.roles is None:
            return
        for role in ctx.guild.roles[::-1]:
            if role.name != "@everyone":
                num += 1
                ret.append(f"``{num}.`` {role.mention}")

        if not ret:
            return await ctx.embed("No roles found in this server.", "warned")

        pages = [p for p in discord.utils.as_chunks(ret, 10)]
        for page in pages:
            pagenum += 1
            embeds.append(
                discord.Embed(
                    title="List of Roles",
                    color=Colors().information,
                    description="\n".join(page),
                )
                .set_author(
                    name=ctx.author.display_name, icon_url=ctx.author.display_avatar
                )
                .set_footer(text=f"Page {pagenum}/{len(pages)}")
            )
        if len(embeds) == 1:
            return await ctx.send(embed=embeds[0])
        else:
            await ctx.paginate(embeds)

    @command(
        name="clearnames",
        aliases=["clearnamehistory", "clnh", "clearnh"],
        brief="clear a user's name history",
        example=",clearnames @lim",
    )
    async def clearnames(self, ctx, *, user: User = None):
        if user is None:
            user = ctx.author

        await self.bot.db.execute("DELETE FROM names WHERE user_id = $1", user.id)
        await ctx.embed(f"Successfully cleared the name history for **{str(user)}**.", "approved")

    @command(
        name="names",
        aliases=["namehistory", "nh", "namehist"],
        brief="show a user's name history",
        example=",names @lim",
    )
    async def names(self, ctx, *, user: User = None):
        if user is None:
            user = ctx.author
        if data := await self.bot.db.fetch(
            "SELECT username, ts, type FROM names WHERE user_id = $1 ORDER BY ts DESC",
            user.id,
        ):
            embed = discord.Embed(
                title=f"{str(user)}'s names",
                color=Colors().information,
                url=self.bot.domain,
            )
            rows = []
            for i, name in enumerate(data, start=1):
                name_type = str(name.type)[0].upper()
                rows.append(
                    f"`{i}{name_type}.` **{name.username}** - {discord.utils.format_dt(name.ts, style='R')}"
                )
            await Paginator(ctx, rows, embed=embed).start()
        return await ctx.embed(f"No **name history** found for **{str(user)}**", "warned")

    @command(
        name="inrole",
        brief="list all users that has a role",
        aliases=["irole"],
        example=",inrole admin",
    )
    async def inrole(self, ctx, *, role: Role):
        role = role[0]

        ret = []

        content = discord.Embed(
            color=Colors().information,
            title=f"Members with {role.name}",
        ).set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar)

        for i, m in enumerate(role.members, start=1):
            ret.append(f"`{i}` {m.mention} (``{m.id}``)")

        if not ret:
            return await ctx.embed(f"no role found named `{role}`", "warned")

        await Paginator(ctx, ret, embed=content).start()

    @command(
        name="roleinfo",
        brief="Shows information on a role",
        example=",roleinfo admin",
        usage="<role>",
    )
    async def roleinfo(self, ctx, *, role: Union[Role, str]):
        if isinstance(role, str):
            matches = get_close_matches(
                role, [r.name for r in ctx.guild.roles], cutoff=0.3
            )

            role = discord.utils.get(ctx.guild.roles, name=matches[0])

        timestamp = round(role.created_at.timestamp())

        members = len(role.members)

        percentage = len(role.members) / len(ctx.guild.members) * 100

        role.guild.get_member(role.guild.owner_id)

        embed = discord.Embed(color=role.color, title=role.name)

        embed.add_field(
            name="**__Overview__**",
            value=f""">>> **Created:** \n<t:{timestamp}:D> (<t:{timestamp}:R>)
**Members:** {members} ({percentage:.2f}%)
**Position:** {role.position}""",
        )

        embed.add_field(
            name="**__Misc__**",
            value=f""">>> **Hoist:** {role.hoist}
**Color:** {role.color}
**Managed:** {role.managed}""",
        )

        embed.set_author(
            name=role.name, icon_url=role.display_icon or ctx.author.display_avatar
        )

        embed.set_thumbnail(url=role.display_icon or ctx.author.display_avatar)

        await ctx.send(embed=embed)

    @command(
        name="firstmessage",
        brief="Get a link for the first message in a channel",
    )
    async def firstmessage(self, ctx: Context, channel: TextChannel = None):
        if channel is None:
            channel = ctx.channel

        try:
            async for message in channel.history(limit=1, oldest_first=True):
                if message:
                    link = message.jump_url
                    embed = discord.Embed(
                        description=f"> [First message]({link}) in {channel.mention}\n\n**Message content**:\n{message.content}",
                        color=Colors().information,
                    )
                    await ctx.send(embed=embed)
                    return

            await ctx.embed("No messages found in this channel.", "warned")
        except Exception:
            await ctx.embed("No messages have been found in this channel.", "warned")

    @command(
        name="inviteinfo",
        aliases=["ii"],
        brief="View information on an invite",
    )
    async def inviteinfo(self, ctx, invite: str):
        """View information on an invite"""

        if not invite.startswith("https://discord.gg/"):
            invite = f"https://discord.gg/{invite}"

        try:
            invite = await self.bot.fetch_invite(invite)
        except discord.NotFound:
            return await ctx.embed("Invalid invite URL or code.", "warned")

        embed = discord.Embed(
            color=Colors().information,
        )

        invite_info = [
            f"**Code:** {invite.code}",
            f"**URL:** [Invite]({invite.url})",
            f"**Channel:** {invite.channel.name} (ID: {invite.channel.id})",
            f"**Channel Created:** {discord.utils.format_dt(invite.channel.created_at, style='F')}",
            f"**Invite Expiration:** {discord.utils.format_dt(invite.expires_at, style='F') if invite.expires_at else 'Never'}",
            f"**Inviter:** {invite.inviter.mention if invite.inviter else 'N/A'}",
            f"**Temporary:** {'Yes' if invite.temporary else 'No'}",
            f"**In Use:** {'Yes' if invite.uses else 'No'}",
        ]

        guild_info = [
            f"**Name:** {invite.guild.name}",
            f"**ID:** {invite.guild.id}",
            f"**Created:** {discord.utils.format_dt(invite.guild.created_at, style='F')}",
            f"**Members:** {invite.approximate_member_count if hasattr(invite, 'approximate_member_count') else 'N/A'}",
            f"**Verification Level:** {invite.guild.verification_level}",
        ]

        embed.add_field(
            name="**__Invite & Channel__**",
            value="\n".join([info for info in invite_info if "N/A" not in info]),
            inline=True,
        )

        embed.add_field(
            name="**__Guild__**",
            value="\n".join([info for info in guild_info if "N/A" not in info]),
            inline=True,
        )

        if invite.guild.icon:
            embed.set_thumbnail(url=invite.guild.icon.url)

        embed.set_footer(
            text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed)

    @command(
        name="invites",
        brief="View all invites in the server",
    )
    async def invites(self, ctx):
        invites = await ctx.guild.invites()
        if not invites:
            return await ctx.embed("No invites found in this server.", "warned")

        invites = sorted(invites, key=lambda invite: invite.created_at, reverse=True)

        rows = []
        for i, invite in enumerate(invites, start=1):
            inviter = invite.inviter.mention if invite.inviter else "Unknown"
            created_at = discord.utils.format_dt(invite.created_at, style="R")
            rows.append(f"`{i}.` **{invite.code}** - {inviter} - {created_at}")

        embeds = []
        page = []
        for i, row in enumerate(rows, start=1):
            if i % 10 == 0 and i > 0:
                embeds.append(
                    discord.Embed(
                        color=Colors().information,
                        description="\n".join(page),
                    )
                    .set_author(
                        name=ctx.author.name, icon_url=ctx.author.display_avatar
                    )
                    .set_footer(text=f"Page {len(embeds) + 1}/{(len(rows) + 9) // 10}")
                )
                page = []
            page.append(row)

        if page:
            embeds.append(
                discord.Embed(
                    color=Colors().information,
                    title=f"Invites in {ctx.guild.name}",
                    description="\n".join(page),
                )
                .set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                .set_footer(text=f"Page {len(embeds) + 1}/{(len(rows) + 9) // 10}")
            )

        if not embeds:
            embeds.append(
                discord.Embed(
                    color=Colors().information,
                    description="**No invites found in this server**",
                ).set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            )

        await ctx.paginate(embeds)

    @commands.group(
        invoke_without_command=True,
        example=",boosters",
        brief="List all the current users boosting the guild",
    )
    async def boosters(self, ctx):
        rows = []

        if len(ctx.guild.premium_subscribers) == 0:
            rows.append("Guild Has No Boosters")

        else:
            premium_subscribers = sorted(
                ctx.guild.premium_subscribers,
                key=lambda m: m.premium_since,
                reverse=True,
            )

            for i, booster in enumerate(premium_subscribers, start=1):
                rows.append(
                    f"``{i}.``**{booster.name} ** - {discord.utils.format_dt(booster.premium_since, style='R')} "
                )

        embeds = []

        page = []

        for i, row in enumerate(rows):
            if i % 10 == 0 and i > 0:
                embeds.append(
                    discord.Embed(
                        color=Colors().information,
                        title=f"{ctx.guild.name}'s boosters",
                        url=self.bot.domain,
                        description="\n".join(page),
                    )
                    .set_author(
                        name=ctx.author.name, icon_url=ctx.author.display_avatar
                    )
                    .set_footer(text=f"Page {len(embeds) + 1}/{(len(rows) + 4) // 10}")
                )

                page = []

            page.append(row)

        if page:
            embeds.append(
                discord.Embed(
                    color=Colors().information,
                    title=f"{ctx.guild.name}'s boosters\n",
                    url=self.bot.domain,
                    description="\n".join(page),
                )
                .set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                .set_footer(text=f"Page {len(embeds) + 1}/{(len(rows) + 4) // 10}")
            )

        if not embeds:
            embeds.append(
                discord.Embed(
                    color=Colors().information,
                    description="**This guild has no boosters**",
                ).set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            )

        await ctx.alternative_paginate(embeds)

    async def get_or_fetch(self, user_id: int) -> str:
        if user := self.bot.get_user(user_id):
            return user.global_name or user.name

        else:
            user = await self.bot.fetch_user(user_id)

            return user.global_name or user.name

    @boosters.command(
        name="lost",
        brief="List all users who has recently stopped boosting the server",
        example=",boosters lost",
    )
    async def boosters_lost(self, ctx: Context):
        embed = discord.Embed(
            title="boosters lost", url=self.bot.domain, color=Colors().information
        )

        if rows := await self.bot.db.fetch(
            "SELECT user_id, ts FROM boosters_lost WHERE guild_id = $1 ORDER BY ts DESC",
            ctx.guild.id,
        ):
            lines = []

            for i, row in enumerate(rows, start=1):
                user = await self.get_or_fetch(row["user_id"])

                lines.append(
                    f"`{i}.` **{user}** - {discord.utils.format_dt(row['ts'], style='R')}"
                )
            await Paginator(ctx, lines, embed=embed).start()

        else:
            return await ctx.embed("No **boosters lost** in guild", "warned")

    @command(name="emojis", brief="List all emojis in the server", example=",emojis")
    async def emojis(self, ctx):
        emojis = ctx.guild.emojis

        if len(emojis) == 0:
            embed = discord.Embed(
                color=Colors().information, description="**Guild Has No Emojis**"
            ).set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)

            await ctx.send(embed=embed)

            return

        rows = []

        for i, emoji in enumerate(emojis, start=1):
            emoji_text = f"`{i}.`{str(emoji)}[{emoji.name}](https://cdn.discordapp.com/emojis/{emoji.id}.png)"

            rows.append(emoji_text)

        embeds = []

        page = []

        pagenum = 0

        total_pages = (len(rows) + 9) // 10

        for i, row in enumerate(rows, start=1):
            if i % 10 == 0 and i > 0:
                pagenum += 1

                embeds.append(
                    discord.Embed(
                        color=Colors().information,
                        title=f"{ctx.guild.name}'s Emojis",
                        description="\n".join(page),
                    )
                    .set_author(
                        name=ctx.author.name, icon_url=ctx.author.display_avatar
                    )
                    .set_footer(text=f"Page {pagenum}/{total_pages}")
                )

                page = []

            page.append(row)

        if page:
            pagenum += 1

            embeds.append(
                discord.Embed(
                    color=Colors().information,
                    title=f"{ctx.guild.name}'s Emojis",
                    description="\n".join(page),
                )
                .set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                .set_footer(text=f"Page {pagenum}/{total_pages}")
            )

        if not embeds:
            embeds.append(
                discord.Embed(
                    color=Colors().information, description="**Guild Has No Emojis**"
                ).set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            )

        await ctx.paginate(embeds)

    @command(name="bots", brief="List all bots in the server", example=",bots")
    async def bots(self, ctx):
        bots = [member for member in ctx.guild.members if member.bot]

        if not bots:
            embed = discord.Embed(
                color=Colors().information,
                description="**No bots found in this server**",
            ).set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)

            await ctx.send(embed=embed)

            return

        rows = []

        for i, bot in enumerate(bots, start=1):
            bot_text = f"`{i}.` {bot.mention}"

            rows.append(bot_text)

        embeds = []

        page = []

        for i, row in enumerate(rows, start=1):
            if i % 10 == 0 and i > 0:
                embeds.append(
                    discord.Embed(
                        color=Colors().information,
                        title=f"Bots in {ctx.guild.name}",
                        description="\n".join(page),
                    )
                    .set_author(
                        name=ctx.author.name, icon_url=ctx.author.display_avatar
                    )
                    .set_footer(text=f"Page {len(embeds) + 1}/{(len(rows) + 9) // 10}")
                )

                page = []

            page.append(row)

        if page:
            embeds.append(
                discord.Embed(
                    color=Colors().information,
                    title=f"Bots in {ctx.guild.name}",
                    description="\n".join(page),
                )
                .set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                .set_footer(text=f"Page {len(embeds) + 1}/{(len(rows) + 9) // 10}")
            )

        if not embeds:
            embeds.append(
                discord.Embed(
                    color=Colors().information,
                    description="**No bots found in this server**",
                ).set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
            )

        await ctx.paginate(embeds)

    @command(
        name="channelinfo",
        brief="View information on a channel",
        example=",channelinfo #txt",
    )
    async def channelinfo(self, ctx, channel: TextChannel):
        category = channel.category.name if channel.category else "No category"

        topic = channel.topic if channel.topic else "No topic for this channel"

        creation_date = channel.created_at.strftime("%m-%d-%Y")

        embed = discord.Embed(
            title=f"#{channel.name}",
            color=Colors().information,
            description=f"**Channel ID:** \n``{channel.id}``"
            f"\n**Guild ID:** \n``{channel.guild.id}``"
            f"\n**Category:** ``{category}``"
            f"\n**Type:** ``{channel.type}``\n"
            f"\n**Topic:** __{topic}__\n",
        )

        embed.set_footer(text=f"Creation date: {creation_date}")

        embed.set_author(name=f"{ctx.author.name}", icon_url=ctx.author.avatar)

        await ctx.send(embed=embed)

    async def urban_definition(self, term: str):
        async with self.bot.session.get(
            "https://api.urbandictionary.com/v0/define", params={"term": term}
        ) as response:
            data = await response.json()
            assert data.get("message") != "Internal server error"
            return tuple(UrbanDefinition(**record) for record in data["list"])

    @command(
        name="urbandictionary",
        aliases=("urban", "ud"),
        example=",urbandictionary black",
        brief="Lookup a words meaning using the urban dictionary",
    )
    async def urbandictionary(self, ctx, term: str):
        """
        Get the urban definition of a term.
        """

        if not (data := await self.urban_definition(term)):
            return await ctx.embed("I couldn't find a definition for that word.", "warned")

        embeds = []

        for index, record in enumerate(
            sorted(data[:3], key=lambda record: record.thumbs_up, reverse=True), start=1
        ):
            embeds.append(
                discord.Embed(color=Colors().information)
                .set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
                .add_field(
                    name=f"Urban Definition for '{term}'",
                    value=f"{(record.definition[:650] + ('...' if len(record.definition) > 650 else '')).replace('[', '').replace(']', '')}",
                )
                .add_field(
                    name="Example",
                    value=f"{(record.example[:650] + ('...' if len(record.example) > 650 else '')).replace('[', '').replace(']', '')}",
                    inline=False,
                )
                .set_footer(
                    text=f"Page {index} / {len(data[:3])} | 👍 {record.thumbs_up} 👎 {record.thumbs_down}"
                )
            )

        return await ctx.paginate(embeds)

    @command(
        name="boomer",
        help="Show the oldest member in the guild by account creation date.",
        aliases=["boomers", "oldest"],
    )
    async def boomer(self, ctx):
        oldest_member = min(ctx.guild.members, key=lambda m: m.created_at)

        embed = discord.Embed(title="Oldest Member", color=Colors().information)

        embed.add_field(name="Username", value=oldest_member.name, inline=False)
        embed.add_field(
            name="Account Creation Date",
            value=oldest_member.created_at.strftime("%Y-%m-%d"),
            inline=False,
        )

        await ctx.send(embed=embed)

    @command(
        name="avatar",
        aliases=["av", "useravatar"],
        description="get the mentioned user's avatar",
        brief="avatar [user]",
        help="avatar @lim",
    )
    async def avatar(
        self,
        ctx: Context,
        user: Optional[Union[Member, User]] = commands.Author,
    ):
        embed = discord.Embed(color=Colors().information, title=f"{user.name}'s avatar")
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
        embed.url = user.display_avatar.url
        embed.set_image(url=user.display_avatar)

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="WEBP",
                url=str(user.display_avatar.replace(size=4096, format="webp")),
            )
        )
        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="PNG",
                url=str(user.display_avatar.replace(size=4096, format="png")),
            )
        )
        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="JPG",
                url=str(user.display_avatar.replace(size=4096, format="jpg")),
            )
        )

        return await ctx.reply(embed=embed, view=view)

    @command(name="vote")
    async def vote(self, ctx):
        """Command to send an embed with a button to vote for Greed bot on top.gg."""
        bot_id = str(self.bot.user.id)
        embed = Embed(
            title="Vote for Greed Bot!",
            color=Colors().information,
            description=f"Vote for **{self.bot.user.name}** and get voter perks and econonmy rewards!",
        )
        embed.set_footer(text="You can vote once every 12 hours!")

        button = discord.ui.Button(
            label="Vote Here",
            style=discord.ButtonStyle.link,
            url=f"https://top.gg/bot/{bot_id}/vote",
        )

        view = discord.ui.View()
        view.add_item(button)

        await ctx.send(embed=embed, view=view)

    @command()
    async def buy(self, ctx):
        """Send an embed with purchase options and buttons."""

        embed = discord.Embed(
            title="Greed Premium / Instances",
            description=(
                "Purchase Greed Premium **$3.50** monthly, **$7** one time, and **$12.50** for Instances\n\n"
                "**please open a ticket below after you have purchased one of these plans.**\n\n"
                "Prices and the available payment methods are listed here.\n\n"
                "Please do not ask to pay with Discord Nitro, or to negotiate the price. "
                "You will be either banned or just ignored.\n\n"
                "-# This is not for wrath or any other bot, this is only for **Greed**"
            ),
            color=Colors().information,
        )

        monthly_button = Button(
            label="Monthly - $3.50",
            style=discord.ButtonStyle.green,
            url="https://buy.stripe.com/aEU5odegE3uf3egfZD",
        )
        lifetime_button = Button(
            label="Lifetime - $7",
            style=discord.ButtonStyle.blurple,
            url="https://buy.stripe.com/cN2aIxb4sd4P7uw6p4",
        )
        transfer_button = Button(
            label="Instances - $12.50",
            style=discord.ButtonStyle.blurple,
            url="https://buy.stripe.com/fZeaIxa0oe8T2accNt",
        )

        view = View()
        view.add_item(monthly_button)
        view.add_item(lifetime_button)
        view.add_item(transfer_button)

        await ctx.send(embed=embed, view=view)

    @command(name="bible", brief="Get a random bible verse", example=",bible")
    async def bible(self, ctx):
        """Get a random Bible verse with reference."""
        try:
            async with self.bot.session.get(
                "https://beta.ourmanna.com/api/v1/get/?format=json"
            ) as response:
                if response.status != 200:
                    return await ctx.embed(
                        "Failed to fetch verse. Please try again later.", "warned"
                    )

                data = await response.json()
                if not data.get("verse") or not data["verse"].get("details"):
                    return await ctx.embed("Invalid API response received.", "warned")

                verse = data["verse"]["details"]["text"]
                verse_reference = data["verse"]["details"]["reference"]

                embed = discord.Embed(
                    title="Bible Verse",
                    color=Colors().information,
                    description=f"*{verse}*",
                )
                embed.set_footer(text=verse_reference)
                embed.set_author(
                    name=ctx.author.name, icon_url=ctx.author.display_avatar
                )

                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in bible command: {str(e)}")
            await ctx.embed(
                "An error occurred while fetching the verse. Please try again later.", "warned"
            )

    @command(
        name="quran",
        brief="Get a random quran verse with translation",
        example=",quran",
    )
    async def quran(self, ctx):
        """Get a random Quran verse with English translation."""
        try:
            async with self.bot.session.get(
                "https://api.alquran.cloud/v1/ayah/random/editions/quran-simple-enhanced,en.asad"
            ) as response:
                if response.status != 200:
                    return await ctx.embed(
                        "Failed to fetch verse. Please try again later.", "warned"
                    )

                data = await response.json()
                if not data.get("data") or len(data["data"]) < 2:
                    return await ctx.embed("Invalid API response received.", "warned")

                arabic = data["data"][0]
                english = data["data"][1]

                embed = discord.Embed(
                    title=f"Surah {arabic['surah']['englishName']} ({arabic['surah']['name']})",
                    color=Colors().information,
                )

                embed.description = f"{arabic['text']}\n\n*{english['text']}*"
                embed.set_footer(
                    text=f"Verse {arabic['numberInSurah']} • Juz {arabic['juz']}"
                )
                embed.set_author(
                    name=ctx.author.name, icon_url=ctx.author.display_avatar
                )

                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in quran command: {str(e)}")
            await ctx.embed(
                "An error occurred while fetching the verse. Please try again later.", "warned"
            )


async def setup(bot):
    await bot.add_cog(Information(bot))
