from __future__ import annotations

import time
import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from greed.framework import Greed

logger = logging.getLogger("greed/tools/ratelimit")


class RatelimitType:
    GUILD = "guild"
    USER = "user" 
    CHANNEL = "channel"
    GLOBAL = "global"


class RatelimitManager:
    """
    Handles rate limiting using Redis sorted sets for accurate time-based tracking
    """
    def __init__(self, bot: Greed):
        self.bot = bot
        self.redis = None
        
        self.limits = {
            RatelimitType.GUILD: (10, 10),
            RatelimitType.USER: (3, 5),
            RatelimitType.CHANNEL: (10, 5),
            RatelimitType.GLOBAL: (300, 60),
        }

    async def check_ratelimit(self, type: str, id: int) -> tuple[bool, float]:
        """
        Check if an entity is ratelimited
        Returns (is_ratelimited, retry_after)
        """
        limit, window = self.limits[type]
        key = f"ratelimit:{type}:{id}"

        current = await self.redis.zcount(key, min=time.time() - window, max="+inf")

        if current >= limit:
            scores = await self.redis.zrange(key, -limit, -limit, withscores=True)
            if scores:
                retry_after = scores[0][1] + window - time.time()
                if retry_after > 0:
                    return True, retry_after

        await self.redis.zadd(key, {str(time.time()): time.time()})
        await self.redis.expire(key, window)

        return False, 0

    async def check_all(self, guild_id: int, channel_id: int, user_id: int) -> tuple[bool, float]:
        """
        Check all applicable ratelimits for a command
        """
        checks = [
            (RatelimitType.GUILD, guild_id),
            (RatelimitType.CHANNEL, channel_id), 
            (RatelimitType.USER, user_id),
            (RatelimitType.GLOBAL, 0),
        ]

        for type, id in checks:
            is_limited, retry_after = await self.check_ratelimit(type, id)
            if is_limited:
                return True, retry_after

        return False, 0

    async def adjust_limits(self):
        """
        Automatically adjust ratelimits based on usage patterns
        """
        while True:
            try:
                global_usage = await self.redis.zcard(f"ratelimit:{RatelimitType.GLOBAL}:0")

                if global_usage > self.limits[RatelimitType.GLOBAL][0] * 0.9:
                    self.limits[RatelimitType.GLOBAL] = (
                        int(self.limits[RatelimitType.GLOBAL][0] * 1.2),
                        self.limits[RatelimitType.GLOBAL][1],
                    )

            except Exception as e:
                logger.error(f"Error in ratelimit adjustment: {e}")

            await asyncio.sleep(60)

    async def setup(self):
        """
        Initialize redis connection and start background tasks
        """
        self.redis = self.bot.redis
        self.bot.loop.create_task(self.adjust_limits()) 