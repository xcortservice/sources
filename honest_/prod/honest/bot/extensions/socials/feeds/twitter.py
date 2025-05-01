import asyncio
import traceback
from collections import defaultdict
from contextlib import suppress
from datetime import timedelta
from random import uniform
from typing import Dict, List, Optional, cast

import orjson
from DataProcessing.models.Twitter.tweets import BasicUser, Tweet, Tweets
from discord import (AllowedMentions, Client, Color, Embed, HTTPException,
                     TextChannel, Thread)
from discord.utils import get, utcnow
from typing_extensions import Self

from .base import BaseRecord, Feed


class Record(BaseRecord):
    username: str
    user_id: int


class Twitter(Feed):
    """
    Listener for new tweets.
    """

    def __init__(self, bot: Client):
        super().__init__(
            bot,
            name="Twitter",
        )

    def replacements(self: Self, user: BasicUser, tweet: Tweet) -> dict:
        REPLACEMENTS = {
            "{post.description}": tweet.text,
            "{post.date}": tweet.posted_at,
            "{post.url}": tweet.url,
            "{post.media_urls}": tweet.media[0] if len(tweet.media) > 0 else "",
            "{post.author.name}": user.name,
            "{post.author.avatar}": user.avatar_url,
            "{post.author.url}": user.url,
        }
        return REPLACEMENTS

    async def start(self: Self) -> None:
        self.log = self.logger
        self.log.info("Started Feed!")
        while True:
            records = await self.get_records()
            for twitter_id, records in records.items():
                self.bot.loop.create_task(self.get_tweets(twitter_id, records))
                await asyncio.sleep(uniform(0.5, 1.5))

            if self.scheduled_deletion:
                await self.bot.db.execute(
                    """
                    DELETE FROM feeds.twitter
                    WHERE channel_id = ANY($1::BIGINT[])
                    """,
                    self.scheduled_deletion,
                )
                self.scheduled_deletion.clear()

            await asyncio.sleep(60 * 9)

    async def get_records(self: Self) -> Dict[int, List[Record]]:
        records = cast(
            List[Record],
            await self.bot.db.fetch(
                """
                SELECT *
                FROM feeds.twitter
                """,
            ),
        )

        result: Dict[int, List[Record]] = defaultdict(list)
        for record in records:
            result[record["user_id"]].append(record)

        return result

    async def get_tweets(self: Self, user_id: int, records: List[Record]) -> None:
        async with self.locks[f"get_tweets:{user_id}"]:
            self.log.info(f"getting tweets for user {user_id}")
            await self.fetch_tweets(user_id, records)

    async def fetch_tweets(self: Self, user_id: int, records: List[Record]) -> None:
        """
        Fetch and dispatch new tweets.
        """
        cached = False
        if not cached:
            try:
                data = await Tweets.fetch(user_id)
                self.log.info(f"got tweets for {user_id}: {data}")
            except Exception as e:
                self.log.info(f"error during tweet fetching: {e}")
                tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                self.bot.twitter_tb = tb
                data = None
            if not data or not data.user:
                self.log.info(
                    "No tweets available for %s (%s).",
                    records[0]["username"],
                    user_id,
                )
                return

        for tweet in reversed(data.tweets[:6]):
            if utcnow() - tweet.posted_at > timedelta(hours=2):
                self.log.info(f"Tweet: {tweet.id} is to old")
                continue

            elif tweet.source == "Advertisement":
                continue

            if await self.bot.redis.sismember(self.key, str(tweet.id)):
                self.log.info(
                    f"skipping {str(tweet.id)} due to it already have been sent"
                )
                continue

            await self.bot.redis.sadd(self.key, str(tweet.id))
            self.bot.loop.create_task(self.dispatch(data.user, tweet, records))
            self.posted += 1

    async def dispatch(
        self: Self,
        user: BasicUser,
        tweet: Tweet,
        records: List[Record],
    ) -> None:
        """
        Dispatch a tweet to the subscription channels.
        """

        self.log.info(
            "Dispatching tweet %r from @%s (%s).", tweet.id, user.screen_name, user.id
        )

        embed = Embed(
            description=tweet.text,
            timestamp=tweet.posted_at,
        )
        embed.set_author(
            url=user.url,
            name=user.name,
            icon_url=user.avatar_url,
        )
        embed.set_footer(
            text=tweet.source,
        )
        for media in tweet.media:
            if media.type in ("photo", "animated_gif"):
                embed.set_image(url=media.url)
                break

        for record in records:
            embed.color = Color.dark_embed()

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

            elif tweet.possibly_sensitive and not channel.is_nsfw():
                continue

            with suppress(HTTPException):

                media = get(tweet.media, type="video")
                if media:
                    file = await media.to_file()
                    if len(file.fp.read()) <= channel.guild.filesize_limit and len(
                        file.fp.read()
                    ):
                        await channel.send(
                            embed=embed,
                            file=file,
                            allowed_mentions=AllowedMentions.all(),
                        )
                        continue

                await channel.send(
                    embed=embed,
                    allowed_mentions=AllowedMentions.all(),
                )
