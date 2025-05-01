import asyncio
from collections import defaultdict
from typing import Any, List, Optional, TypedDict, Union

from discord import TextChannel, Thread
from system.managers.logger import configure_logger, make_dask_sink
from typing_extensions import Self
from xxhash import xxh32_hexdigest


class BaseRecord(TypedDict):
    guild_id: int
    channel_id: int


class Feed:
    """
    Base class for all Social Feeds.
    """

    bot: Any
    name: str
    posted: int = 0
    scheduled_deletion: List[int] = []
    task: Optional[asyncio.Task] = None

    def __init__(
        self,
        bot: Any,
        *,
        name: str = "",
    ):
        self.bot = bot
        self.name = name
        self.locks = defaultdict(asyncio.Lock)
        self.task = asyncio.create_task(self.start())

    def __repr__(self: Self) -> str:
        state = "running" if self.task and not self.task.done() else "finished"
        return f"<{self.name}Feed state={state} posted={self.posted} task={self.task}>"

    def __str__(self: Self) -> str:
        return self.name

    @property
    def redis(self: Self):
        return self.bot.redis

    @property
    def logger(self: Self):
        return configure_logger(f"Feeds/{self.name.title()}")

    @property
    def key(self: Self) -> str:
        return xxh32_hexdigest(f"feed:{self.name}")

    def make_key(self: Self, string: str):
        return xxh32_hexdigest(string)

    async def start(self: Self) -> None:
        """
        The feed task.
        """

        raise NotImplementedError

    async def stop(self: Self) -> None:
        """
        Stop the feed task.
        """

        if self.task:
            self.task.cancel("Feed stopped.")
            self.task = None

    async def get_records(self: Self) -> dict[Union[str, int], List[BaseRecord]]:
        """
        Get records receiving the feed.

        This will group the feeds based on the name_id,
        Which means that if you have multiple feeds for the same
        name_id, it will only fetch that user once.
        """

        raise NotImplementedError

    def can_post(self: Self, channel: Union[TextChannel, Thread]) -> bool:
        """
        Check if the channel can receive the feed.
        """

        return (
            channel.permissions_for(channel.guild.me).send_messages
            and channel.permissions_for(channel.guild.me).embed_links
            and channel.permissions_for(channel.guild.me).attach_files
        )
