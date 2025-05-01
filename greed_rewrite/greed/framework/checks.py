import json
import logging
import redis
from typing import List, Tuple, Optional, Dict, Any

from discord import Guild, Member, TextChannel, Role
from discord.ext import commands
from discord.errors import Forbidden

from greed.framework.exceptions import BotMissingPermissions

logger = logging.getLogger("greed/checks")


class CommandChecker:
    """
    Handles all command permission and restriction checks
    """
    def __init__(self, bot):
        self.bot = bot
        self.redis = bot.redis
        self.db = bot.database
        self.ratelimit = bot.ratelimit
        self._cd = commands.CooldownMapping.from_cooldown(1, 2, commands.BucketType.default)

    async def check_permissions(self, ctx) -> bool:
        """
        Check if the bot has required permissions in the channel
        """
        if not ctx.guild or not ctx.channel:
            return False

        if await self.bot.is_owner(ctx.author):
            return True

        try:
            missing_perms = [
                perm
                for perm in ["send_messages", "embed_links", "attach_files"]
                if not getattr(ctx.channel.permissions_for(ctx.me), perm)
            ]
            if missing_perms:
                raise BotMissingPermissions(missing_perms)
            return True
        except Exception:
            return False

    async def check_blacklist(self, ctx) -> bool:
        """
        Check if the user or guild is blacklisted
        """
        check = await self.db.fetchrow(
            """
            SELECT * FROM blacklisted
            WHERE (object_id = $1 AND object_type = $2)
            OR (object_id = $3 AND object_type = $4)
            """,
            ctx.author.id,
            "user_id",
            ctx.guild.id,
            "guild_id",
        )
        return not bool(check)

    async def check_ratelimits(self, ctx) -> Tuple[bool, Optional[float]]:
        """
        Check if the user is being rate limited
        """
        try:
            is_limited, retry_after = await self.ratelimit.check_all(
                ctx.guild.id, ctx.channel.id, ctx.author.id
            )
            return is_limited, retry_after
        except redis.RedisError as e:
            logger.error(f"Redis error in ratelimit check: {e}")
            bucket = self._cd.get_bucket(ctx.message)
            retry_after = bucket.update_rate_limit()
            return bool(retry_after), retry_after

    async def check_command_restrictions(self, ctx) -> Tuple[bool, Optional[str]]:
        """
        Check if the command is restricted to specific roles
        """
        restrictions = await self.db.fetch(
            """SELECT role_id FROM command_restriction WHERE guild_id = $1 AND command_name = $2""",
            ctx.guild.id,
            ctx.command.qualified_name,
        )
        
        if not restrictions:
            return True, None
            
        roles = [ctx.guild.get_role(role_id[0]) for role_id in restrictions]
        if any(role in ctx.author.roles for role in roles if role):
            mention = ", ".join(role.mention for role in roles if role)
            return False, f"You have one of the following roles {mention} and cannot use this command"
            
        return True, None

    async def check_disabled_channels(self, ctx) -> Tuple[bool, Optional[str]]:
        """
        Check if the command is disabled in the current channel
        """
        disabled_channels = await self.db.fetchval(
            """
            SELECT channels 
            FROM disabled_commands 
            WHERE guild_id = $1 AND command = $2
            """,
            ctx.guild.id, 
            ctx.command.qualified_name
        )
        
        if not disabled_channels:
            return True, None
            
        channels = json.loads(disabled_channels)
        if not channels or ctx.channel.id in channels:
            return False, "This command has been disabled in this channel by administrators"
            
        return True, None

    async def check_command(self, ctx) -> bool:
        """
        Main command check that runs all checks in sequence
        """
        if not await self.check_permissions(ctx):
            return False
            
        if not await self.check_blacklist(ctx):
            return False
            
        is_limited, retry_after = await self.check_ratelimits(ctx)
        if is_limited:
            if retry_after > 1:
                cache_key = f"ratelimit_warning:{ctx.author.id}:{ctx.channel.id}"
                if await self.redis.set(cache_key, "1", ex=int(retry_after), nx=True):
                    await ctx.embed(f"You're being ratelimited! Please wait {retry_after:.1f} seconds.", "warned")
            raise commands.CommandOnCooldown(None, retry_after, commands.BucketType.default)
            
        allowed, message = await self.check_command_restrictions(ctx)
        if not allowed:
            await ctx.embed(message, "warned")
            return False
            
        allowed, message = await self.check_disabled_channels(ctx)
        if not allowed:
            await ctx.embed(message, "warned")
            return False
            
        return True 