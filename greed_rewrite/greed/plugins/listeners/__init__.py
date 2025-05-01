import discord
from discord.ext import commands, tasks
import asyncio
from contextlib import suppress
import logging
from typing import Optional, Dict, Tuple, Any, Union
from functools import wraps
import re
from collections import defaultdict
from datetime import datetime
from greed.shared.config import Colors
import random
from greed.framework.script import Script

logger = logging.getLogger("greed/plugins/listeners")


def ratelimit(key: str, amount: int, time: int, wait: bool = True):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if wait and (
                delay := await self.bot.glory_cache.ratelimited(
                    key.format(*args, **kwargs), amount, time
                )
            ):
                await asyncio.sleep(delay)
            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


class Listeners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voicemaster_clear.start()
        self.word_batch: Dict[int, Dict[str, Dict[int, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        self.batch_lock = asyncio.Lock()
        self.processing_task: Optional[asyncio.Task] = None
        self.word_pattern = re.compile(r"\b\w+\b")
        self._level_settings_cache: Dict[int, Dict] = {}

    async def get_level_settings(self, guild_id: int) -> Dict:
        cache_key = f"levels:settings:{guild_id}"
        if cached := await self.bot.redis.get(cache_key):
            return cached

        data = await self.bot.db.fetchrow(
            """SELECT * FROM text_level_settings WHERE guild_id = $1""",
            guild_id,
        )
        settings = dict(data) if data else {"roles": [], "award_message": {}}
        await self.bot.redis.set(cache_key, settings, ex=3600)
        return settings

    async def get_user_levels(self, guild_id: int, user_id: int) -> Tuple[int, int]:
        cache_key = f"levels:user:{guild_id}:{user_id}"
        if cached := await self.bot.redis.get(cache_key):
            return tuple(map(int, cached.split(":")))

        text_data = await self.bot.db.fetchrow(
            """SELECT xp, msgs FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
            guild_id,
            user_id,
        )
        voice_data = await self.bot.db.fetchrow(
            """SELECT xp, time_spent FROM voice_levels WHERE guild_id = $1 AND user_id = $2""",
            guild_id,
            user_id,
        )

        text_xp = text_data["xp"] if text_data else 0
        voice_xp = voice_data["xp"] if voice_data else 0
        total_xp = text_xp + voice_xp

        await self.bot.redis.set(cache_key, f"{total_xp}:{text_xp}:{voice_xp}", ex=300)
        return total_xp, text_xp, voice_xp

    @commands.Cog.listener("on_text_level_up")
    @ratelimit("level_up:{0.id}:{1.id}", 1, 5)
    async def on_level_up(
        self, guild: discord.Guild, member: discord.Member, level: int
    ):
        try:
            settings = await self.get_level_settings(guild.id)
            total_xp, text_xp, voice_xp = await self.get_user_levels(
                guild.id, member.id
            )

            roles = settings.get("roles", [])
            for role_level, role_id in roles:
                if level >= role_level:
                    if role := guild.get_role(role_id):
                        try:
                            await member.add_roles(role, reason=f"Level {level} role")
                        except discord.Forbidden:
                            logger.warning(
                                f"Missing permissions to add role {role_id} in guild {guild.id}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error adding role {role_id} to {member.id}: {e}"
                            )

            award_data = settings.get("award_message", {})
            channel_id = award_data.get("channel_id")
            message = award_data.get("message")

            if not channel_id:
                return

            if channel := guild.get_channel(channel_id):
                if not message:
                    message = f"Congratulations {member.mention}, you have reached level {level}!"
                else:
                    message = message.replace("{level}", str(level))
                    message = message.replace("{user.mention}", member.mention)
                    message = message.replace("{user.name}", member.name)
                    message = message.replace(
                        "{user.discriminator}", member.discriminator
                    )
                    message = message.replace("{total_xp}", str(total_xp))
                    message = message.replace("{text_xp}", str(text_xp))
                    message = message.replace("{voice_xp}", str(voice_xp))

                try:
                    await self.bot.send_embed(channel, message, user=member)
                except discord.Forbidden:
                    logger.warning(
                        f"Missing permissions to send message in channel {channel_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error sending level up message in guild {guild.id}: {e}"
                    )

        except Exception as e:
            logger.error(f"Error in level up handler for guild {guild.id}: {e}")

    async def cog_unload(self):
        self.voicemaster_clear.cancel()
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.id in (self.bot.user.id, 123):
            return

        if not message.guild:
            return

        if not message.channel.permissions_for(message.guild.me).view_channel:
            return

        await self.bot.snipes.add_entry("snipe", message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content == after.content or before.author.id == self.bot.user.id:
            return

        if not before.guild:
            return

        if not before.channel.permissions_for(before.guild.me).view_channel:
            return

        await self.bot.snipes.add_entry("editsnipe", before)

        if before.author.bot:
            return

        ctx = await self.bot.get_context(after)
        if ctx.valid:
            return

        return await self.on_message_filter(after)

    @tasks.loop(minutes=5)
    async def voicemaster_clear(self):
        """Clean up empty voice master channels periodically."""
        try:
            if await self.bot.glory_cache.ratelimited("voicemaster_clear", 1, 10):
                return

            rows = await self.bot.db.fetch(
                """SELECT guild_id, channel_id FROM voicemaster_data"""
            )

            for batch in [rows[i : i + 10] for i in range(0, len(rows), 10)]:
                delete_tasks = []

                for row in batch:
                    if guild := self.bot.get_guild(row["guild_id"]):
                        if channel := guild.get_channel(row["channel_id"]):
                            active_members = [m for m in channel.members if not m.bot]
                            if not active_members:
                                delete_tasks.append(
                                    self._delete_channel(channel, row["channel_id"])
                                )

                if delete_tasks:
                    await asyncio.gather(*delete_tasks, return_exceptions=True)

                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in voicemaster_clear: {str(e)}")

    async def _delete_channel(self, channel: discord.VoiceChannel, channel_id: int):
        with suppress(
            discord.NotFound, discord.Forbidden, commands.BotMissingPermissions
        ):
            await channel.delete(reason="Voice master cleanup - channel empty")

        await self.bot.db.execute(
            """DELETE FROM voicemaster_data WHERE channel_id = $1""", channel_id
        )

        logger.debug(f"Cleaned up empty voice channel {channel_id}")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        return await self.voicemaster_event(member, before, after)

    @ratelimit("voicemaster_guild:{member.guild.id}", 3, 5, False)
    async def create_and_move(
        self,
        member: discord.Member,
        after: discord.VoiceState,
        status: Optional[str] = None,
    ):
        guild_rl = await self.bot.glory_cache.ratelimited(
            f"voicemaster_guild:{member.guild.id}", 5, 10
        )
        user_rl = await self.bot.glory_cache.ratelimited(
            f"voicemaster_move:{member.id}", 5, 10
        )

        if guild_rl > 0:
            await asyncio.sleep(guild_rl)
            return None

        if user_rl > 0:
            await asyncio.sleep(user_rl)
            return None

        try:
            overwrites = {
                member: discord.PermissionOverwrite(connect=True, view_channel=True)
            }
            channel = await member.guild.create_voice_channel(
                name=f"{member.name}'s channel",
                user_limit=0,
                category=after.channel.category,
                overwrites=overwrites,
            )
            if status:
                await channel.edit(status=status)
            await asyncio.sleep(0.3)
            try:
                await member.move_to(channel)
            except Exception:
                with suppress(discord.errors.NotFound):
                    await channel.delete()
                return None
            return channel
        except Exception:
            return None

    async def voicemaster_event(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if (
            await self.bot.glory_cache.ratelimited(f"vm_event:{member.guild.id}", 20, 5)
            == 0
        ):
            if self.bot.is_ready() and not (
                before.channel
                and after.channel
                and before.channel.id == after.channel.id
            ):
                if data := await self.bot.db.fetchrow(
                    """
                    SELECT voicechannel_id, category_id
                    FROM voicemaster
                    WHERE guild_id = $1
                    """,
                    member.guild.id,
                ):
                    join_chanel = data["voicechannel_id"]
                    data["category_id"]
                    if after.channel and after.channel.id == join_chanel:
                        if await self.bot.glory_cache.ratelimited(
                            f"rl:voicemaster_channel_create:{member.guild.id}", 15, 30
                        ):
                            if (
                                before.channel
                                and before.channel != join_chanel
                                and len(before.channel.members) == 0
                                and await self.bot.db.fetchrow(
                                    "SELECT * FROM voicemaster_data WHERE channel_id = $1",
                                    before.channel.id,
                                )
                            ):
                                await self.bot.db.execute(
                                    """
                                    DELETE FROM voicemaster_data
                                    WHERE channel_id = $1
                                    """,
                                    before.channel.id,
                                )
                                with suppress(discord.errors.NotFound):
                                    await before.channel.delete()

                        else:
                            status = None
                            if stat := await self.bot.db.fetchrow(
                                """SELECT status FROM vm_status WHERE user_id = $1""",
                                member.id,
                            ):
                                status = stat["status"]
                            channel = await self.create_and_move(member, after, status)
                            if channel is not None:
                                await self.bot.db.execute(
                                    """
                                    INSERT INTO voicemaster_data
                                    (channel_id, guild_id, owner_id)
                                    VALUES ($1, $2, $3)
                                    """,
                                    channel.id,
                                    channel.guild.id,
                                    member.id,
                                )

                            if (
                                before.channel
                                and before.channel != join_chanel
                                and len(before.channel.members) == 0
                                and await self.bot.db.fetchrow(
                                    "SELECT * FROM voicemaster_data WHERE channel_id = $1",
                                    before.channel.id,
                                )
                            ):
                                await self.bot.db.execute(
                                    """
                                    DELETE FROM voicemaster_data
                                    WHERE channel_id = $1
                                    """,
                                    before.channel.id,
                                )
                                with suppress(discord.errors.NotFound):
                                    await before.channel.delete()

                    elif before and before.channel:
                        voice = await self.bot.db.fetchval(
                            """
                            SELECT channel_id
                            FROM voicemaster_data
                            WHERE channel_id = $1
                            """,
                            before.channel.id,
                        )
                        if len(before.channel.members) == 0 and voice:
                            if before.channel.id == voice:
                                await self.bot.db.execute(
                                    """
                                    DELETE FROM voicemaster_data
                                    WHERE channel_id = $1
                                    """,
                                    before.channel.id,
                                )
                                with suppress(discord.errors.NotFound):
                                    await before.channel.delete()
                            elif before.channel.id == data:
                                await asyncio.sleep(5)
                                voice = await self.bot.db.fetchval(
                                    """
                                    SELECT channel_id
                                    FROM voicemaster_data
                                    WHERE owner_id = $1
                                    """,
                                    member.id,
                                )
                                if before.channel.id == voice:
                                    await self.bot.db.execute(
                                        """
                                        DELETE FROM voicemaster_data
                                        WHERE owner_id = $1
                                        """,
                                        member.id,
                                    )
                                    with suppress(discord.errors.NotFound):
                                        await before.channel.delete()

    async def _process_word_batch(self):
        while True:
            try:
                await asyncio.sleep(5)
                async with self.batch_lock:
                    if not self.word_batch:
                        continue

                    values = []
                    for guild_id, guild_words in self.word_batch.items():
                        for word, user_counts in guild_words.items():
                            for user_id, count in user_counts.items():
                                values.append((guild_id, user_id, word, count))

                    if values:
                        await self.bot.db.executemany(
                            """
                            INSERT INTO stats.word_usage (guild_id, user_id, word, count, last_used)
                            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                            ON CONFLICT (guild_id, user_id, word) 
                            DO UPDATE SET 
                                count = stats.word_usage.count + EXCLUDED.count,
                                last_used = CURRENT_TIMESTAMP
                            """,
                            values,
                        )

                    self.word_batch.clear()

            except Exception as e:
                self.bot.logger.error(f"Error processing word batch: {e}")

    async def get_xp(self, guild_id: int, user_id: int) -> int:
        cache_key = f"levels:xp:{guild_id}:{user_id}"
        if cached := await self.bot.redis.get(cache_key):
            return int(cached)

        xp = await self.bot.db.fetchval(
            """SELECT xp FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
            guild_id,
            user_id,
        )
        xp = xp or 0
        await self.bot.redis.set(cache_key, xp, ex=300)
        return xp

    async def add_xp(self, guild_id: int, user_id: int, amount: int) -> None:
        current_xp = await self.get_xp(guild_id, user_id)
        new_xp = current_xp + amount

        await self.bot.db.execute(
            """INSERT INTO text_levels (guild_id, user_id, xp) VALUES($1, $2, $3)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp""",
            guild_id,
            user_id,
            new_xp,
        )

        cache_key = f"levels:xp:{guild_id}:{user_id}"
        await self.bot.redis.set(cache_key, new_xp, ex=300)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        context = await self.bot.get_context(message)

        if message.guild and not context.valid:
            try:
                if await self.bot.glory_cache.ratelimited(
                    f"text_level:{message.author.id}:{message.guild.id}", 1, 60
                ):
                    return

                settings = await self.get_level_settings(message.guild.id)
                if not settings:
                    return

                current_xp = await self.get_xp(message.guild.id, message.author.id)
                xp_gain = random.randint(15, 25)
                new_xp = current_xp + xp_gain

                current_level = 0
                new_level = 0
                for level in range(1, 101):
                    xp_required = 5 * (level**2) + 50 * level + 100
                    if current_xp >= xp_required:
                        current_level = level
                    if new_xp >= xp_required:
                        new_level = level

                await self.add_xp(message.guild.id, message.author.id, xp_gain)

                if new_level > current_level:
                    self.bot.dispatch(
                        "text_level_up", message.guild, message.author, new_level
                    )

            except Exception as e:
                logger.error(f"Error in text leveling: {e}")

        afk_data = self.bot.afks.get(message.author.id)
        if isinstance(afk_data, dict):
            if not context.valid or context.command.qualified_name.lower() != "afk":
                await self.do_afk(message, context, afk_data)

        if message.mentions:
            if not await self.bot.glory_cache.ratelimited(
                f"afk_mentions:{message.guild.id}", 3, 10
            ):
                mention_tasks = []
                processed_users = set()

                for user in message.mentions:
                    if user.id in processed_users:
                        continue
                    processed_users.add(user.id)

                    if user_afk := self.bot.afks.get(user.id):
                        if not await self.bot.glory_cache.ratelimited(
                            f"afk_user:{user.id}", 1, 30
                        ):
                            mention_tasks.append(
                                self.handle_afk_mention(
                                    context, message, user, user_afk
                                )
                            )

                            if len(mention_tasks) >= 3:
                                break

                if mention_tasks:
                    for task in mention_tasks:
                        await task
                        await asyncio.sleep(0.5)

        if not context.valid:
            await self.on_message_filter(message)

    def find_emojis(self, content: str) -> bool:
        emoji_pattern = re.compile(r"<a?:\w+:\d+>|[\U0001F300-\U0001F9FF]")
        return bool(emoji_pattern.search(content))

    async def autoresponder_event(self, message: discord.Message):
        if message.guild is None:
            return
        if message.author.bot:
            return
        try:
            if message.channel.permissions_for(message.guild.me).send_messages is False:
                return
        except discord.errors.ClientException:
            pass

        if (
            await self.bot.glory_cache.ratelimited(
                f"autoresponder_global:{message.guild.id}", 10, 3
            )
            != 0
        ):
            return

        await asyncio.gather(
            self.check_message(message),
            self.handle_autoreacts(message),
        )

    async def check_message(self, message: discord.Message):
        if (
            await self.bot.glory_cache.ratelimited(
                f"check_msg:{message.guild.id}", 1, 1
            )
            != 0
        ):
            return

        try:
            data = self.bot.cache.autoresponders.get(message.guild.id)
            if not data:
                return

            if (
                await self.bot.glory_cache.ratelimited(
                    f"autoresponse_channel:{message.channel.id}", 3, 5
                )
                != 0
            ):
                return

            if (
                await self.bot.glory_cache.ratelimited(
                    f"autoresponse_user:{message.author.id}:{message.guild.id}", 2, 10
                )
                != 0
            ):
                return

            content = message.content.lower()
            for trigger, response_data in data.items():
                if not trigger or not response_data:
                    continue

                response = response_data
                strict_mode = False
                reply_mode = False

                if isinstance(response_data, dict):
                    response = response_data.get("response", "")
                    strict_mode = response_data.get("strict", False)
                    reply_mode = response_data.get("reply", False)

                if not response:
                    continue

                trigger = trigger.lower()
                matched = False

                if trigger.endswith("*"):
                    base = trigger.strip("*")
                    if base in content:
                        matched = True
                elif strict_mode:
                    if content == trigger or content.split() == [trigger]:
                        matched = True
                else:
                    trigger = trigger.strip()
                    if (
                        content.startswith(f"{trigger} ")
                        or content == trigger
                        or f" {trigger} " in content
                        or content.endswith(f" {trigger}")
                        or trigger in content.split()
                        or trigger in content
                    ):
                        matched = True

                if matched:
                    await self.do_autoresponse(trigger, message, reply_mode)
                    break

        except Exception as e:
            logger.error(f"Error in check_message: {e}")

    async def do_autoresponse(
        self, trigger: str, message: discord.Message, reply_mode: bool = False
    ):
        try:
            if (
                await self.bot.glory_cache.ratelimited(
                    f"ar:{message.channel.id}:{trigger}", 1, 1
                )
                != 0
            ):
                return

            if (
                await self.bot.glory_cache.ratelimited(
                    f"ar:{message.guild.id}:{trigger}", 2, 4
                )
                != 0
            ):
                return

            if (
                await self.bot.glory_cache.ratelimited(
                    f"ar_user:{message.author.id}:{trigger}", 1, 15
                )
                != 0
            ):
                return

            response_data = None
            if message.guild.id in self.bot.cache.autoresponders:
                response_data = self.bot.cache.autoresponders[message.guild.id].get(
                    trigger
                )

            response = None
            if isinstance(response_data, dict):
                response = response_data.get("response", "")
                reply_mode = response_data.get("reply", reply_mode)
            else:
                response = response_data

            if not response:
                db_data = await self.bot.db.fetchrow(
                    """SELECT response, strict, reply FROM autoresponder WHERE guild_id = $1 AND trig = $2""",
                    message.guild.id,
                    trigger,
                )
                if db_data:
                    response = db_data["response"]
                    reply_mode = db_data["reply"]

                    if message.guild.id not in self.bot.cache.autoresponders:
                        self.bot.cache.autoresponders[message.guild.id] = {}
                    self.bot.cache.autoresponders[message.guild.id][trigger] = {
                        "response": response,
                        "strict": db_data["strict"],
                        "reply": reply_mode,
                    }

            if not response:
                logger.debug(
                    f"No response found for trigger '{trigger}' in guild {message.guild.id}"
                )
                return

            if response.lower().startswith("{embed}"):
                if reply_mode:
                    await self.bot.send_embed(
                        message.channel,
                        response,
                        user=message.author,
                        reference=message,
                    )
                else:
                    await self.bot.send_embed(
                        message.channel, response, user=message.author
                    )
            else:
                if reply_mode:
                    await message.reply(
                        response,
                        allowed_mentions=discord.AllowedMentions(
                            users=True,
                        ),
                    )
                else:
                    await message.channel.send(
                        response,
                        allowed_mentions=discord.AllowedMentions(
                            users=True,
                        ),
                    )

        except Exception as e:
            logger.error(f"Error in do_autoresponse for trigger '{trigger}': {str(e)}")

    async def handle_autoreacts(self, message: discord.Message):
        if not self.bot.cache.autoreacts.get(message.guild.id):
            return

        if await self.bot.glory_cache.ratelimited(
            f"autoreact_guild:{message.guild.id}", 5, 2
        ):
            return

        try:
            keywords_covered = []

            if await self.bot.glory_cache.ratelimited(
                f"autoreact_channel:{message.channel.id}", 3, 5
            ):
                return

            if await self.bot.glory_cache.ratelimited(
                f"autoreact_user:{message.author.id}", 2, 10
            ):
                return

            for keyword, reactions in self.bot.cache.autoreacts[
                message.guild.id
            ].items():
                if keyword not in ["spoilers", "images", "emojis", "stickers"]:
                    if keyword.lower() in message.content.lower():
                        if await self.bot.glory_cache.ratelimited(
                            f"autoreact:{message.guild.id}:{message.channel.id}:{keyword}",
                            1,
                            3,
                        ):
                            continue
                        await self.add_reaction(message, reactions)
                        keywords_covered.append(keyword)

            event_types = await self.get_event_types(message)
            if not event_types:
                return

            tasks = []
            for event_type in event_types:
                if event_type == "images" and any(
                    attachment.content_type
                    and attachment.content_type.startswith(("image/", "video/"))
                    for attachment in message.attachments
                ):
                    tasks.append(self.add_event_reaction(message, "images"))

                elif event_type == "spoilers" and message.content.count("||") >= 2:
                    tasks.append(self.add_event_reaction(message, "spoilers"))

                elif event_type == "emojis" and self.find_emojis(message.content):
                    tasks.append(self.add_event_reaction(message, "emojis"))

                elif event_type == "stickers" and message.stickers:
                    tasks.append(self.add_event_reaction(message, "stickers"))

            if tasks:
                await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"Error in handle_autoreacts: {e}")

    async def add_event_reaction(self, message: discord.Message, event_type: str):
        if await self.bot.glory_cache.ratelimited(
            f"autoreact:{message.guild.id}:{message.channel.id}:{event_type}", 1, 3
        ):
            return

        reactions = self.bot.cache.autoreacts[message.guild.id].get(event_type)
        if reactions:
            await self.add_reaction(message, reactions)

    async def do_afk(
        self, message: discord.Message, context: commands.Context, afk_data: Any
    ):
        if (
            await self.bot.glory_cache.ratelimited(f"afk:{message.author.id}", 1, 1)
            == 0
        ):
            author_afk_since: datetime = afk_data["date"]
            welcome_message = f":wave_tone3: {message.author.mention}: **Welcome back**, you went away {discord.utils.format_dt(author_afk_since, style='R')}"
            embed = discord.Embed(description=welcome_message, color=0x9EAFBF)
            await context.send(embed=embed)

            if message.author.id in self.bot.afks:
                self.bot.afks.pop(message.author.id)
            else:
                logger.error(f"{message.author.id} not found in AFK list.")

    async def revert_slowmode(self, channel: discord.TextChannel):
        await asyncio.sleep(300)
        await channel.edit(slowmode_delay=0, reason="Auto Mod Auto Slow Mode")
        return True

    async def reset_filter(self, guild: discord.Guild):
        tables = [
            """DELETE FROM filter_event WHERE guild_id = $1""",
            """DELETE FROM filter_setup WHERE guild_id = $1""",
        ]
        return await asyncio.gather(
            *[self.bot.db.execute(table, guild.id) for table in tables]
        )

    async def validate_reaction(self, reaction: str) -> bool:
        try:
            if isinstance(reaction, str):
                if reaction.startswith("<") and reaction.endswith(">"):
                    emoji_id = int(reaction.split(":")[-1][:-1])
                    await self.bot.fetch_emoji(emoji_id)
                else:
                    await self.bot.get_emoji(reaction)
            return True
        except (discord.NotFound, ValueError, AttributeError):
            return False

    @commands.Cog.listener("on_guild_join")
    async def handle_guild_join(self, guild: discord.Guild) -> None:
        """
        Handle new guild joins and notify about larger servers joining the network.
        Includes rate limiting and validation checks.
        """
        try:
            if (
                await self.bot.db.fetchval(
                    """SELECT guild_id FROM guild_notifications WHERE guild_id = $1""",
                    guild.id,
                )
                or not hasattr(guild, "member_count")
                or guild.member_count < self.min_member_threshold
            ):
                return

            cache_key = f"guild_stats:{guild.id}"
            stats = await self.bot.redis.get(cache_key)

            if not stats:
                guild_data = {
                    "members": [{"bot": m.bot} for m in guild.members],
                    "member_count": guild.member_count,
                }

                stats = await self.bot.process_data("guild_data", guild_data)
                await self.bot.redis.set(cache_key, stats, ex=300)

            icon_url = guild.icon.url if guild.icon else None
            splash_url = guild.splash.url if guild.splash else None
            banner_url = guild.banner.url if guild.banner else None

            icon = f"[icon]({icon_url})" if icon_url else "N/A"
            splash = f"[splash]({splash_url})" if splash_url else "N/A"
            banner = f"[banner]({banner_url})" if banner_url else "N/A"

            embed = discord.Embed(
                timestamp=datetime.now(),
                description="Greed has joined a guild.",
                color=Colors().information,
            )
            if icon_url:
                embed.set_thumbnail(url=icon_url)
            embed.set_author(name=guild.name)

            fields = {
                "Owner": f"{guild.owner.mention}\n{guild.owner}",
                "Members": (
                    f"**Users:** {stats['user_count']} ({stats['user_percentage']:.2f}%)\n"
                    f"**Bots:** {stats['bot_count']} ({stats['bot_percentage']:.2f}%)\n"
                    f"**Total:** {guild.member_count}"
                ),
                "Information": (
                    f"**Verification:** {guild.verification_level}\n"
                    f"**Boosts:** {guild.premium_subscription_count} (level {guild.premium_tier})\n"
                    f"**Large:** {'yes' if guild.large else 'no'}"
                ),
                "Design": f"{icon}\n{splash}\n{banner}",
                f"Channels ({len(guild.channels)})": (
                    f"**Text:** {len(guild.text_channels)}\n"
                    f"**Voice:** {len(guild.voice_channels)}\n"
                    f"**Categories:** {len(guild.categories)}"
                ),
                "Counts": (
                    f"**Roles:** {len(guild.roles)}/250\n"
                    f"**Emojis:** {len(guild.emojis)}/{guild.emoji_limit * 2}\n"
                    f"**Stickers:** {len(guild.stickers)}/{guild.sticker_limit}"
                ),
            }

            for name, value in fields.items():
                embed.add_field(name=name, value=value)

            embed.set_footer(text=f"Guild ID: {guild.id}")
            if banner_url:
                embed.set_image(url=banner_url)

            view = None
            if guild.vanity_url_code:
                view = discord.ui.View()
                view.add_item(
                    discord.ui.Button(
                        label="Invite",
                        url=f"https://discord.gg/{guild.vanity_url_code}",
                    )
                )

            await self.bot.ipc.send_to_channel(
                guild_id=1301617147964821524,
                channel_id=1302458572981932053,
                embed=embed,
                view=view,
                silent=True,
            )

            await self.bot.db.execute(
                """INSERT INTO guild_notifications (guild_id) VALUES ($1)""", guild.id
            )

        except Exception as e:
            logger.error(
                f"Error handling guild join for {guild.id}: {e}", exc_info=True
            )

    async def check_rolee(self, guild: discord.Guild, role: discord.Role) -> bool:
        if role.position >= guild.me.top_role.position:
            return False
        if role.is_default():
            return False
        if role.is_bot_managed():
            return False
        if role.is_premium_subscriber():
            return False
        return True

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction: discord.RawReactionActionEvent):
        emoji = str(reaction.emoji)
        if roles := await self.bot.db.fetch(
            """SELECT role_id FROM reactionrole WHERE guild_id = $1 AND message_id = $2 AND emoji = $3""",
            reaction.guild_id,
            reaction.message_id,
            emoji,
        ):
            guild = self.bot.get_guild(reaction.guild_id)
            if guild.me.guild_permissions.administrator is False:
                return
        else:
            return

        @ratelimit("rr:{reaction.guild_id}", 3, 5, True)
        async def do(
            reaction: discord.RawReactionActionEvent, roles: Any, guild: discord.Guild
        ):
            for r in roles:
                if role := guild.get_role(r.role_id):
                    if await self.check_rolee(guild, role) is not True:
                        return logger.info("failed rr checks")
                    if member := guild.get_member(reaction.user_id):
                        if await self.bot.glory_cache.ratelimited("rr", 1, 4) != 0:
                            await asyncio.sleep(5)
                        if role in member.roles:
                            return
                        try:
                            await member.add_roles(role)
                        except Exception:
                            await member.add_roles(role)

        return await do(reaction, roles, guild)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, reaction: discord.RawReactionActionEvent):
        emoji = str(reaction.emoji)
        if roles := await self.bot.db.fetch(
            """SELECT role_id FROM reactionrole WHERE guild_id = $1 AND message_id = $2 AND emoji = $3""",
            reaction.guild_id,
            reaction.message_id,
            emoji,
        ):
            guild = self.bot.get_guild(reaction.guild_id)
            if guild.me.guild_permissions.administrator is False:
                return logger.info("failed rr perm checks")
        else:
            return

        @ratelimit("rr:{reaction.guild_id}", 3, 5, True)
        async def do(
            reaction: discord.RawReactionActionEvent, roles: Any, guild: discord.Guild
        ):
            if member := guild.get_member(reaction.user_id):
                if len(member.roles) > 0:
                    member_roles = [r.id for r in member.roles]
                    for role in roles:
                        if r := guild.get_role(role.role_id):
                            if await self.check_rolee(guild, r) is not True:
                                return logger.info("failed rr checks")
                        else:
                            return logger.info("no role lol")
                        if role.role_id in member_roles:
                            if await self.bot.glory_cache.ratelimited("rr", 1, 4) != 0:
                                await asyncio.sleep(5)
                            try:
                                await member.remove_roles(guild.get_role(role.role_id))
                            except Exception:
                                await member.remove_roles(
                                    guild.get_role(role.role_id), reason="RR"
                                )

        return await do(reaction, roles, guild)

    async def handle_afk_mention(
        self,
        context: commands.Context,
        message: discord.Message,
        user: Union[discord.Member, discord.User],
        afk_data: Dict[str, Any],
    ):
        """
        Handle mentions of AFK users and send their AFK status.
        """
        afk_since: datetime = afk_data["date"]
        status: str = afk_data["status"]
        afk_message = f":zzz: {user.mention} is AFK: **{status}** - {discord.utils.format_dt(afk_since, style='R')}"
        embed = discord.Embed(description=afk_message, color=0x9EAFBF)
        await context.send(embed=embed)

    async def on_message_filter(self, message: discord.Message) -> None:
        await self.bot.wait_until_ready()

        if message.author.bot or not message.guild:
            return

        try:
            if isinstance(message.channel, discord.Thread):
                if not message.channel.parent:
                    return
                permissions = message.channel.parent.permissions_for(message.guild.me)
            else:
                permissions = message.channel.permissions_for(message.guild.me)

            if not all(
                [
                    permissions.send_messages,
                    permissions.moderate_members,
                    permissions.manage_messages,
                ]
            ):
                return logger.debug(
                    f"Missing required permissions in {message.channel.id}"
                )

        except (discord.ClientException, AttributeError):
            return

        context = await self.bot.get_context(message)

        db_fetch = self.bot.db.fetch(
            """SELECT event FROM filter_event WHERE guild_id = $1""", context.guild.id
        )
        afk_fetch = asyncio.create_task(
            asyncio.to_thread(lambda: self.bot.afks.get(message.author.id))
        )

        filter_events, afk_data = await asyncio.gather(
            db_fetch, afk_fetch, return_exceptions=True
        )

        filter_events = (
            tuple(record["event"] for record in filter_events)
            if isinstance(filter_events, list)
            else ()
        )

        await self.autoresponder_event(message)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.me.guild_permissions.manage_messages:
            if data := await self.bot.db.fetchrow(
                "SELECT * FROM welcome WHERE guild_id = $1", member.guild.id
            ):
                channel = self.bot.get_channel(data["channel_id"])
                message = data["message"]
                if channel:
                    try:
                        script = Script(message, [member.guild, channel, member])
                        await script.send(channel)
                    except Exception as e:
                        await channel.send(f"fix your welcome message: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if data := await self.bot.db.fetchrow(
            "SELECT * FROM leave WHERE guild_id = $1", member.guild.id
        ):
            channel = self.bot.get_channel(data["channel_id"])
            message = data["message"]
            if channel:
                try:
                    user_data = {
                        "id": member.id,
                        "name": member.name,
                        "mention": member.mention,
                        "display_name": member.display_name,
                        "created_at": member.created_at,
                        "joined_at": member.joined_at,
                        "discriminator": member.discriminator,
                        "avatar": str(member.display_avatar.url) if member.display_avatar else None
                    }
                    script = Script(message, [member.guild, channel, user_data])
                    await script.send(channel)
                except Exception as e:
                    await channel.send("There is an issue with your leave message, please make sure to fix it.")


async def setup(bot):
    await bot.add_cog(Listeners(bot))
