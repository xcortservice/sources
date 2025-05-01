#
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from io import BytesIO
from random import uniform
from typing import Any, Dict, List, Optional, Union, cast

from aiohttp import ClientSession
from DataProcessing.models.Instagram.instagram import \
    EdgeFelixVideoTimelineClass as Timeline  # type: ignore
from DataProcessing.models.Instagram.instagram import (
    InstagramProfileModelResponse, UserPostItem)
from discord import Client, Color, Embed, File
from loguru import logger
from unidecode_rs import decode as unidecode_rs

from ..util import download_data
from .base import BaseRecord, Feed


class Record(BaseRecord):
    username: str


class Instagram(Feed):
    def __init__(self, bot: Client):
        super().__init__(
            bot,
            name="Instagram",
        )
        self.log = None

        async def get_records(self) -> Dict[int, List[Record]]:
            records = cast(
                List[Record],
                await self.bot.db.fetch(
                    """
                    SELECT *
                    FROM feeds.instagram
                    """,
                ),
            )

            result: Dict[int, List[Record]] = defaultdict(list)
            for record in records:
                result[record["username"]].append(record)

            return result

    async def get_posts(self, username: str, records: List[Record]):
        shifted = datetime.now(tz=timezone.utc) - timedelta(minutes=62)
        shifted_ts = shifted.timestamp()
        for i in range(10):
            try:
                user = await self.bot.services.instagram.get_user(
                    username, cached=False
                )
                posts = user.post_items
                break
            except Exception as error:
                if i == 9:
                    raise error
                else:
                    await asyncio.sleep(10)

        for post in posts:
            if post.taken_at_timestamp >= int(shifted_ts):
                if await self.redis.sismember(self.key, str(post.id)):
                    logger.info(f"{post.id} has already been posted, skipping it...")
                    continue
                self.bot.loop.create_task(self.dispatch(post, records))
                self.posted += 1

        self.log.info(f"Successfully dispatched {self.posted} instagram posts")

    async def dispatch(
        self,
        user: InstagramProfileModelResponse,
        post: UserPostItem,
        records: List[Record],
    ):

        async def send(embeds: List[Embed], record: Record, *, file: bytes = None):
            if not (guild := self.bot.get_guild(record.guild_id)):
                return
            if not (channel := guild.get_channel(record.channel_id)):
                return
            if not self.can_post(channel):
                return
            kwargs = {}
            if file:
                kwargs["file"] = File(fp=BytesIO(file), filename="instagram.mp4")
            return await channel.send(embeds=embeds, **kwargs)

        args = {}
        embed = Embed(
            title="New Post",
            description=unidecode_rs(post.title or "No Description Provided"),
            color=Color.from_str("#DD829B"),
        )
        footer_text = f"""❤️ {post.like_count.humanize()} 👀 {post.view_count.humanize()} 💬 {post.comment_count.humanize()} ∙ Instagram"""
        embed.set_footer(
            text=footer_text,
            icon_url="https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png",
        )
        embed.set_author(
            name=f"{user.full_name} (@{user.username})", icon_url=user.avatar_url
        )
        embed.url = post.url
        if post.video_url:
            args["file"] = await download_data(post.video_url)
        else:
            embed.set_image(url=post.display_url)
        for record in records:
            await send(embed, record, **args)
        await self.redis.sadd(self.key, str(post.id))

    async def start(self) -> None:
        self.log = self.logger
        self.log.info("Started Feed!")
        while True:
            self.posted = 0
            records = await self.get_records()
            for username, records in records.items():
                needed = False
                for record in records:
                    if self.bot.get_guild(record.guild_id):
                        needed = True
                        break
                if needed:
                    self.bot.loop.create_task(self.get_posts(username, records))
                    await asyncio.sleep(uniform(4, 9))

            if self.scheduled_deletion:
                await self.bot.db.execute(
                    """
                    DELETE FROM feeds.instagram
                    WHERE channel_id = ANY($1::BIGINT[])
                    """,
                    self.scheduled_deletion,
                )
                self.scheduled_deletion.clear()
            await asyncio.sleep(3600)
