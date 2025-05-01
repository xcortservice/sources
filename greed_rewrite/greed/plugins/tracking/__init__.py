import discord
from discord.ext import commands
import logging
import asyncio
from typing import Dict, Set, List, Literal
from collections import defaultdict
from greed.framework.discord.context import Context
from greed.shared.config import Colors
from greed.framework import Context, Greed

logger = logging.getLogger("greed/plugins/tracking")

class Tracking(commands.Cog):
    def __init__(self, bot: Greed):
        self.bot = bot
        self.locks = defaultdict(asyncio.Lock)
        self.notification_lock = asyncio.Lock()
        self._tracking_channels: Dict[int, int] = {}
        self._vanity_channels: Dict[int, Dict] = {}
        self._username_cache: Set[int] = set()
        self._processed_notifications: Set[str] = set()

    async def cog_load(self):
        await self.create_tables()
        await self.load_channels()

    async def load_channels(self):
        try:
            tracking_rows = await self.bot.db.fetch(
                "SELECT guild_id, channel_id FROM tracking_channels"
            )
            vanity_rows = await self.bot.db.fetch(
                "SELECT guild_id, channel_id, message FROM vanity"
            )

            self._tracking_channels = {
                row["guild_id"]: row["channel_id"] for row in tracking_rows
            }
            self._vanity_channels = {row["guild_id"]: dict(row) for row in vanity_rows}
        except Exception as e:
            logger.error(f"Failed to load channels: {e}")

    async def create_tables(self):
        try:
            await self.bot.db.execute(
                """
                CREATE TABLE IF NOT EXISTS tracking_channels (
                    guild_id BIGINT PRIMARY KEY,
                    channel_id BIGINT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vanity (
                    guild_id BIGINT PRIMARY KEY,
                    channel_id BIGINT NOT NULL,
                    message TEXT
                );
                CREATE TABLE IF NOT EXISTS track.vanity (
                    vanity TEXT PRIMARY KEY,
                    user_ids BIGINT[] NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS track.username (
                    username TEXT PRIMARY KEY,
                    user_ids BIGINT[] NOT NULL DEFAULT '{}'
                );
            """)
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")

    async def update_tracking_channel(self, guild_id: int, channel_id: int) -> None:
        try:
            await self.bot.db.execute(
                """INSERT INTO tracking_channels (guild_id, channel_id)
                   VALUES ($1, $2)
                   ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2""",
                guild_id,
                channel_id,
            )
            self._tracking_channels[guild_id] = channel_id
        except Exception as e:
            logger.error(f"Failed to update tracking channel: {e}")

    async def update_vanity_channel(
        self, guild_id: int, channel_id: int, message: str = None
    ) -> None:
        try:
            await self.bot.db.execute(
                """INSERT INTO vanity (guild_id, channel_id, message)
                   VALUES($1, $2, $3)
                   ON CONFLICT (guild_id) DO UPDATE 
                   SET channel_id = excluded.channel_id,
                       message = COALESCE(excluded.message, vanity.message)""",
                guild_id,
                channel_id,
                message,
            )
            self._vanity_channels[guild_id] = {
                "channel_id": channel_id,
                "message": message,
            }
        except Exception as e:
            logger.error(f"Failed to update vanity channel: {e}")

    async def remove_tracking_channel(self, guild_id: int) -> bool:
        try:
            result = await self.bot.db.execute(
                "DELETE FROM tracking_channels WHERE guild_id = $1",
                guild_id,
            )
            self._tracking_channels.pop(guild_id, None)
            return result != "DELETE 0"
        except Exception as e:
            logger.error(f"Failed to remove tracking channel: {e}")
            return False

    async def remove_vanity_channel(self, guild_id: int) -> bool:
        try:
            result = await self.bot.db.execute(
                "DELETE FROM vanity WHERE guild_id = $1",
                guild_id,
            )
            self._vanity_channels.pop(guild_id, None)
            return result != "DELETE 0"
        except Exception as e:
            logger.error(f"Failed to remove vanity channel: {e}")
            return False

    @commands.group(
        name="tracking",
        brief="manage tracking settings",
        invoke_without_command=True,
    )
    async def tracking(self, ctx: Context):
        await ctx.send_help(ctx.command.qualified_name)

    @tracking.group(
        name="username",
        brief="manage username tracking",
        invoke_without_command=True,
    )
    async def username(self, ctx: Context):
        await ctx.send_help(ctx.command.qualified_name)

    @username.command(
        name="channel",
        aliases=["set"],
        brief="Set the channel where username changes will be sent",
        example=",tracking username channel #username-changes",
    )
    @commands.has_permissions(manage_channels=True)
    async def username_channel(self, ctx: Context, channel: discord.TextChannel):
        if not channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.embed(
                f"I don't have permission to send messages in {channel.mention}",
                "denied",
            )

        await self.update_tracking_channel(ctx.guild.id, channel.id)
        await ctx.embed(
            f"Username change notifications will now be sent to {channel.mention}",
            "approved",
        )
        logger.info(f"Tracking channel set to {channel.id} for guild {ctx.guild.id}")

    @username.command(
        name="unset",
        aliases=["remove", "reset"],
        brief="Remove the channel where username changes are sent",
        example=",tracking username unset",
    )
    @commands.has_permissions(manage_channels=True)
    async def username_unset(self, ctx: Context):
        if await self.remove_tracking_channel(ctx.guild.id):
            await ctx.embed("Username tracking channel has been unset", "approved")
            logger.info(f"Tracking channel unset for guild {ctx.guild.id}")
        else:
            await ctx.embed(
                "No channel is currently set for username tracking", "warning"
            )

    @tracking.group(
        name="vanity",
        brief="manage vanity URL tracking",
        invoke_without_command=True,
    )
    async def vanity(self, ctx: Context):
        await ctx.send_help(ctx.command.qualified_name)

    @vanity.command(
        name="set",
        brief="set the channel for checking vanities",
        example=",tracking vanity set #vanity-updates",
    )
    @commands.has_permissions(manage_roles=True)
    async def vanity_set(self, ctx: Context, channel: discord.TextChannel):
        await self.update_vanity_channel(ctx.guild.id, channel.id)
        await ctx.embed(f"**Vanity channel** set to {channel.mention}", "approved")

    @vanity.command(
        name="unset",
        brief="unset the channel for checking vanities",
        example=",tracking vanity unset",
    )
    @commands.has_permissions(manage_roles=True)
    async def vanity_unset(self, ctx: Context):
        if await self.remove_vanity_channel(ctx.guild.id):
            await ctx.embed("**Vanity channel** has been unset", "approved")
        else:
            await ctx.embed(
                "There is no **Vanity channel** set for this server", "denied"
            )

    @commands.group(invoke_without_command=True)
    async def notify(self, ctx: Context):
        """Manage notifications for vanities and usernames."""
        await ctx.send_help(ctx.command)

    @notify.command(name="add", example="vanity evict")
    async def notify_add(
        self, ctx: Context, type: Literal["vanity", "username"], desired: str
    ):
        """Add a notification for a vanity or username."""
        desired = desired.lower().strip()
        table = f"track.{type}"

        confirmation_message = (
            f"Are you sure you would like evict to notify you if the {type} `{desired}` is available?\n"
            f"> By agreeing, you allow evict to send you a direct message if the set {type} is available"
        )

        confirmed = await ctx.prompt(confirmation_message)
        if not confirmed:
            return await ctx.embed("Notification setup cancelled.", "neutral")

        try:
            await self.bot.db.execute(
                f"""
                INSERT INTO {table} ({type}, user_ids)
                VALUES ($1, ARRAY[$2]::BIGINT[])
                ON CONFLICT ({type}) 
                DO UPDATE SET user_ids = 
                    CASE 
                        WHEN $2 = ANY({table}.user_ids) THEN {table}.user_ids
                        ELSE array_append({table}.user_ids, $2::BIGINT)
                    END
                """,
                desired,
                ctx.author.id,
            )
            await ctx.embed(
                f"You will be notified if the {type} `{desired}` becomes available.",
                "approved"
            )
        except Exception as e:
            logger.error(f"Failed to add notification: {e}")
            await ctx.embed("Failed to add notification. Please try again later.", "warned")

    @notify.command(name="list")
    async def notify_list(self, ctx: Context):
        """List your active notifications."""
        try:
            vanities = await self.bot.db.fetch(
                """
                SELECT vanity
                FROM track.vanity
                WHERE $1 = ANY(user_ids)
                """,
                ctx.author.id,
            )

            usernames = await self.bot.db.fetch(
                """
                SELECT username
                FROM track.username
                WHERE $1 = ANY(user_ids)
                """,
                ctx.author.id,
            )

            if not vanities and not usernames:
                return await ctx.embed("You don't have any active notifications.", "warned")

            embed = discord.Embed(title="Your Active Notifications", color=Colors().information)

            if vanities:
                vanity_list = ", ".join(f"`{v['vanity']}`" for v in vanities)
                embed.add_field(name="Vanities", value=vanity_list, inline=True)

            if usernames:
                username_list = ", ".join(f"`{u['username']}`" for u in usernames)
                embed.add_field(name="Usernames", value=username_list, inline=True)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to list notifications: {e}")
            await ctx.embed("Failed to list notifications. Please try again later.", "warned")

    @notify.command(name="remove", example="vanity evict")
    async def notify_remove(
        self, ctx: Context, type: Literal["vanity", "username"], desired: str
    ):
        """Remove a notification for a vanity or username."""
        desired = desired.lower().strip()
        table = f"track.{type}"

        try:
            result = await self.bot.db.execute(
                f"""
                UPDATE {table}
                SET user_ids = array_remove(user_ids, $2::BIGINT)
                WHERE {type} = $1 AND $2 = ANY(user_ids)
                """,
                desired,
                ctx.author.id,
            )

            await self.bot.db.execute(
                f"""
                DELETE FROM {table} 
                WHERE array_length(user_ids, 1) IS NULL
                """
            )

            if result == "UPDATE 0":
                return await ctx.embed(f"You weren't tracking the {type} `{desired}`.", "warned")

            await ctx.embed(f"Removed notification for {type} `{desired}`.", "approved")
        except Exception as e:
            logger.error(f"Failed to remove notification: {e}")
            await ctx.embed("Failed to remove notification. Please try again later.", "warned")

    async def _clear_processed_notification(self, item: str):
        await asyncio.sleep(300)  # 5 minutes
        self._processed_notifications.discard(item)

    @commands.Cog.listener("on_guild_update")
    async def guild_update(self, before: discord.Guild, after: discord.Guild):
        if before.vanity_url_code == after.vanity_url_code:
            return

        if not self._vanity_channels:
            return

        vanity = before.vanity_url_code
        if not vanity or vanity.lower() == "none":
            return

        message = None
        for guild_data in self._vanity_channels.values():
            if guild_data.get("message"):
                message = guild_data["message"].replace("{vanity}", vanity)
                break

        if not message:
            message = f"Vanity **{vanity}** has been dropped"

        embed = discord.Embed(
            title="New Vanity",
            description=message,
            color=Colors().information,
        )

        for guild_data in self._vanity_channels.values():
            try:
                await self.bot.send_raw(guild_data["channel_id"], embed=embed)
                await asyncio.sleep(0.1)
            except Exception:
                continue

        try:
            data = {"method": "vanity_change", "vanity": vanity}
            await self.bot.connection.inform(data, destinations=self.bot.ipc.sources)
        except Exception as e:
            logger.error(f"Failed to send vanity notification: {e}")

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.name != after.name and len(before.name) > 4:
            if not await self.bot.glory_cache.ratelimited("rl:usernames", 4, 10) == 0:
                return

            if before.id in self._username_cache:
                return

            self._username_cache.add(before.id)
            asyncio.create_task(self._clear_username_cache(before.id))

            old_username = before.name
            if not self._tracking_channels:
                return

            embed = discord.Embed(
                description=f"**{old_username}** has been **dropped**.\n> usernames will be available after **14 days**",
                timestamp=discord.utils.utcnow(),
                color=Colors().information,
            )

            for channel_id in self._tracking_channels.values():
                try:
                    await self.bot.send_raw(channel_id, embed=embed)
                    await asyncio.sleep(0.5)
                except Exception:
                    continue

    async def _clear_username_cache(self, user_id: int):
        await asyncio.sleep(5)
        self._username_cache.discard(user_id)

    @commands.Cog.listener("on_username_change")
    async def dispatch_username_change(self, username: str):
        if not self._tracking_channels:
            return

        embed = discord.Embed(
            description=f"**{username}** has been **dropped**.\n ",
            timestamp=discord.utils.utcnow(),
            color=Colors().information,
        )

        for channel_id in self._tracking_channels.values():
            if not (channel := self.bot.get_channel(channel_id)):
                continue
            permissions = channel.permissions_for(channel.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                continue
            try:
                await channel.send(embed=embed)
            except Exception:
                continue


async def setup(bot: Greed) -> None:
    await bot.add_cog(Tracking(bot))
