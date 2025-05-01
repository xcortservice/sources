from typing import Any, Dict, List, Optional, Union

from aiohttp import ClientSession
from pydantic import BaseModel


class VideoThumbnail(BaseModel):
    """Thumbnails for the video in different sizes"""

    url: str
    width: int
    height: int


class VideoStatistics(BaseModel):
    """Statistics of the post"""

    likes: Optional[int] = 0
    views: Optional[int] = 0
    comments: Optional[int] = 0


class AuthorStatistics(BaseModel):
    """Statistics of the author"""

    subscribers: Optional[int] = 0
    videos: Optional[int] = 0
    views: Optional[int] = 0


class AuthorAvatar(BaseModel):
    url: str
    width: int
    height: int


class VideoAuthor(BaseModel):
    """The author of the video"""

    name: str
    id: str
    url: str
    avatar: Optional[AuthorAvatar] = None
    statistics: AuthorStatistics
    description: str


class YouTubeVideo(BaseModel):
    """YouTube video object"""

    videoId: str
    title: str
    length: int
    isOwnerViewing: Optional[bool] = False
    description: str
    isCrawlable: Optional[bool] = False
    thumbnails: Optional[List[VideoThumbnail]] = None
    allowRatings: Optional[bool] = False
    isPrivate: Optional[bool] = False
    isUnpluggedCorpus: Optional[bool] = False
    isLiveContent: Optional[bool] = False
    statistics: VideoStatistics
    downloadAddr: str
    filesize: int
    file: Optional[str] = None
    channel: VideoAuthor

    async def get_file_data(self) -> bytes:
        async with ClientSession() as session:
            async with session.get(self.downloadAddr) as response:
                data = await response.read()
        return data
