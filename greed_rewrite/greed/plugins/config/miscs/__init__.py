import asyncio
from asyncio import sleep
import io
import random
import re
import typing
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Union, TYPE_CHECKING
from greed.shared.config import Colors

import aiohttp
import arrow
import cairosvg
import discord
import sympy as sp
from cashews import cache
from discord import PartialEmoji, ui
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    command,
    group,
    cooldown,
    has_permissions,
    bot_has_permissions,
    BucketType,
)
from discord.ext import tasks
from loguru import logger
from pydantic import BaseModel

from greed.framework import Context
from discord import Embed
from greed.framework.pagination import Paginator

if TYPE_CHECKING:
    from greed.framework import Greed

DEBUG = True
cache.setup("mem://")
eros_key = "c9832179-59f7-477e-97ba-dca4a46d7f3f"


def generate(img: bytes) -> bytes:
    return cairosvg.svg2png(bytestring=img)

class ReviveMessageView(ui.View):
    def __init__(
        self, message_content: str, guild_id: int, is_embed: bool, cog: "Miscs"
    ):
        super().__init__()
        self.message_content = message_content
        self.guild_id = guild_id
        self.is_embed = is_embed
        self.cog = cog

    @ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.bot.db.execute(
            "INSERT INTO revive (guild_id, message, is_embed) VALUES ($1, $2, $3) "
            "ON CONFLICT (guild_id) DO UPDATE SET message = $2, is_embed = $3",
            self.guild_id,
            self.message_content,
            self.is_embed,
        )
        await interaction.response.edit_message(
            content="✅ Revive message has been updated.", view=None
        )

    @ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content="❌ You have declined this message.", view=None
        )


