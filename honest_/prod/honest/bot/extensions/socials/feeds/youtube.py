import asyncio
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from random import uniform
from typing import Dict, List, Optional, cast

from discord import (AllowedMentions, Client, Color, Embed, HTTPException,
                     TextChannel, Thread)
from discord.utils import utcnow
from typing_extensions import NoReturn, Self

from ..models.youtube import FeedEntry, YouTubeChannel, YouTubeFeed
from .base import BaseRecord, Feed


class Record(BaseRecord):
    youtube_id: int
    youtube_name: str
    color: Optional[str]


class YouTube(Feed):
    """
    Listener for new posts.
    """

    def __init__(self, bot: Client):
        super().__init__(
            bot,
            name="YouTube",
        )
        self.log = None

    def replacements(self: Self, user: YouTubeChannel, post: FeedEntry) -> dict:
        REPLACEMENTS = {
            "{post.description}": (post.title or "")[:256],
            "{post.date}": datetime.fromisoformat(post.published),
            "{post.url}": post.link,
            "{post.media_urls}": post.media_thumbnail[0].url,
            "{post.author.name}": user.name,
            "{post.author.nickname}": "",
            "{post.author.avatar}": user.avatarUrl,
            "{post.author.url}": user.url,
            "{post.stats.likes}": "",
            "{post.stats.comments}": "",
            "{post.stats.plays}": post.media_statistics.views,
            "{post.stats.shares}": "",
        }
        return REPLACEMENTS

    async def start(self: Self) -> NoReturn:
        self.log = self.logger
        self.log.info("Started Feed!")
        while True:
            records = await self.get_records()
            for youtube_id, records in records.items():
                needed = False
                for record in records:
                    if self.bot.get_guild(record["guild_id"]):
                        needed = True
                if needed:
                    self.bot.loop.create_task(self.get_posts(youtube_id, records))
                    await asyncio.sleep(uniform(0.5, 1.5))

            if self.scheduled_deletion:
                await self.bot.db.execute(
                    """
                    DELETE FROM feeds.youtube
                    WHERE channel_id = ANY($1::BIGINT[])
                    """,
                    self.scheduled_deletion,
                )
                self.scheduled_deletion.clear()

            await asyncio.sleep(60 * 9)

    async def get_records(self: Self) -> dict[int, List[Record]]:
        records = cast(
            List[Record],
            await self.bot.db.fetch(
                """
                SELECT *
                FROM feeds.youtube
                """,
            ),
        )

        result: Dict[int, List[Record]] = defaultdict(list)
        for record in records:
            result[record["youtube_id"]].append(record)

        return result

    async def get_posts(self: Self, youtube_id: str, records: List[Record]) -> NoReturn:
        feed = await YouTubeFeed.from_id(youtube_id)
        youtube_channel = await YouTubeChannel.from_id(youtube_id)
        if not feed:
            self.log.info(f"Couldnt fetch feed for YouTube Channel ID {youtube_id}")
            return
        for item in feed.entries[:3]:
            if await self.bot.redis.sismember(self.key, str(item.yt_videoid)):
                self.log.info(
                    f"skipping {str(item.yt_videoid)} due to it already have been sent"
                )
                continue
            if datetime.now(timezone.utc) - datetime.fromisoformat(
                item.published
            ) > timedelta(hours=1):
                self.log.info(f"skipping {item} due to it being to old")
                self.bot.ytvideo = item
                continue
            await self.bot.redis.sadd(self.key, str(item.yt_videoid))
            self.bot.loop.create_task(self.dispatch(youtube_channel, item, records))

    async def dispatch(
        self: Self,
        youtube_channel: YouTubeChannel,
        youtube_video: FeedEntry,
        records: List[Record],
        live: Optional[bool] = False,
    ) -> None:
        """
        Dispatch a youtube post to the subscription channels.
        """

        # self.log.debug(
        #    "Dispatching youtube post %r from @%s (%s).", youtube_video.id, youtube_channel.name, youtube_channel.id
        # )

        embed = Embed(
            description=f"[{youtube_video.title}]({youtube_video.link})",
            timestamp=datetime.fromisoformat(youtube_video.published),
        )
        embed.set_author(
            url=youtube_video.link,
            name=youtube_video.author,
            icon_url=youtube_channel.avatarUrl,
        )
        embed.color = self.bot.color
        embed.set_thumbnail(url=youtube_video.media_thumbnail[0].url)
        for record in records:

            guild = self.bot.get_guild(record["guild_id"])
            if not guild:
                continue

            channel = guild.get_channel_or_thread(record["channel_id"])
            if not isinstance(channel, (TextChannel, Thread)):
                self.scheduled_deletion.append(record["channel_id"])
                continue

            elif not self.can_post(channel):
                self.scheduled_deletion.append(record["channel_id"])
                continue

            with suppress(HTTPException):
                await channel.send(
                    embed=embed,
                    allowed_mentions=AllowedMentions.all(),
                )
