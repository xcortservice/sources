import asyncio
import contextlib
import sys
from loguru import logger
from weakref import WeakValueDictionary
from typing import Union, Optional, Dict, Set
from collections import defaultdict

import discord
from asyncpg import Record
from asyncpg.exceptions import UniqueViolationError
from discord.ext import commands
from discord.ext.commands import Context
from greed.framework import Greed
from greed.framework.pagination import Paginator

from greed.shared.config import Colors


class StarboardCache:
    def __init__(self, bot: Greed):
        self.bot = bot
        self._starboards: Dict[int, Dict[str, Record]] = defaultdict(dict)
        self._ignored_channels: Dict[int, Set[int]] = defaultdict(set)
        self._message_cache: Dict[int, discord.Message] = {}
        self._reaction_cache: Dict[int, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._lock = asyncio.Lock()

    async def get_starboard(self, guild_id: int, emoji: str) -> Optional[Record]:
        try:
            starboard = await self.bot.db.fetchrow(
                "SELECT channel_id, emoji, threshold FROM starboard WHERE guild_id = $1 AND emoji = $2",
                guild_id,
                emoji,
            )
            return starboard
        except Exception as e:
            logger.error(f"Error fetching starboard config: {e}", exc_info=True)
            return None

    async def is_channel_ignored(self, guild_id: int, channel_id: int) -> bool:
        if channel_id not in self._ignored_channels[guild_id]:
            async with self._lock:
                if channel_id not in self._ignored_channels[guild_id]:
                    ignored = await self.bot.db.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM starboard_ignored WHERE guild_id = $1 AND channel_id = $2)",
                        guild_id,
                        channel_id,
                    )
                    if ignored:
                        self._ignored_channels[guild_id].add(channel_id)
        return channel_id in self._ignored_channels[guild_id]

    def cache_message(self, message: discord.Message):
        self._message_cache[message.id] = message

    def get_cached_message(self, message_id: int) -> Optional[discord.Message]:
        return self._message_cache.get(message_id)

    def update_reaction_count(self, message_id: int, emoji: str, count: int):
        self._reaction_cache[message_id][emoji] = count

    def get_reaction_count(self, message_id: int, emoji: str) -> int:
        return self._reaction_cache[message_id].get(emoji, 0)

    def clear_cache(self):
        self._message_cache.clear()
        self._reaction_cache.clear()


