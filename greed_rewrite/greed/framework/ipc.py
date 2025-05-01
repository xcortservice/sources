from __future__ import annotations

import asyncio
import json
import logging
import time

from typing import Any, Dict, Optional, Callable, Set, List
from datetime import datetime
import discord
from greed.shared.config import Colors, ContextEmojis

logger = logging.getLogger("greed/ipc")


class IPC:
    """
    Inter-Process Communication system for Greed clusters.
    """

    def __init__(self, bot):
        self.bot = bot
        self.cluster_id = bot.cluster_id
        self.redis = bot.redis
        self.pubsub = None
        self.handlers: Dict[str, Callable] = {}
        self.listener_task = None
        self.heartbeat_task = None
        self._stop_event = asyncio.Event()
        self._message_lock = asyncio.Lock()
        self._processed_autopfp: Set[int] = set()

    async def start(self) -> None:
        """
        Initialize the IPC system.
        """
        try:
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe(f"cluster_{self.cluster_id}")

            self.add_handler("get_guild", self._handle_get_guild)
            self.add_handler("get_member", self._handle_get_member)
            self.add_handler("get_channel", self._handle_get_channel)
            self.add_handler("get_guild_count", self._handle_get_guild_count)
            self.add_handler("get_user_count", self._handle_get_user_count)
            self.add_handler(
                "autopfp:get_processed", self._handle_autopfp_get_processed
            )
            self.add_handler(
                "autopfp:mark_processed", self._handle_autopfp_mark_processed
            )

            self.listener_task = asyncio.create_task(self._listen())
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info(f"IPC system started for cluster {self.cluster_id}")

        except Exception as e:
            logger.error(f"Failed to start IPC: {e}", exc_info=True)
            await self.cleanup()
            raise

    async def _listen(self) -> None:
        """
        Listen for incoming IPC messages.
        """
        try:
            while not self._stop_event.is_set():
                try:
                    message = await self.pubsub.get_message(
                        ignore_subscribe_messages=True
                    )
                    if not message:
                        await asyncio.sleep(0.1)
                        continue

                    async with self._message_lock:
                        data = json.loads(message["data"])

                        if data.get("source_cluster") == self.cluster_id:
                            continue

                        if handler := self.handlers.get(data["command"]):
                            response = await handler(data.get("data", {}))

                            if response_channel := data.get("response_channel"):
                                await self.redis.publish(
                                    response_channel,
                                    json.dumps(
                                        {
                                            "cluster_id": self.cluster_id,
                                            "data": response,
                                            "timestamp": datetime.utcnow().isoformat(),
                                        }
                                    ),
                                )

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(
                        f"Error handling IPC message: {e}",
                        exc_info=True,
                    )

        except asyncio.CancelledError:
            logger.info("IPC listener cancelled")
        except Exception as e:
            logger.error(f"IPC listener error: {e}", exc_info=True)

    async def _heartbeat_loop(self) -> None:
        """
        Send periodic heartbeats.
        """
        while True:
            try:
                await self._send_heartbeat()
                if self._processed_autopfp:
                    logger.info(
                        f"Clearing processed autopfp set ({len(self._processed_autopfp)} entries)"
                    )
                    self._processed_autopfp.clear()
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def _send_heartbeat(self) -> None:
        """
        Send a heartbeat to Redis.
        """
        try:
            await self.redis.set(
                f"cluster_{self.cluster_id}_heartbeat",
                datetime.utcnow().isoformat(),
                ex=60,
            )
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}", exc_info=True)
            raise

    def add_handler(self, command: str, handler: Callable) -> None:
        """Register a new command handler"""
        self.handlers[command] = handler
        logger.debug(f"Added handler for {command}")

    async def broadcast(
        self,
        command: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[int, Any]:
        """
        Broadcast a command to all clusters and collect responses.
        """
        response_channel = (
            f"response_{command}_{self.cluster_id}_{datetime.utcnow().timestamp()}"
        )

        message = {
            "command": command,
            "data": data or {},
            "source_cluster": self.cluster_id,
            "response_channel": response_channel,
            "timestamp": datetime.utcnow().isoformat(),
        }

        temp_pubsub = self.redis.pubsub()
        await temp_pubsub.subscribe(response_channel)

        responses = {}
        try:
            for cluster_id in range(self.bot.cluster_count):
                if cluster_id != self.cluster_id:
                    await self.redis.publish(
                        f"cluster_{cluster_id}",
                        json.dumps(message),
                    )

            if handler := self.handlers.get(command):
                responses[self.cluster_id] = await handler(data or {})

            start_time = asyncio.get_event_loop().time()
            while len(responses) < self.bot.cluster_count:
                if asyncio.get_event_loop().time() - start_time > 5.0:
                    break

                try:
                    response = await asyncio.wait_for(
                        temp_pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=0.1,
                    )
                    if response and response["type"] == "message":
                        response_data = json.loads(response["data"])
                        responses[response_data["cluster_id"]] = response_data["data"]
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error processing response: {e}")

        finally:
            await temp_pubsub.unsubscribe()
            await temp_pubsub.close()

        return responses

    async def cleanup(self) -> None:
        """
        Cleanup IPC resources.
        """
        self._stop_event.set()

        if self.listener_task:
            self.listener_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()

    async def _handle_get_guild(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle get_guild requests.
        """
        guild_id = int(data["guild_id"])
        guild = self.bot.get_guild(guild_id)

        if not guild:
            return None

        return {
            "id": guild.id,
            "name": guild.name,
            "member_count": guild.member_count,
            "shard_id": guild.shard_id,
            "icon": guild.icon,
            "splash": guild.splash,
            "banner": guild.banner,
            "owner": guild.owner,
            "owner_id": guild.owner_id,
            "verification_level": guild.verification_level,
            "premium_subscription_count": guild.premium_subscription_count,
            "premium_tier": guild.premium_tier,
            "large": guild.large,
            "channels": guild.channels,
            "text_channels": guild.text_channels,
            "voice_channels": guild.voice_channels,
            "categories": guild.categories,
            "roles": guild.roles,
            "emojis": guild.emojis,
            "emoji_limit": guild.emoji_limit,
            "stickers": guild.stickers,
            "sticker_limit": guild.sticker_limit,
            "vanity_url_code": guild.vanity_url_code,
            "members": guild.members,
        }

    async def _handle_get_member(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle get_member requests.
        """
        guild_id = int(data["guild_id"])
        user_id = int(data["user_id"])

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None

        member = guild.get_member(user_id)
        if not member:
            return None

        return {
            "id": member.id,
            "name": member.name,
            "global_name": member.global_name,
            "roles": [role.id for role in member.roles],
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            "premium_since": (
                member.premium_since.isoformat() if member.premium_since else None
            ),
            "pending": member.pending,
            "communication_disabled_until": (
                member.communication_disabled_until.isoformat()
                if member.communication_disabled_until
                else None
            ),
            "guild_avatar": member.guild_avatar.url if member.guild_avatar else None,
            "guild_banner": member.guild_banner.url if member.guild_banner else None,
            "display_avatar": member.display_avatar.url,
            "banner": member.banner.url if member.banner else None,
            "status": member.status.name,
            "desktop_status": member.desktop_status.name,
            "web_status": member.web_status.name,
            "mobile_status": member.mobile_status.name,
            "activity": (
                {
                    "name": member.activity.name if member.activity else None,
                    "type": member.activity.type.name if member.activity else None,
                    "url": member.activity.url if member.activity else None,
                }
                if member.activity
                else None
            ),
        }

    async def _handle_get_channel(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle get_channel requests.
        """
        channel_id = int(data["channel_id"])

        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id)
            if channel:
                return {
                    "id": channel.id,
                    "name": channel.name,
                    "type": channel.type,
                    "guild_id": channel.guild.id,
                }

        return None

    async def get_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """
        Get channel information from any cluster.

        Args:
            channel_id: The ID of the channel to retrieve

        Returns:
            Channel information if found, None otherwise
        """
        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id)
            if channel:
                return {
                    "id": channel.id,
                    "name": channel.name,
                    "type": channel.type,
                    "guild_id": channel.guild.id,
                }

        responses = await self.broadcast("get_channel", {"channel_id": channel_id})

        for cluster_id, response in responses.items():
            if response is not None:
                return response

        return None

    async def get_guild(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """
        Get guild information from any cluster.

        Args:
            guild_id: The ID of the guild to retrieve

        Returns:
            Guild information if found, None otherwise
        """
        guild = self.bot.get_guild(guild_id)
        if guild:
            return {
                "id": guild.id,
                "name": guild.name,
                "member_count": guild.member_count,
                "shard_id": guild.shard_id,
                "icon": guild.icon,
                "splash": guild.splash,
                "banner": guild.banner,
                "owner": guild.owner,
                "owner_id": guild.owner_id,
                "verification_level": guild.verification_level,
                "premium_subscription_count": guild.premium_subscription_count,
                "premium_tier": guild.premium_tier,
                "large": guild.large,
                "channels": guild.channels,
                "text_channels": guild.text_channels,
                "voice_channels": guild.voice_channels,
                "categories": guild.categories,
                "roles": guild.roles,
                "emojis": guild.emojis,
                "emoji_limit": guild.emoji_limit,
                "stickers": guild.stickers,
                "sticker_limit": guild.sticker_limit,
                "vanity_url_code": guild.vanity_url_code,
                "members": guild.members,
            }

        responses = await self.broadcast("get_guild", {"guild_id": guild_id})

        for cluster_id, response in responses.items():
            if response is not None:
                return response

        return None

    async def _handle_get_guild_count(self, data: Dict[str, Any]) -> int:
        """
        Handle get_guild_count requests.
        """
        return len(self.bot.guilds)

    async def _handle_get_user_count(self, data: Dict[str, Any]) -> int:
        """
        Handle get_user_count requests.
        """
        return sum(guild.member_count for guild in self.bot.guilds)

    async def _handle_autopfp_get_processed(self, data: Dict) -> List[int]:
        return list(self._processed_autopfp)

    async def _handle_autopfp_mark_processed(self, data: Dict[str, Any]) -> None:
        guild_id = data.get("guild_id")
        if guild_id:
            logger.info(f"Marking guild {guild_id} as processed")
            self._processed_autopfp.add(guild_id)

    async def _handle_notify_vanity(self, data: Dict[str, Any]) -> None:
        vanity = data.get("vanity")
        if not vanity:
            return

        try:
            users = await self.bot.db.fetch(
                """
                SELECT user_ids
                FROM track.vanity
                WHERE vanity = $1
                """,
                vanity,
            )
            if not users:
                return

            user_ids = users[0]["user_ids"]
            embed = discord.Embed(
                description=f"The vanity `{vanity}` you have set to track with **greed** is now available.\n> {ContextEmojis().warn} You are receiving this message because you have setup vanity tracking with **evict**",
                color=Colors().information,
            )

            for user_id in user_ids:
                try:
                    if user := self.bot.get_user(user_id):
                        await user.send(embed=embed)
                except Exception:
                    continue

            await self.bot.db.execute(
                """
                DELETE FROM track.vanity
                WHERE vanity = $1
                """,
                vanity,
            )
        except Exception as e:
            logger.error(f"Failed to handle vanity notification: {e}")

    async def _handle_notify_username(self, data: Dict[str, Any]) -> None:
        username = data.get("username")
        if not username:
            return

        try:
            users = await self.bot.db.fetch(
                """
                SELECT user_ids
                FROM track.username
                WHERE username = $1
                """,
                username,
            )
            if not users:
                return

            user_ids = users[0]["user_ids"]
            embed = discord.Embed(
                description=f"The username `{username}` you have set to track with **greed** is now available.\n> {ContextEmojis().warn} You are receiving this message because you have setup username tracking with **evict**",
                color=Colors().information,
            )

            for user_id in user_ids:
                try:
                    if user := self.bot.get_user(user_id):
                        await user.send(embed=embed)
                except Exception:
                    continue

            await self.bot.db.execute(
                """
                DELETE FROM track.username
                WHERE username = $1
                """,
                username,
            )
        except Exception as e:
            logger.error(f"Failed to handle username notification: {e}")

    async def send_to_channel(
        self,
        guild_id: int,
        channel_id: int,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        view: Optional[discord.ui.View] = None,
        silent: bool = False,
    ) -> None:
        """
        Send a message to a specific channel in a guild.
        Includes cluster guesstimation and fallback mechanism.

        Args:
            guild_id: The ID of the guild containing the channel
            channel_id: The ID of the channel to send to
            content: Optional message content
            embed: Optional embed to send
            view: Optional view to attach
            silent: Whether to send the message silently
        """
        try:
            cache_key = f"channel_cluster:{channel_id}"
            cached_cluster = await self.redis.get(cache_key)

            if cached_cluster:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if guild and guild.shard_id == int(cached_cluster):
                        channel = guild.get_channel(channel_id)
                        if channel:
                            await channel.send(
                                content=content, embed=embed, view=view, silent=silent
                            )
                            return
                except Exception:
                    pass

            guild = self.bot.get_guild(guild_id)
            if guild:
                channel = guild.get_channel(channel_id)
                if channel:
                    await self.redis.set(cache_key, str(guild.shard_id), ex=3600)
                    await channel.send(
                        content=content, embed=embed, view=view, silent=silent
                    )
                    return

            responses = await self.broadcast(
                "get_channel", {"channel_id": channel_id, "guild_id": guild_id}
            )

            for cluster_id, response in responses.items():
                if response and response.get("guild_id") == guild_id:
                    await self.redis.set(cache_key, str(cluster_id), ex=3600)

                    await self.bot.ipc.send_to_channel(
                        guild_id=guild_id,
                        channel_id=channel_id,
                        content=content,
                        embed=embed,
                        view=view,
                        silent=silent,
                    )
                    return

            logger.error(
                f"Channel {channel_id} not found in any cluster for guild {guild_id}"
            )

        except Exception as e:
            logger.error(
                f"Error sending to channel {channel_id} in guild {guild_id}: {e}"
            )