class Miscs(Cog):
    def __init__(self, bot: "Greed") -> None:
        self.bot = bot
        self.color = Colors().information
        self.bot.afks = {}
        self.locks = {}
        self.revive_loops = {}
        self.revive_tasks = {}
        self.nsfw_domains = [
            "pornhub.com",
            "xvideos.com",
            "xhamster.com",
            "redtube.com",
            "tube8.com",
            "youporn.com",
            "spankwire.com",
            "tnaflix.com",
            "sex.com",
            "bangbros.com",
        ]
        self.queue = defaultdict(asyncio.Lock)
        self.uwu_queue = defaultdict(list)
        self.check_reminds.start()
        self.process_uwu_queue.start()

    async def cog_load(self):
        await self.bot.db.execute(
            """CREATE TABLE IF NOT EXISTS reminders (
                user_id BIGINT,
                guild_id BIGINT,
                channel_id BIGINT,
                reminder TEXT,
                time TIMESTAMP
            );"""
        )

    def cog_unload(self):
        self.check_reminds.cancel()
        self.process_uwu_queue.cancel()

    @tasks.loop(seconds=7200)
    async def revive_task(self):
        """Repeatedly call send_message for all guilds with enabled revive tasks."""
        for guild_id in self.revive_loops:
            guild = self.bot.get_guild(guild_id)
            if guild:
                await self.send_message(guild)

    async def notify_owner(self, ctx: Context, command_name: str):
        """Notify the server owner that a command was used."""
        server_owner = ctx.guild.owner
        user = ctx.author

        if not server_owner:
            return

        try:
            embed = discord.Embed(
                title="Command Used Notification",
                description=f"An admin only command (`{command_name}`) was used.",
                color=Colors().information,
            )
            embed.add_field(
                name="User", value=f"{user.mention} ({user.name}#{user.discriminator})"
            )
            embed.add_field(name="User ID", value=user.id)
            embed.set_thumbnail(url=user.avatar.url)
            embed.add_field(name="Command", value=command_name)
            embed.set_footer(
                text=f"Server: {ctx.guild.name} | Server ID: {ctx.guild.id}"
            )

            await server_owner.send(embed=embed)
        except Exception as e:
            await ctx.embed(
                "Could not notify the server owner. Ensure their DMs are open.",
                "denied",
            )

    @tasks.loop(seconds=10)
    async def check_reminds(self):
        try:
            BATCH_SIZE = 10
            total_processed = 0

            while True:
                reminds = await self.bot.db.fetch(
                    "SELECT * FROM reminders WHERE time < $1 LIMIT $2",
                    datetime.utcnow(),
                    BATCH_SIZE,
                )

                if not reminds:
                    break

                for i in range(0, len(reminds), 5):
                    chunk = reminds[i : i + 5]

                    for remind in chunk:
                        try:
                            user = await self.bot.fetch_user(remind["user_id"])
                            channel = self.bot.get_channel(remind["channel_id"])

                            if channel:
                                view = discord.ui.View()
                                view.add_item(
                                    discord.ui.Button(
                                        style=discord.ButtonStyle.gray,
                                        label="reminder set by user",
                                        disabled=True,
                                    )
                                )
                                await channel.send(
                                    f"{user.mention} {remind['reminder']}", view=view
                                )
                                await self.bot.db.execute(
                                    "DELETE FROM reminders WHERE time = $1 AND user_id = $2",
                                    remind["time"],
                                    remind["user_id"],
                                )
                                total_processed += 1

                        except discord.NotFound:
                            await self.bot.db.execute(
                                "DELETE FROM reminders WHERE time = $1 AND user_id = $2",
                                remind["time"],
                                remind["user_id"],
                            )

                    await asyncio.sleep(1)

                if len(reminds) < BATCH_SIZE:
                    break

                await asyncio.sleep(2)

            if total_processed > 0:
                logger.info(f"Processed {total_processed} reminders")

        except Exception as e:
            logger.error(f"Error in check_reminds: {e}")

    def parse_embed_code(self, embed_code: str) -> discord.Embed:
        """Parses the provided embed code into a Discord Embed."""
        embed = discord.Embed()
        field_pattern = r"\$v\{field: ([^&]+) && ([^&]+) && ([^}]+)\}"
        parts = re.split(r"\$v", embed_code)

        for part in parts:
            if part.startswith("{description:"):
                description = re.search(r"{description: ([^}]+)}", part)
                if description:
                    embed.description = description.group(1).strip()

            elif part.startswith("{color:"):
                color = re.search(r"{color: #([0-9a-fA-F]+)}", part)
                if color:
                    embed.color = discord.Color(int(color.group(1), 16))

            elif part.startswith("{author:"):
                author = re.search(r"{author: ([^&]+) && ([^}]+)}", part)
                if author:
                    embed.set_author(
                        name=author.group(1).strip(), icon_url=author.group(2).strip()
                    )

            elif part.startswith("{thumbnail:"):
                thumbnail = re.search(r"{thumbnail: ([^}]+)}", part)
                if thumbnail:
                    embed.set_thumbnail(url=thumbnail.group(1).strip())

            elif "field:" in part:
                fields = re.findall(field_pattern, part)
                for name, value, inline in fields:
                    embed.add_field(
                        name=name.strip(),
                        value=value.strip(),
                        inline=inline.strip().lower() == "true",
                    )

        return embed

    async def send_message(self, guild: discord.Guild):
        """Fetch and send the set message or embed to the configured channel."""
        result = await self.bot.db.fetchrow(
            "SELECT channel_id, message, is_embed FROM revive WHERE guild_id = $1 AND enabled = TRUE",
            guild.id,
        )
        if not result:
            return

        channel_id, message, is_embed = result
        channel = guild.get_channel(channel_id)

        if not channel:
            return

        if is_embed:
            try:
                embed = self.parse_embed_code(message)
                await channel.send(embed=embed)
            except Exception as e:
                logger.info(f"Error sending embed: {e}")
        else:
            await channel.send(message)

    @tasks.loop(seconds=3)
    async def process_uwu_queue(self):
        """Process queued uwu messages every 3 seconds."""
        try:
            for guild_id, messages in self.uwu_queue.items():
                if not messages:
                    continue

                message_data = messages[0]
                try:
                    async with aiohttp.ClientSession() as session:
                        webhook = discord.Webhook.from_url(
                            message_data["webhook_url"], session=session
                        )
                        await webhook.send(
                            content=message_data["content"],
                            username=message_data["username"],
                            avatar_url=message_data["avatar_url"],
                        )
                    self.uwu_queue[guild_id].pop(0)
                except Exception as e:
                    logger.error(f"Error processing uwu message: {e}")
                    self.uwu_queue[guild_id].pop(0)
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error in uwu queue processor: {e}")

    @process_uwu_queue.before_loop
    async def before_uwu_processor(self):
        await self.bot.wait_until_ready()

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listener to transform messages from uwulocked users into uwu-speak."""
        if message.author.bot or not message.guild:
            return

        data = await self.bot.db.fetchrow(
            """SELECT * FROM uwulock WHERE guild_id = $1 AND user_id = $2 AND channel_id = $3""",
            message.guild.id,
            message.author.id,
            message.channel.id,
        )

        if not data:
            return

        if await self.bot.glory_cache.ratelimited(f"uwulock:{message.guild.id}", 5, 3):
            return

        if await self.bot.glory_cache.ratelimited(
            f"uwulock_user:{message.author.id}", 2, 3
        ):
            return

        if await self.bot.glory_cache.ratelimited(
            f"uwulock_channel:{message.channel.id}", 3, 3
        ):
            return

        await message.delete()

        if message.guild.id not in self.uwu_queue:
            self.uwu_queue[message.guild.id] = []

            self.uwu_queue[message.guild.id].append(
                {
                    "webhook_url": data["webhook_url"],
                    "content": self.uwuify(message.content),
                    "username": message.author.display_name,
                    "avatar_url": message.author.display_avatar.url,
                }
            )

    @command(
        name="variables",
        brief="show all embed variables used for the bots embed creator",
        example=",variables",
    )
    async def variables(self, ctx: Context):
        from greed.framework.script import Script

        b = Script("{embed}{description: sup}", user=ctx.author)
        rows = [f"`{k}`" for k in b.replacements.keys()]
        rows.extend([f"`{k}`" for k in ["{timer}", "{ends}", "{prize}"]])
        embed = discord.Embed(title="variables", color=Colors().information)
        await Paginator(ctx, rows, embed=embed).start()

    @command(
        name="afk",
        brief="Set an afk message before going offline",
        example=",afk going to that little girls house",
    )
    async def afk(
        self, ctx: commands.Context, *, status: str = "AFK"
    ) -> discord.Message:
        if self.bot.afks.get(ctx.author.id):
            return await ctx.embed("You are **already afk**", "warned")
        self.bot.afks[ctx.author.id] = {"date": datetime.now(), "status": str(status)}
        return await ctx.embed(
            f"**You're now afk** with the status: `{status[:25]}`", "approved"
        )

    @command()
    async def randomuser(self, ctx):
        logger.info(f"Total members in guild: {len(ctx.guild.members)}")

        members = ctx.guild.members

        human_members = [member for member in members if not member.bot]

        logger.info(f"Total human members (excluding bots): {len(human_members)}")

        if not human_members:
            await ctx.send("No human members found in the server.")
            return

        chosen_member = random.choice(human_members)

        logger.info(f"Chosen user: {chosen_member.name}")

        await ctx.send(f"Randomly selected user: {chosen_member.name}")

    @command(
        name="snipe",
        aliases=["s"],
        example=",snipe 4",
        breif="Retrive a recently deleted message",
    )
    @cooldown(1, 7, BucketType.user)
    async def snipe(self, ctx: Context, index: int = 1):
        if not (
            snipe := await self.bot.snipes.get_entry(
                ctx.channel, type="snipe", index=index
            )
        ):
            return await ctx.embed(
                f"There are **no deleted messages** for {ctx.channel.mention}", "denied"
            )
        total = snipe[1]
        snipe = snipe[0]
        if await self.bot.db.fetch(
            """SELECT * FROM filter_event WHERE guild_id = $1 AND event = $2""",
            ctx.guild.id,
            "snipe",
        ):
            if content := snipe.get("content"):
                if (
                    "discord.gg/" in content.lower()
                    or "discord.com/" in content.lower()
                    or "discordapp.com/" in content.lower()
                ):
                    return await ctx.embed("snipe had **filtered content**", "denied")
                content = "".join(c for c in content if c.isalnum() or c.isspace())
                if (
                    "discord.gg" in content.lower()
                    or "discord.com/" in content.lower()
                    or "discordapp.com" in content.lower()
                ):
                    return await ctx.embed("snipe had **filtered content**", "denied")
                for keyword in self.bot.cache.filter.get(ctx.guild.id, []):
                    if keyword.lower() in content.lower():
                        return await ctx.embed(
                            "snipe had **filtered content**", "denied"
                        )
        embed = discord.Embed(
            color=Colors().information,
            description=(
                snipe.get("content")
                or (
                    snipe["embeds"][0].get("description") if snipe.get("embeds") else ""
                )
            ),
            timestamp=datetime.fromtimestamp(snipe.get("timestamp")),
        )

        embed.set_author(
            name=snipe.get("author").get("name"),
            icon_url=snipe.get("author").get("avatar"),
        )

        if att := snipe.get("attachments"):
            embed.set_image(url=att[0])

        elif sticks := snipe.get("stickers"):
            embed.set_image(url=sticks[0])

        embed.set_footer(
            text=f"Deleted {arrow.get(snipe.get('timestamp')).humanize()} | {index}/{total}"
        )

        return await ctx.send(embed=embed)

    @command(
        name="editsnipe",
        aliases=["es"],
        example=",editsnipe 2",
        brief="Retrieve a messages original text before edited",
    )
    @cooldown(1, 7, BucketType.user)
    async def editsnipe(self, ctx: Context, index: int = 1):
        if not (
            snipe := await self.bot.snipes.get_entry(
                ctx.channel, type="editsnipe", index=index
            )
        ):
            return await ctx.embed("There is nothing to snipe.", "denied")
        total = snipe[1]
        snipe = snipe[0]
        if await self.bot.db.fetch(
            """SELECT * FROM filter_event WHERE guild_id = $1 AND event = $2""",
            ctx.guild.id,
            "snipe",
        ):
            if content := snipe.get("content"):
                if (
                    "discord.gg/" in content.lower()
                    or "discord.com/" in content.lower()
                    or "discordapp.com/" in content.lower()
                ):
                    return await ctx.embed("snipe had **filtered content**", "denied")
                content = "".join(c for c in content if c.isalnum() or c.isspace())
                if (
                    "discord.gg" in content.lower()
                    or "discord.com/" in content.lower()
                    or "discordapp.com" in content.lower()
                ):
                    return await ctx.embed("snipe had **filtered content**", "denied")
                for keyword in self.bot.cache.filter.get(ctx.guild.id, []):
                    if keyword.lower() in content.lower():
                        return await ctx.embed(
                            "editsnipe had **filtered content**", "denied"
                        )
        embed = discord.Embed(
            color=Colors().information,
            description=(
                snipe.get("content")
                or ("Message contains an embed" if snipe.get("embeds") else "")
            ),
            timestamp=datetime.fromtimestamp(snipe.get("timestamp")),
        )

        embed.set_author(
            name=snipe.get("author").get("name"),
            icon_url=snipe.get("author").get("avatar"),
        )

        if att := snipe.get("attachments"):
            embed.set_image(url=att[0])

        elif sticks := snipe.get("stickers"):
            embed.set_image(url=sticks[0])

        embed.set_footer(
            text=f"Edited {arrow.get(snipe.get('timestamp')).humanize()} | {index}/{total}",
            icon_url=ctx.author.display_avatar,
        )

        return await ctx.send(embed=embed)

    @command(
        name="reactionsnipe",
        aliases=["reactsnipe", "rs"],
        brief="Retrieve a deleted reaction from a message",
        example=",reactionsipe 2",
    )
    @cooldown(1, 7, BucketType.user)
    async def reactionsnipe(self, ctx: Context, index: int = 1):
        if not (
            snipe := await self.bot.snipes.get_entry(
                ctx.channel, type="reactionsnipe", index=index
            )
        ):
            return await ctx.embed("There is nothing to snipe.", "denied")
        snipe[1]
        snipe = snipe[0]
        embed = discord.Embed(
            color=Colors().information,
            description=(
                f"""**{str(snipe.get('author').get('name'))}** reacted with {snipe.get('reaction')
                if not snipe.get('reaction').startswith('https://cdn.discordapp.com/')
                else str(snipe.get('reaction'))} <t:{int(snipe.get('timestamp'))}:R>"""
            ),
        )

        return await ctx.send(embed=embed)

    @command(
        name="clearsnipe",
        aliases=["cs"],
        brief="Clear all deleted messages from greed",
        example=",clearsnipe",
    )
    @cooldown(1, 7, BucketType.user)
    @has_permissions(manage_messages=True)
    async def clearsnipes(self, ctx: Context):
        await self.bot.snipes.clear_entries(ctx.channel)
        return await ctx.embed(
            f"**Cleared** snipes for {ctx.channel.mention}", "approved"
        )

    @group(
        name="birthday",
        aliases=["bday"],
        brief="get a user's birthday or set your own",
        example=",bday @aiohttp",
        usage=",bday {member}",
    )
    async def birthday(self, ctx, *, member: typing.Optional[discord.Member]):
        if ctx.invoked_subcommand is None:
            if not member:
                mem = "your"
                member = ctx.author
            else:
                mem = f"{member.mention}'s"
            date = await self.bot.db.fetchval(
                """SELECT ts FROM birthday WHERE user_id = $1""", member.id
            )
            if date:
                try:
                    now = arrow.now()
                    birthday_date = arrow.get(date)

                    if (
                        now.month == birthday_date.month
                        and now.day == birthday_date.day
                    ):
                        await ctx.send(
                            embed=discord.Embed(
                                color=self.color,
                                description=f"🎂 {mem} birthday is **today**",
                            )
                        )
                        return

                    if "ago" in arrow.get(date).humanize(granularity="day"):
                        date = arrow.get(date).shift(years=1)
                    else:
                        date = date
                    if arrow.get(date).humanize(granularity="day") == "in 0 days":
                        now = arrow.now()
                        d = arrow.get(date).humanize(now)
                        date = d
                    else:
                        date = arrow.get(
                            (arrow.get(date).datetime + timedelta(days=1))
                        ).humanize(granularity="day")
                    await ctx.send(
                        embed=discord.Embed(
                            color=self.color,
                            description=f"🎂 {mem} birthday is **{date}**",
                        )
                    )
                except Exception:
                    await ctx.send(
                        embed=discord.Embed(
                            color=self.color,
                            description=f"🎂 {mem} birthday is **today**",
                        )
                    )
            else:
                await ctx.embed(
                    f"{mem} birthday is not set, set it using `{ctx.prefix}bday set`",
                    "denied",
                )

    @birthday.command(
        name="set",
        brief="set your birthday",
        usage=",birthday set {month} {day}",
        example=",birthday set August 10",
    )
    async def birthday_set(self, ctx, month: str, day: Optional[str]):
        if "/" in month:
            month, day = month.split("/")[0:2]
        try:
            if len(month) == 1:
                mn = "M"
            elif len(month) == 2:
                mn = "MM"
            elif len(month) == 3:
                mn = "MMM"
            else:
                mn = "MMMM"
            if "th" in day:
                day = day.replace("th", "")
            if "st" in day:
                day = day.replace("st", "")
            if len(day) == 1:
                dday = "D"
            else:
                dday = "DD"
            datee = arrow.now().date()
            ts = f"{month} {day} {datee.year}"
            if "ago" in arrow.get(ts, f"{mn} {dday} YYYY").humanize(granularity="day"):
                year = datee.year + 1
            else:
                year = datee.year
            string = f"{month} {day} {year}"
            date = (
                arrow.get(string, f"{mn} {dday} YYYY")
                .replace(tzinfo="America/New_York")
                .to("UTC")
                .datetime
            )
            await self.bot.db.execute(
                """INSERT INTO birthday (user_id, ts) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET ts = excluded.ts""",
                ctx.author.id,
                date,
            )
            await ctx.embed(f"set your birthday as `{month}` `{day}`", "approved")
        except Exception as e:
            if ctx.author.name == "aiohttp":
                raise e
            return await ctx.embed(
                f"please use this format `,birthday set <month> <day>` \n {e}", "denied"
            )

    @birthday.command(
        name="reset", brief="Clear your set birthday", example="birthday reset"
    )
    async def birthday_clear(self, ctx: Context):
        bday = await self.bot.db.fetchval(
            "SELECT ts FROM birthday WHERE user_id = $1;", ctx.author.id
        )
        if not bday:
            return await ctx.embed(
                "You **don't have a birthday** set to clear", "denied"
            )

        await self.bot.db.execute(
            "DELETE FROM birthday WHERE user_id = $1;",
            ctx.author.id,
        )
        return await ctx.embed("**reset** your **birthday settings**", "approved")

    @command(
        name="selfpurge",
        example=",selfpurge 100",
        brief="Clear your messages from a chat",
    )
    @cooldown(1, 7, BucketType.user)
    @bot_has_permissions(manage_messages=True)
    async def selfpurge(self, ctx, amount: int):
        amount = amount + 1

        try:
            is_donator = await self.bot.db.fetchrow(
                """SELECT * FROM boosters WHERE user_id = $1""", ctx.author.id
            )
        except Exception as e:
            return await ctx.send(
                f"An error occurred while checking donator status: {e}"
            )

        if not is_donator and amount > 0:
            return await ctx.embed(
                "This command is only available to boosters & donators.", "denied"
            )

        def check(message):
            return message.author == ctx.message.author

        await ctx.message.delete()

        deleted_messages = await ctx.channel.purge(limit=amount, check=check)

        if len(deleted_messages) > amount:
            deleted_messages = deleted_messages[:amount]

        await ctx.embed(
            f"Purged {len(deleted_messages)} of your messages.",
            "approved",
            delete_after=5,
        )

    async def check_role(self, ctx, role: discord.Role):
        if (
            ctx.author.top_role.position <= role.position
            and not ctx.author.id == ctx.guild.owner_id
        ):
            await ctx.embed("Your role isn't higher than that role.", "denied")
            return False
        return True

    @command(
        name="imageonly",
        brief="Toggle image only mode in a channel",
        aliases=["imgonly"],
    )
    @has_permissions(manage_messages=True)
    async def imageonly(self, ctx: Context):
        if await self.bot.db.fetchval(
            "SELECT * FROM imageonly WHERE channel_id = $1", ctx.channel.id
        ):
            await self.bot.db.execute(
                "DELETE FROM imageonly WHERE channel_id = $1", ctx.channel.id
            )
            return await ctx.embed("Disabled image only mode", "approved")
        await self.bot.db.execute(
            "INSERT INTO imageonly (channel_id) VALUES($1)", ctx.channel.id
        )
        return await ctx.embed("Enabled image only mode", "approved")

    @command(name="enlarge", aliases=["downloademoji", "e", "jumbo"])
    async def enlarge(self, ctx, emoji: Union[discord.PartialEmoji, str] = None):
        """
        Get an image version of a custom server emoji
        """
        if not emoji:
            return await ctx.embed("Please provide an emoji to enlarge", "denied")

        if isinstance(emoji, PartialEmoji):
            return await ctx.reply(
                file=await emoji.to_file(
                    filename=f"{emoji.name}{'.gif' if emoji.animated else '.png'}"
                )
            )

        elif isinstance(emoji, str):
            if not emoji.startswith("<"):
                return await ctx.embed(
                    "You can only enlarge custom server emojis", "denied"
                )

            try:
                name = emoji.split(":")[1]
                emoji_id = emoji.split(":")[2][:-1]

                if emoji.startswith("<a:"):
                    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.gif"
                    name += ".gif"
                else:
                    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
                    name += ".png"

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            return await ctx.embed(
                                "Could not download that emoji", "denied"
                            )
                        img = io.BytesIO(await resp.read())

                return await ctx.send(file=discord.File(img, filename=name))

            except (IndexError, KeyError):
                return await ctx.embed(
                    "That doesn't appear to be a valid custom emoji", "denied"
                )

    @group(
        name="reminder",
        aliases=["remind"],
        brief="Set a reminder for a specific time",
    )
    async def reminder(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @reminder.command(
        name="add",
        brief="Add a reminder",
        example=",reminder add 5m take out the trash",
    )
    async def reminder_add(self, ctx: Context, time: str, *, reminder: str):
        """
        Add a reminder for a specific time
        """
        import humanfriendly as hf

        try:
            delta = hf.parse_timespan(time)
            reminder_time = datetime.utcnow() + timedelta(seconds=delta)
            if delta <= 0:
                return await ctx.embed(
                    "Please provide a valid time in the future", "denied"
                )
        except Exception:
            return await ctx.embed("Please provide a valid time", "denied")

        await self.bot.db.execute(
            "INSERT INTO reminders (user_id, guild_id, channel_id, reminder, time) VALUES ($1, $2, $3, $4, $5)",
            ctx.author.id,
            ctx.guild.id,
            ctx.channel.id,
            reminder,
            reminder_time,
        )

        await ctx.embed(
            f"Reminder set for {arrow.get(reminder_time).humanize()}", "approved"
        )

    @reminder.command(
        name="list", brief="List all your reminders", example=",reminder list"
    )
    async def reminder_list(self, ctx: Context):
        """
        List all your reminders
        """
        reminders = await self.bot.db.fetch(
            "SELECT * FROM reminders WHERE user_id = $1", ctx.author.id
        )

        if not reminders:
            return await ctx.embed("You don't have any reminders set", "denied")

        embed = discord.Embed(
            title="Reminders",
            color=self.color,
            description="\n".join(
                f"**{i + 1}.** {reminder['reminder']} - {arrow.get(reminder['time']).humanize()}"
                for i, reminder in enumerate(reminders)
            ),
        )

        await ctx.send(embed=embed)

    @reminder.command(
        name="remove",
        aliases=["delete"],
        brief="Remove a reminder",
        example=",reminder remove 1",
    )
    async def reminder_remove(self, ctx: Context, index: int):
        """
        Remove a reminder by its index
        """
        reminders = await self.bot.db.fetch(
            "SELECT * FROM reminders WHERE user_id = $1", ctx.author.id
        )

        if not reminders:
            return await ctx.embed("You don't have any reminders set", "denied")

        try:
            reminder = reminders[index - 1]
        except IndexError:
            return await ctx.embed("Invalid reminder index", "denied")

        await self.bot.db.execute(
            "DELETE FROM reminders WHERE user_id = $1 AND time = $2",
            ctx.author.id,
            reminder["time"],
        )

        await ctx.embed("Reminder removed", "approved")

    @group(name="revive", invoke_without_command=True)
    async def revive_group(self, ctx):
        """Command group for revive-related commands.

        Use this command to manage the revive feature with its subcommands.
        """
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.embed(
                "You need `Manage Messages` permission to use this command.", "denied"
            )

    @revive_group.command(
        name="enable", brief="Enable revive for the server.", example=",revive enable"
    )
    async def enable(self, ctx):
        """Enable the revive feature for this server.

        Activates the revive functionality, allowing periodic sending of the configured revive message.
        """
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.embed(
                "You need `Manage Messages` permission to use this command.", "denied"
            )

        guild_id = ctx.guild.id
        await self.bot.db.execute(
            "UPDATE revive SET enabled = TRUE WHERE guild_id = $1", guild_id
        )

        if guild_id not in self.revive_loops:
            self.revive_loops[guild_id] = True
            if not self.revive_task or not self.revive_task.is_running():
                self.revive_task.start()

        await ctx.embed("Revive feature enabled for this server.", "approved")

    @revive_group.command(
        name="disable",
        brief="Disable revive for the server.",
        example=",revive disable",
    )
    async def disable(self, ctx):
        """Disable the revive feature for this server."""
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.embed(
                "You need `Manage Messages` permission to use this command.", "denied"
            )

        guild_id = ctx.guild.id
        await self.bot.db.execute(
            "UPDATE revive SET enabled = FALSE WHERE guild_id = $1", guild_id
        )

        if guild_id in self.revive_loops:
            self.revive_loops[guild_id] = False

        await ctx.embed("Revive feature disabled for this server.", "approved")

    @revive_group.command(
        name="channel",
        brief="Set the revive message channel.",
        example=",revive channel #general",
    )
    async def set_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel where revive messages will be sent."""
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.embed(
                "You need `Manage Messages` permission to use this command.", "denied"
            )

        guild_id = ctx.guild.id
        await self.bot.db.execute(
            "INSERT INTO revive (guild_id, channel_id, enabled) VALUES ($1, $2, FALSE) "
            "ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2",
            guild_id,
            channel.id,
        )
        await ctx.embed(
            f"Revive messages will now be sent in {channel.mention}.", "approved"
        )

    @revive_group.command(
        name="message",
        brief="Set the revive message content.",
        example=",revive message Hello, revive!",
    )
    async def set_message(self, ctx, *, message: str):
        """Set the revive message for this server."""
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.embed(
                "You need `Manage Messages` permission to use this command.", "denied"
            )

        guild_id = ctx.guild.id
        is_embed = "{embed}" in message

        await self.bot.db.execute(
            "INSERT INTO revive (guild_id, message, is_embed) VALUES ($1, $2, $3) "
            "ON CONFLICT (guild_id) DO UPDATE SET message = $2, is_embed = $3",
            guild_id,
            message,
            is_embed,
        )
        await ctx.embed(
            f"Revive message updated. {'Embed mode enabled.' if is_embed else 'Regular message mode set.'}",
            "approved",
        )

    @revive_group.command(
        name="view", brief="View revive message settings.", example=",revive view"
    )
    async def view_message(self, ctx):
        """Show the current revive message configuration, channel, and embed mode."""
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.embed(
                "You need `Manage Messages` permission to use this command.", "denied"
            )

        guild_id = ctx.guild.id
        result = await self.bot.db.fetchrow(
            "SELECT channel_id, message, is_embed FROM revive WHERE guild_id = $1",
            guild_id,
        )

        if not result:
            return await ctx.embed("No revive message configured.", "denied")

        channel_id, message, is_embed = result
        channel = ctx.guild.get_channel(channel_id)

        embed = discord.Embed(title="Revive Message Settings")
        embed.add_field(
            name="Channel",
            value=channel.mention if channel else "Not set",
            inline=False,
        )
        embed.add_field(
            name="Message", value=message if message else "No message set", inline=False
        )
        embed.add_field(
            name="Embed Mode", value="Enabled" if is_embed else "Disabled", inline=False
        )

        await ctx.send(embed=embed)

    @revive_group.command(
        name="send", brief="Send the revive message now.", example=",revive send"
    )
    async def send_revive_message(self, ctx):
        """Manually send the revive message configured for this server."""
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.embed(
                "You need `Manage Messages` permission to use this command.", "denied"
            )

        await ctx.message.delete()
        guild_id = ctx.guild.id
        result = await self.bot.db.fetchrow(
            "SELECT channel_id, message, is_embed FROM revive WHERE guild_id = $1",
            guild_id,
        )

        if not result:
            return

        channel_id, message, is_embed = result
        channel = ctx.guild.get_channel(channel_id)

        if not channel:
            return

        if is_embed:
            try:
                embed = self.parse_embed_code(message)
                await channel.send(embed=embed)
            except Exception as e:
                logger.info(f"Error sending embed: {e}")
        else:
            await channel.send(message)

    @command(
        name="delete_roles",
        brief="Delete all roles in the server.",
        aliases=["delroles"],
    )
    @has_permissions(administrator=True)
    async def delete_roles(self, ctx):
        """
        Deletes all roles in the server except @everyone and other community system roles.
        """
        await self.notify_owner(ctx, "delete_roles")

        await ctx.embed(
            "Are you sure you want to **delete all roles?** Type `yes` to confirm.",
            "warned",
        )

        def check(m):
            return m.author == ctx.author and m.content.lower() == "yes"

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
            await ctx.embed("Deleting roles... This may take some time.", "approved")
            roles_deleted = 0

            for role in ctx.guild.roles:
                if role.is_default():
                    continue
                try:
                    await role.delete()
                    roles_deleted += 1
                    await sleep(2)
                except discord.Forbidden:
                    await ctx.embed(
                        f"Unable to delete role `{role.name}`. Insufficient permissions.",
                        "denied",
                    )
                except discord.HTTPException as e:
                    await ctx.embed(
                        f"An error occurred while deleting `{role.name}`: {e}", "denied"
                    )

            await ctx.embed(
                f"Roles deletion complete. Total roles deleted: {roles_deleted}",
                "approved",
            )
        except Exception as e:
            await ctx.embed(f"Operation cancelled or unexpected error: {e}", "denied")

    @command(
        name="delete_channels",
        brief="Delete all channels in the server.",
        aliases=["delchannels"],
    )
    @has_permissions(administrator=True)
    async def delete_channels(self, ctx):
        """
        Deletes all channels in the server except community-set channels (system channels).
        """
        await self.notify_owner(ctx, "delete_channels")

        await ctx.embed(
            "Are you sure you want to delete all channels? Type `yes` to confirm.",
            "warned",
        )

        def check(m):
            return m.author == ctx.author and m.content.lower() == "yes"

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
            await ctx.embed("Deleting channels... This may take some time.", "approved")
            channels_deleted = 0

            for channel in ctx.guild.channels:
                if not channel.is_system_channel:
                    try:
                        await channel.delete()
                        channels_deleted += 1
                        await sleep(2)
                    except discord.Forbidden:
                        await ctx.embed(
                            f"Unable to delete channel `{channel.name}`. Insufficient permissions.",
                            "denied",
                        )
                    except discord.HTTPException as e:
                        await ctx.embed(
                            f"An error occurred while deleting `{channel.name}`: {e}",
                            "denied",
                        )

            await ctx.embed(
                f"Channels deletion complete. Total channels deleted: {channels_deleted}",
                "approved",
            )
        except Exception as e:
            await ctx.embed(f"Operation cancelled or unexpected error: {e}", "denied")

    @command(
        name="copyembed",
        aliases=["cembed"],
        brief="Convert an embed to parser format",
        example=",copyembed https://discord.com/channels/...",
    )
    async def copyembed(self, ctx: Context, message_link: Optional[str] = None):
        if message_link:
            try:
                _, channel_id, message_id = message_link.split("/")[-3:]
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    return await ctx.embed("Could not find the channel", "denied")
                message = await channel.fetch_message(int(message_id))
            except:
                return await ctx.embed("Invalid message link provided", "denied")
        else:
            ref = ctx.message.reference
            if not ref or not ref.message_id:
                return await ctx.embed(
                    "Please reply to a message or provide a message link", "denied"
                )
            message = await ctx.channel.fetch_message(ref.message_id)

        if not message.embeds:
            return await ctx.embed("This message doesn't contain any embeds", "denied")

        embed = message.embeds[0]
        parts = ["{embed}"]

        content = message.content
        if content:
            parts.append(f"{{content: {content}}}")

        if embed.title:
            parts.append(f"{{title: {embed.title}}}")

        if embed.description:
            parts.append(f"{{description: {embed.description}}}")

        if embed.color:
            parts.append(f"{{color: #{embed.color.value:06x}}}")

        if embed.author:
            author_parts = [embed.author.name]
            if embed.author.url:
                author_parts.append(embed.author.url)
            if embed.author.icon_url:
                author_parts.append(embed.author.icon_url)
            parts.append(f"{{author: {' && '.join(author_parts)}}}")

        if embed.footer:
            footer_parts = [embed.footer.text]
            if embed.footer.icon_url:
                footer_parts.append(embed.footer.icon_url)
            parts.append(f"{{footer: {' && '.join(footer_parts)}}}")

        if embed.thumbnail:
            parts.append(f"{{thumbnail: {embed.thumbnail.url}}}")

        if embed.image:
            parts.append(f"{{image: {embed.image.url}}}")

        for field in embed.fields:
            parts.append(
                f"{{field: {field.name} && {field.value} && {str(field.inline)}}}"
            )

        result = "$v".join(parts)

        if len(result) > 2000:
            file = discord.File(io.BytesIO(result.encode()), filename="embed.txt")
            await ctx.send(
                "The embed code is too long to send as a message.", file=file
            )
        else:
            await ctx.send(f"```{result}```")

    @command(
        name="calculate",
        aliases=["calc"],
        brief="calculate an equation",
        example=",calc 1+1",
    )
    async def calculator(self, ctx, *, equation: str = None):
        """Solves any mathematical problem and provides an explanation. If no input is given, generates a random math problem."""
        try:
            x = sp.symbols("x")

            equation = equation.replace("^", "**")

            if "=" in equation:
                lhs, rhs = equation.split("=")
                lhs = sp.sympify(lhs.strip())
                rhs = sp.sympify(rhs.strip())
                solution = sp.solve(lhs - rhs, x)
                explanation = f"Solving **{equation}**, we get: **{solution}**"

            elif "d/dx" in equation:
                expr = equation.replace("d/dx", "").strip()
                expr = sp.sympify(expr)
                result = sp.diff(expr, x)
                explanation = f"The derivative of **{expr}** is: **{result}**"

            elif "∫" in equation or "integrate" in equation.lower():
                expr = equation.replace("∫", "").replace("integrate", "").strip()
                expr = sp.sympify(expr)
                result = sp.integrate(expr, x)
                explanation = f"The integral of **{expr}** is: **{result}** + C"

            elif "lim" in equation:
                parts = equation.split("->")
                if len(parts) == 2:
                    expr, val = parts[0].replace("lim", "").strip(), parts[1].strip()
                    expr = sp.sympify(expr)
                    limit_value = sp.limit(expr, x, float(val))
                    explanation = f"The limit of **{expr}** as x approaches **{val}** is: **{limit_value}**"
                else:
                    raise ValueError("Invalid limit format. Use 'lim f(x) -> value'.")

            elif "log" in equation:
                expr = sp.sympify(equation)
                result = sp.simplify(expr)
                explanation = f"The simplified logarithmic expression is: **{result}**"

            else:
                result = sp.sympify(equation)
                if result.is_real:
                    if result == int(result):
                        result = int(result)
                    else:
                        result = float(result)
                explanation = f"The result of **{equation}** is: **{result}**"

            await ctx.embed(explanation, "approved")
        except Exception as e:
            await ctx.embed(
                f"{e}. Ensure your equation is **correctly formatted!**", "denied"
            )

    def generate_math_problem(self):
        """Generates a random math problem from basic to advanced levels, including fractions."""
        difficulty = random.choice(["easy", "medium", "hard", "college"])
        if difficulty == "easy":
            a, b = random.randint(1, 10), random.randint(1, 10)
            problem = f"{a} + {b}"
            solution = a + b
        elif difficulty == "medium":
            a, b = random.randint(1, 20), random.randint(1, 20)
            problem = f"{a} / {b}"
            solution = sp.Rational(a, b)
        elif difficulty == "hard":
            a = random.randint(2, 10)
            problem = f"√{a**2}"
            solution = a
        else:
            a = random.randint(1, 5)
            b = random.randint(1, 5)
            problem = f"∫ {a}x^{b} dx"
            x = sp.symbols("x")
            solution = sp.integrate(a * x**b, x)

        if solution == int(solution):
            solution = int(solution)
        else:
            solution = float(solution)

        return problem, solution


async def setup(bot: "Greed") -> None:
    await bot.add_cog(Miscs(bot))