class starboard(commands.Cog, name="Starboard"):
    def __init__(self, bot: "Greed"):
        self.bot = bot
        self._locks: WeakValueDictionary[int, asyncio.Lock] = WeakValueDictionary()
        self._about_to_be_deleted: set[int] = set()
        self.cache = StarboardCache(bot)
        self._batch_queue: Dict[int, Dict[str, Dict[int, Set[int]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(set))
        )
        self._batch_lock = asyncio.Lock()
        self._batch_task = None

    async def cog_load(self):
        self._batch_task = asyncio.create_task(self._process_batch_queue())

    async def cog_unload(self):
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

    async def _process_batch_queue(self):
        while True:
            try:
                await asyncio.sleep(5)

                to_process = {}
                async with self._batch_lock:
                    for guild_id, emoji_data in self._batch_queue.items():
                        to_process[guild_id] = {}
                        for emoji, channel_data in emoji_data.items():
                            to_process[guild_id][emoji] = {}
                            for channel_id, message_ids in channel_data.items():
                                to_process[guild_id][emoji][
                                    channel_id
                                ] = message_ids.copy()

                for guild_id, emoji_data in to_process.items():
                    for emoji, channel_data in emoji_data.items():
                        for channel_id, message_ids in channel_data.items():
                            if message_ids:

                                await self._process_message_batch(
                                    guild_id, emoji, message_ids
                                )
                                async with self._batch_lock:
                                    if (
                                        guild_id in self._batch_queue
                                        and emoji in self._batch_queue[guild_id]
                                        and channel_id
                                        in self._batch_queue[guild_id][emoji]
                                    ):
                                        self._batch_queue[guild_id][emoji][
                                            channel_id
                                        ].clear()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing starboard batch: {e}", exc_info=True)

    async def _process_message_batch(
        self, guild_id: int, emoji: str, message_ids: Set[int]
    ):
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return

            starboard = await self.cache.get_starboard(guild_id, emoji)
            if not starboard:
                return

            starboard_channel = guild.get_channel(starboard["channel_id"])
            if not starboard_channel:
                logger.warning(f"Starboard channel {starboard['channel_id']} not found, deleting record")
                await self.bot.db.execute(
                    "DELETE FROM starboard WHERE guild_id = $1 AND channel_id = $2 AND emoji = $3",
                    guild_id,
                    starboard["channel_id"],
                    emoji,
                )
                self.cache._starboards[guild_id].clear()
                return

            for message_id in message_ids:
                try:
                    channel = guild.get_channel(starboard["channel_id"])
                    if not channel or not isinstance(channel, discord.TextChannel):
                        continue

                    try:
                        message = await channel.fetch_message(message_id)
                        if not message:
                            continue

                        if message.author.bot:
                            return

                        actual_count = 0
                        for reaction in message.reactions:
                            if str(reaction.emoji) == emoji:
                                actual_count = reaction.count
                                break

                        if actual_count >= starboard["threshold"]:
                            try:
                                content, embed, files = await self.render_starboard_entry(
                                    starboard, message
                                )

                                existing_entry = await self.bot.db.fetchrow(
                                    "SELECT starboard_message_id FROM starboard_entries WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3 AND emoji = $4",
                                    guild.id,
                                    channel.id,
                                    message_id,
                                    emoji,
                                )

                                if existing_entry:
                                    try:
                                        starboard_message = (
                                            await starboard_channel.fetch_message(
                                                existing_entry["starboard_message_id"]
                                            )
                                        )
                                        await starboard_message.edit(
                                            content=content, embed=embed
                                        )
                                    except discord.NotFound:
                                        starboard_message = (
                                            await starboard_channel.send(
                                                content=content, embed=embed, files=files
                                            )
                                        )
                                        await self.bot.db.execute(
                                            "UPDATE starboard_entries SET starboard_message_id = $1 WHERE guild_id = $2 AND channel_id = $3 AND message_id = $4 AND emoji = $5",
                                            starboard_message.id,
                                            guild.id,
                                            channel.id,
                                            message_id,
                                            emoji,
                                        )
                                else:
                                    starboard_message = await starboard_channel.send(
                                        content=content, embed=embed, files=files
                                    )
                                    await self.bot.db.execute(
                                        "INSERT INTO starboard_entries (guild_id, channel_id, message_id, emoji, starboard_message_id) VALUES ($1, $2, $3, $4, $5)",
                                        guild.id,
                                        channel.id,
                                        message_id,
                                        emoji,
                                        starboard_message.id,
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error creating/updating starboard message: {e}",
                                    exc_info=True,
                                )
                        else:
                            return

                    except discord.NotFound:
                        continue
                    except Exception as e:
                        logger.error(f"Error fetching message {message_id}: {e}", exc_info=True)

                except Exception as e:
                    logger.error(f"Error processing message {message_id}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in batch processing: {e}", exc_info=True)

    async def reaction_logic(self, fmt: str, payload: discord.RawReactionActionEvent):
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            channel = guild.get_channel(payload.channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            if await self.cache.is_channel_ignored(guild.id, channel.id):
                return

            try:
                message = await channel.fetch_message(payload.message_id)
                if message.author.bot:
                    return
            except discord.NotFound:
                return

            starboard = await self.cache.get_starboard(guild.id, str(payload.emoji))
            if not starboard:
                return

            starboard_channel = guild.get_channel(starboard["channel_id"])
            if not starboard_channel:
                return

            member = payload.member or guild.get_member(payload.user_id)
            if not member:
                return

            current_count = self.cache.get_reaction_count(
                payload.message_id, str(payload.emoji)
            )

            if fmt == "star":
                new_count = current_count + 1
            else:
                new_count = max(0, current_count - 1)

            self.cache.update_reaction_count(
                payload.message_id, str(payload.emoji), new_count
            )

            async with self._batch_lock:
                if guild.id not in self._batch_queue:
                    self._batch_queue[guild.id] = defaultdict(lambda: defaultdict(set))
                self._batch_queue[guild.id][str(payload.emoji)][payload.channel_id].add(
                    payload.message_id
                )
        except Exception as e:
            logger.error(f"Error in starboard reaction logic: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.reaction_logic("star", payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.reaction_logic("unstar", payload)

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEmojiEvent):
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            channel = guild.get_channel(payload.channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            starboard_entry = await self.bot.db.fetchrow(
                "DELETE FROM starboard_entries WHERE message_id = $1 RETURNING emoji, starboard_message_id",
                payload.message_id,
            )
            if not starboard_entry:
                return

            starboard = await self.cache.get_starboard(
                guild.id, starboard_entry["emoji"]
            )
            if not starboard:
                return

            starboard_channel = guild.get_channel(starboard["channel_id"])
            if not starboard_channel:
                return

            with contextlib.suppress(discord.HTTPException):
                await starboard_channel.delete_messages(
                    [discord.Object(id=starboard_entry["starboard_message_id"])]
                )

            self.cache.update_reaction_count(
                payload.message_id, starboard_entry["emoji"], 0
            )

        except Exception as e:
            logger.error(f"Error in reaction clear: {e}")

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        try:
            if payload.message_id in self._about_to_be_deleted:
                self._about_to_be_deleted.discard(payload.message_id)
                return

            await self.bot.db.execute(
                "DELETE FROM starboard_entries WHERE guild_id = $1 AND starboard_message_id = $2",
                payload.guild_id,
                payload.message_id,
            )

            self.cache.get_cached_message(payload.message_id)
            self.cache._reaction_cache.pop(payload.message_id, None)

        except Exception as e:
            logger.error(f"Error in message delete: {e}")

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self, payload: discord.RawBulkMessageDeleteEvent
    ):
        try:
            if payload.message_ids <= self._about_to_be_deleted:
                self._about_to_be_deleted.difference_update(payload.message_ids)
                return

            await self.bot.db.execute(
                "DELETE FROM starboard_entries WHERE guild_id = $1 AND starboard_message_id = ANY($2::BIGINT[])",
                payload.guild_id,
                list(payload.message_ids),
            )

            for message_id in payload.message_ids:
                self.cache.get_cached_message(message_id)
                self.cache._reaction_cache.pop(message_id, None)

        except Exception as e:
            logger.error(f"Error in bulk message delete: {e}")

    async def render_starboard_entry(self, starboard: Record, message: discord.Message):
        try:
            embed = discord.Embed(color=Colors().information)
            embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.display_avatar,
                url=message.jump_url,
            )

            content = message.content
            if len(content) > 2048:
                content = content[:2045] + "..."

            embed.description = content

            if message.embeds:
                for msg_embed in message.embeds:
                    if msg_embed.type in ("image", "gif", "gifv"):
                        if msg_embed.url:
                            embed.set_image(url=msg_embed.url)
                    elif msg_embed.description:
                        embed.description += f"\n\n{msg_embed.description}"

            files = []
            for attachment in message.attachments:
                if attachment.url.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".webp")
                ):
                    embed.set_image(url=attachment.url)
                elif attachment.url.lower().endswith(
                    (".mp4", ".mov", ".webm", ".mp3", ".ogg", ".wav")
                ):
                    file = await attachment.to_file()
                    if sys.getsizeof(file.fp) <= message.guild.filesize_limit:
                        files.append(file)

            if message.reference and (reference := message.reference.resolved):
                if not isinstance(reference, discord.DeletedReferencedMessage):
                    embed.add_field(
                        name=f"**Replying to {reference.author.display_name}**",
                        value=f"[Jump to reply]({reference.jump_url})",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="**Replying to deleted message**",
                        value="Original message was deleted",
                        inline=False,
                    )

            embed.add_field(
                name=f"**#{message.channel}**",
                value=f"[Jump to message]({message.jump_url})",
                inline=False,
            )
            embed.timestamp = message.created_at

            reaction_count = self.cache.get_reaction_count(
                message.id, starboard["emoji"]
            )
            reactions = f"#{reaction_count:,}"

            if str(starboard["emoji"]) == "⭐":
                if 5 > reaction_count >= 0:
                    reaction = "⭐"
                elif 10 > reaction_count >= 5:
                    reaction = "🌟"
                elif 25 > reaction_count >= 10:
                    reaction = "💫"
                else:
                    reaction = "✨"
            else:
                reaction = str(starboard["emoji"])

            return f"{reaction} **{reactions}**", embed, files

        except Exception as e:
            raise

    @commands.group(
        name="starboard",
        usage="(subcommand) <args>",
        example=",starboard",
        aliases=["board", "star", "skullboard", "clownboard", "cb", "skull"],
        brief="Create a channel saved of messsages reacted to with said reaction",
        invoke_without_command=True,
    )
    @commands.has_permissions(manage_guild=True)
    async def starboard(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command.qualified_name)

    @starboard.command(
        name="add",
        usage="(channel) (emoji)",
        example=",starboard add #shame 🤡 2",
        brief="Add a channel for the starboard to be set to, add an emoji for it to be saved when a message is reacted to with said emoji",
        aliases=["create"],
    )
    @commands.has_permissions(manage_guild=True)
    async def starboard_add(
        self,
        ctx: Context,
        channel: Union[discord.TextChannel, discord.Thread],
        emoji: str,
        threshold: int,
    ):
        try:
            await ctx.message.add_reaction(emoji)
        except discord.HTTPException:
            return await ctx.embed(f"**{emoji}** is not a valid emoji", "warned")

        try:
            await self.bot.db.execute(
                "INSERT INTO starboard (guild_id, channel_id, emoji, threshold) VALUES ($1, $2, $3, $4)",
                ctx.guild.id,
                channel.id,
                emoji,
                threshold,
            )
            self.cache._starboards[ctx.guild.id].clear()
            await ctx.embed(
                f"Added a **starboard** for {channel.mention} using **{emoji}** with a threshold of `{threshold}`",
                "approved",
            )
        except UniqueViolationError:
            await ctx.embed(
                f"There is already a **starboard** using **{emoji}**", "warned"
            )
        except Exception as e:
            logger.error(f"Error in starboard_add: {e}", exc_info=True)
            await ctx.embed("An error occurred while adding the starboard.", "warned")

    @starboard.command(
        name="remove",
        usage="(channel) (emoji)",
        example=",starboard remove #shame 🤡",
        brief="remove a starboard from the starboard channel",
        aliases=["delete", "del", "rm"],
    )
    @commands.has_permissions(manage_guild=True)
    async def starboard_remove(
        self,
        ctx: Context,
        channel: Union[discord.TextChannel, discord.Thread],
        emoji: str,
    ):
        try:
            result = await self.bot.db.execute(
                "DELETE FROM starboard WHERE guild_id = $1 AND channel_id = $2 AND emoji = $3",
                ctx.guild.id,
                channel.id,
                emoji,
            )
            if result == "DELETE 0":
                return await ctx.embed(
                    f"There isn't a **starboard** using **{emoji}**", "warned"
                )

            self.cache._starboards[ctx.guild.id].clear()
            await ctx.embed(
                f"Removed the **starboard** for {channel.mention} using **{emoji}**",
                "approved",
            )
        except Exception as e:
            logger.error(f"Error in starboard_remove: {e}")
            await ctx.embed("An error occurred while removing the starboard.", "warned")

    @starboard.command(
        name="list",
        aliases=["show", "all"],
        brief="List all the Starboards currently set to the starboard channel",
        example=",starboard list",
    )
    @commands.has_permissions(manage_guild=True)
    async def starboard_list(self, ctx: Context):
        try:
            rows = await self.bot.db.fetch(
                "SELECT channel_id, emoji, threshold FROM starboard WHERE guild_id = $1",
                ctx.guild.id,
            )

            starboards = []
            for row in rows:
                channel = ctx.guild.get_channel(row["channel_id"])
                if channel:
                    starboards.append(
                        f"{channel.mention} - **{row['emoji']}** (threshold: `{row['threshold']}`)"
                    )

            if not starboards:
                return await ctx.embed("No **starboards** have been set up", "warned")

            embed = discord.Embed(title="Starboards", color=Colors().information)
            paginator = Paginator(ctx, starboards, embed=embed)
            await paginator.start()

        except Exception as e:
            logger.error(f"Error in starboard_list: {e}", exc_info=True)
            await ctx.embed("An error occurred while listing starboards.", "warned")

    @starboard.command(
        name="ignore",
        example=",starboard ignore #shame",
        brief="Ignore a channel from being added to the starboard",
    )
    @commands.has_permissions(manage_guild=True)
    async def starboard_ignore(self, ctx: Context, channel: discord.TextChannel):
        try:
            await self.bot.db.execute(
                "INSERT INTO starboard_ignored (guild_id, channel_id) VALUES ($1, $2)",
                ctx.guild.id,
                channel.id,
            )
            self.cache._ignored_channels[ctx.guild.id].add(channel.id)
            await ctx.embed(f"Ignored **{channel.mention}**", "approved")
        except UniqueViolationError:
            await ctx.embed(f"**{channel.mention}** is already being ignored", "warned")
        except Exception as e:
            logger.error(f"Error in starboard_ignore: {e}")
            await ctx.embed("An error occurred while ignoring the channel.", "warned")

    @starboard.command(
        name="unignore",
        example=",starboard unignore #shame",
        brief="Unignore a channel from being added to the starboard",
    )
    @commands.has_permissions(manage_guild=True)
    async def starboard_unignore(self, ctx: Context, channel: discord.TextChannel):
        try:
            result = await self.bot.db.execute(
                "DELETE FROM starboard_ignored WHERE guild_id = $1 AND channel_id = $2",
                ctx.guild.id,
                channel.id,
            )
            if result == "DELETE 0":
                return await ctx.embed(
                    f"**{channel.mention}** is not being ignored", "warned"
                )

            self.cache._ignored_channels[ctx.guild.id].discard(channel.id)
            await ctx.embed(f"Unignored **{channel.mention}**", "approved")
        except Exception as e:
            logger.error(f"Error in starboard_unignore: {e}")
            await ctx.embed("An error occurred while unignoring the channel.", "warned")

    @starboard.command(
        name="move",
        usage="(emoji) (channel)",
        example=",starboard move 😭 #starboard",
        brief="Move a starboard to a different channel",
        aliases=["update", "channel"],
    )
    @commands.has_permissions(manage_guild=True)
    async def starboard_move(
        self,
        ctx: Context,
        emoji: str,
        channel: Union[discord.TextChannel, discord.Thread],
    ):
        try:
            result = await self.bot.db.execute(
                "UPDATE starboard SET channel_id = $1 WHERE guild_id = $2 AND emoji = $3",
                channel.id,
                ctx.guild.id,
                emoji,
            )

            if result == "UPDATE 0":
                return await ctx.embed(
                    f"There isn't a **starboard** using **{emoji}**", "warned"
                )

            self.cache._starboards[ctx.guild.id].clear()
            await ctx.embed(
                f"Moved the **starboard** for emoji **{emoji}** to {channel.mention}",
                "approved",
            )
        except Exception as e:
            logger.error(f"Error in starboard_move: {e}", exc_info=True)
            await ctx.embed("An error occurred while moving the starboard.", "warned")


async def setup(bot):
    await bot.add_cog(starboard(bot))
