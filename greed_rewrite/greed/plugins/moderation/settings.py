from __future__ import annotations

from typing import Optional
from discord import Member, User, Guild

from greed.framework import Greed


class ModSettings:
    def __init__(self, bot: Greed, guild: Guild):
        self.bot = bot
        self.guild = guild
        self.settings = {}
        self.thresholds = {}
        self.trusted_users = set()
        self.whitelisted_users = set()

    @classmethod
    async def fetch(cls, bot: Greed, guild: Guild) -> ModSettings:
        self = cls(bot, guild)
        await self._load_settings()
        return self

    async def _load_settings(self):
        antinuke_settings = await self.bot.db.fetchrow(
            """
            SELECT * FROM antinuke 
            WHERE guild_id = $1
            """,
            self.guild.id,
        )

        if antinuke_settings:
            self.settings = dict(antinuke_settings)

        antinuke_thresholds = await self.bot.db.fetchrow(
            """
            SELECT * FROM antinuke_threshold 
            WHERE guild_id = $1
            """,
            self.guild.id,
        )

        if antinuke_thresholds:
            self.thresholds = dict(antinuke_thresholds)

        trusted_users = await self.bot.db.fetch(
            """
            SELECT user_id FROM antinuke_admin 
            WHERE guild_id = $1
            """,
            self.guild.id,
        )
        self.trusted_users = {r["user_id"] for r in trusted_users}

        whitelisted_users = await self.bot.db.fetch(
            """
            SELECT user_id FROM antinuke_whitelist 
            WHERE guild_id = $1
            """,
            self.guild.id,
        )
        self.whitelisted_users = {r["user_id"] for r in whitelisted_users}

    def is_trusted(self, user: Member | User) -> bool:
        if user.id == self.guild.owner_id:
            return True
        if user.id in self.bot.owner_ids:
            return True
        return user.id in self.trusted_users

    def is_whitelisted(self, user: Member | User) -> bool:
        if self.is_trusted(user):
            return True
        return user.id in self.whitelisted_users

    async def check_threshold(
        self, bot: Greed, user: Member | User, action: str
    ) -> bool:
        if not self.settings.get(action, False):
            return False

        threshold = self.thresholds.get(action, 0)
        if threshold == 0:
            return True

        count = await bot.db.fetchval(
            """
            SELECT COUNT(*) FROM moderation.history
            WHERE guild_id = $1 AND moderator_id = $2 AND action = $3
            AND created_at > NOW() - INTERVAL '1 hour'
            """,
            self.guild.id,
            user.id,
            action,
        )

        return count >= threshold
