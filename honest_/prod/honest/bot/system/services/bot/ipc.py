import asyncio

try:
    from rival import Connection
except Exception:
    pass
from typing import Any, Coroutine, Dict, List, Optional, Union

from cashews import cache
from data.config import CONFIG
from discord.ext.commands import AutoShardedBot
from typing_extensions import Self

cache.setup("mem://")

CACHE_TTL = CONFIG["CACHE_TTL"]

DICT = Optional[Dict[Any, Any]]

LIST = Optional[List[Any]]


class IPC:
    def __init__(self: Self, bot: AutoShardedBot):
        self.bot = bot
        self.bot.ipc = Connection(local_name=self.bot.cluster_name)
        self.transformers = self.bot.transformers

    async def start(self: Self) -> bool:
        # List of methods to exclude from IPC route registration
        excluded_methods = ["start", "pop_after", "__init__"]
        await self.bot.connection.start()

        # Collect all methods not in the excluded list
        routes: List[Coroutine] = [
            getattr(self, method_name)
            for method_name in dir(self)
            if callable(getattr(self, method_name))
            and method_name not in excluded_methods
        ]
        await asyncio.gather(*[self.bot.ipc.add_route(route) for route in routes])
        return True

    async def get_guild(self: Self, source: str, guild_id: int) -> DICT:
        if guild := self.bot.get_guild(guild_id):
            return self.transformers.transform_guild(guild)
        else:
            return None

    async def get_user(self: Self, source: str, user_id: int) -> DICT:
        if user := self.bot.get_user(user_id):
            return self.transformers.transform_user(user)
        else:
            return None

    async def get_member(self: Self, guild_id: int, member_id: int) -> DICT:
        if guild := self.bot.get_guild(guild_id):
            if member := guild.get_member(member_id):
                return self.transformers.transform_member(member)
        return None

    @cache(ttl=CACHE_TTL, key="ipc:guild_count:{source}")
    async def guild_count(self: Self, source: str) -> int:
        return len(self.bot.guilds)

    @cache(ttl=CACHE_TTL, key="ipc:user_count:{source}")
    async def user_count(self: Self, source: str) -> int:
        return len(self.bot.get_all_members())

    @cache(ttl=CACHE_TTL, key="ipc:channel_count:{source}")
    async def channel_count(self: Self, source: str) -> int:
        return sum([len(i.channels) for i in self.bot.guilds])

    @cache(ttl=CACHE_TTL, key="ipc:role_count:{source}")
    async def role_count(self: Self, source: str) -> int:
        return sum([len(i.roles) for i in self.bot.guilds])

    @cache(ttl=CACHE_TTL, key="ipc:get_guilds:{source}")
    async def get_guilds(self: Self, source: str) -> DICT:
        return {g.id: self.transformers.transform_guild(g) for g in self.bot.guilds}
