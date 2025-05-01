from __future__ import annotations

import re
from logging import getLogger
from typing import List, Optional

from aiohttp import ClientSession
from cashews import cache
from discord.ext.commands import CommandError
from pydantic import BaseModel
from system.worker import offloaded
from typing_extensions import Self

cache.setup("mem://")


@offloaded
def get_youtube_channel(url: str):
    import orjson
    from pytubefix import Channel
    from quantulum3 import parser

    def format_value(value: str) -> int:
        return int(parser.parse(value)[0].value * 1_000)

    c = Channel(url)
    metadata = c.initial_data["header"]["pageHeaderRenderer"]["content"][
        "pageHeaderViewModel"
    ]["metadata"]["contentMetadataViewModel"]["metadataRows"]
    row = metadata[-1]
    try:
        subscribers = format_value(
            row["metadataParts"][0]["text"]["content"].split(" ", 1)[0]
        )
    except Exception:
        subscribers = 0
    return orjson.dumps(
        {
            "id": c.channel_id,
            "name": c.channel_name,
            "description": c.description,
            "avatarUrl": c.thumbnail_url,
            "subscriberCount": subscribers,
        }
    )


@cache(ttl=1600, key="get_channel:{url}")
async def get_channel(url: str):
    return await get_youtube_channel(url)


log = getLogger("feeds/youtube")

CHANNEL_LOOKUPS = {
    "BY_ID": "https://pipedapi.kavin.rocks/channel/",
    "BY_USERNAME": "https://pipedapi.kavin.rocks/c/",
}

REGEXES = [
    re.compile(r"channel/([a-zA-Z0-9_-]+)"),  # Matches channel URLs
    re.compile(r"c/([a-zA-Z0-9_-]+)"),  # Matches custom URLs (short form)
    re.compile(r"user/([a-zA-Z0-9_-]+)"),  # Matches legacy user URLs
    re.compile(r"@([a-zA-Z0-9_-]+)"),
    re.compile(
        r"^https:\/\/(?:www\.)?youtube\.com\/([a-zA-Z0-9_-]+)$"
    ),  # Matches YouTube handles
]


class RelatedStream(BaseModel):
    url: Optional[str] = None
    type: Optional[str] = None
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    uploaderName: Optional[str] = None
    uploaderUrl: Optional[str] = None
    uploaderAvatar: None = None
    uploadedDate: Optional[str] = None
    shortDescription: Optional[str] = None
    duration: Optional[int] = None
    views: Optional[int] = None
    uploaded: Optional[int] = None
    uploaderVerified: Optional[bool] = None
    isShort: Optional[bool] = None


class Tab(BaseModel):
    name: Optional[str] = None
    data: Optional[str] = None


class YouTubeChannel(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    avatarUrl: Optional[str] = None
    description: Optional[str] = None
    # nextpage: Optional[str] = None
    subscriberCount: Optional[int] = None
    # verified: Optional[bool] = None
    # relatedStreams: Optional[List[RelatedStream]] = None
    # tabs: Optional[List[Tab]] = None

    @property
    def url(self) -> str:
        return f"https://youtube.com/channel/{self.id}"

    @classmethod
    async def from_url(cls, url: str) -> Optional[Self]:
        snowflake = None
        for r in REGEXES:
            if match := r.search(url):
                snowflake = match.group(1)
                log.info(f"got match {match} for URL {url}")
                break
            else:
                log.info(f"couldn't get a match for URL {url}")
        if not snowflake:
            raise ValueError("Invalid channel snowflake provided")
        try:
            data = await get_channel(url)
        except Exception as e:
            log.error(f"Failed to get channel data for {url}: {e}")
            raise CommandError("Invalid YouTube Channel URL provided")
        return cls.parse_raw(data)

    @classmethod
    async def from_id(cls, channel_id: str) -> Optional[Self]:
        try:
            data = await get_channel(f"https://youtube.com/channel/{channel_id}")
            return cls.parse_raw(data)
        except Exception as e:
            log.error(f"Failed to get channel data for {channel_id}: {e}")
            raise CommandError("Invalid YouTube Channel ID provided")
        async with ClientSession() as session:
            async with session.get(
                f"{CHANNEL_LOOKUPS['BY_ID']}{channel_id}"
            ) as response:
                data = await response.read()
        return cls.parse_raw(data)
