from asyncio import sleep
from collections import defaultdict
from random import uniform
from typing import Dict, List, Optional, cast

from DataProcessing.models.Twitch import Channel, Stream
from discord import Client, Color, Embed
from system.classes.builtins import shorten

from .base import BaseRecord, Feed


class Record(BaseRecord):
    username: str


class Twitch(Feed):
    def __init__(self, bot: Client):
        super().__init__(
            bot,
            name="Twitch",
        )
        self.log = None

    async def get_records(self) -> Dict[int, List[Record]]:
        records = cast(
            List[Record],
            await self.bot.db.fetch(
                """
                SELECT *
                FROM feeds.twitch
                """,
            ),
        )

        result: Dict[int, List[Record]] = defaultdict(list)
        for record in records:
            result[record["username"]].append(record)

        return result

    async def get_streams(self, username: str, records: List[Record]):
        streams = await self.bot.services.twitch.get_streams(username=username)
        for stream in streams.data:
            if await self.redis.sismember(self.key, str(stream.id)):
                continue
            self.posted += 1
            self.bot.loop.create_task(self.dispatch(stream, records))

    async def dispatch(self, stream: Stream, records: List[Record]):

        async def send(embed: Embed, record: Record):
            if not (guild := self.bot.get_guild(record.guild_id)):
                return
            if not (channel := guild.get_channel(record.channel_id)):
                return
            if not self.can_post(channel):
                return
            return await channel.send(embed=embed)

        channel = await self.bot.services.twitch.get_channel(stream.user_login)
        embed = Embed(
            title=shorten(stream.title, 256),
            color=Color.from_str("#6441a5"),
            url=f"https://twitch.tv/{stream.user_login}",
        )
        embed.set_author(
            name=stream.user_login,
            url=f"https://twitch.tv/{stream.user_login}",
            icon_url=channel.channel.profile_image_url,
        )
        if stream.thumbnail_url:
            embed.set_image(url=stream.thumbnail_url)
        embed.timestamp = stream.started_at
        for record in records:
            await send(embed, record)
        await self.redis.sadd(self.key, str(stream.id))

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
                    self.bot.loop.create_task(self.get_streams(username, records))
                    await sleep(uniform(4, 9))
            if self.scheduled_deletion:
                await self.bot.db.execute(
                    """DELETE FROM feeds.twitch WHERE channel_id = ANY($1::BIGINT[])""",
                    self.scheduled_deletion,
                )
            await sleep(300)
