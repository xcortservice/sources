from asyncio import sleep
from collections import defaultdict
from random import uniform
from typing import Dict, List, Optional, cast

from DataProcessing.models.Kick import (KickChannel,  # type: ignore
                                        Livestream, User)
from discord import Client, Color, Embed
from system.classes.builtins import shorten

from .base import BaseRecord, Feed


class Record(BaseRecord):
    username: str


class Kick(Feed):
    def __init__(self, bot: Client):
        super().__init__(
            bot,
            name="Kick",
        )
        self.log = None

    async def get_records(self) -> Dict[int, List[Record]]:
        records = cast(
            List[Record],
            await self.bot.db.fetch(
                """
                SELECT *
                FROM feeds.kick
                """,
            ),
        )

        result: Dict[int, List[Record]] = defaultdict(list)
        for record in records:
            result[record["username"]].append(record)

        return result

    async def get_streams(self, username: str, records: List[Record]):
        user = await self.bot.services.kick.get_channel(username, cached=False)
        if user.livestream:
            if await self.redis.sismember(self.key, str(user.livestream.id)):
                return
            self.bot.loop.create_task(
                self.dispatch(user.livestream, user.user, user, records)
            )
            self.posted += 1

    async def dispatch(
        self, stream: Livestream, user: User, raw: KickChannel, records: List[Record]
    ):

        async def send(embed: Embed, record: Record):
            if not (guild := self.bot.get_guild(record.guild_id)):
                return
            if not (channel := guild.get_channel(record.channel_id)):
                return
            if not self.can_post(channel):
                return
            return await channel.send(embed=embed)

        embed = Embed(
            title=f"{user.username} is now live!",
            description=shorten(stream.session_title, 256),
            color=Color.from_str("#00e701"),
            url=f"https://kick.com/{user.username}",
        )
        embed.add_field(name="Views", value=stream.viewer_count.humanize(), inline=True)
        embed.add_field(
            name="Followers",
            value=raw.followersCount.humanize() if raw.followersCount else "0",
            inline=True,
        )
        embed.set_footer(
            text="Kick Notifications", icon_url="https://kick.com/img/kick-logo.svg"
        )
        embed.set_author(name=user.username, icon_url=user.profile_pic)
        if stream.thumbnail:
            embed.set_thumbnail(url=stream.thumbnail.url)

        for record in records:
            await send(embed, record)
        await self.redis.sadd(self.key, str(stream.id))

    async def start(self) -> None:
        self.log = self.logger
        self.log.info("Started Feed!")
        while True:
            records = await self.get_records()
            for username, records in records.items():
                self.bot.loop.create_task(self.get_streams(username, records))
                await sleep(uniform(0.5, 1.5))

            if self.scheduled_deletion:
                await self.bot.db.execute(
                    """
                    DELETE FROM feeds.kick
                    WHERE channel_id = ANY($1::BIGINT[])
                    """,
                    self.scheduled_deletion,
                )
                self.scheduled_deletion.clear()

            await sleep(60 * 9)
