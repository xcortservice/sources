import json
import re
from typing import Any, Dict, List, Optional, Union

from data.variables import YOUTUBE_WILDCARD
from discord import Client, Message
from pydantic import BaseModel
from system.worker import offloaded

from .models.response import YouTubeVideo


@offloaded
def download(
    url: str, length_limit: Optional[int] = None, download: Optional[bool] = False
) -> dict:
    from pytubefix import Channel, YouTube
    from quantulum3 import parser
    from tuuid import tuuid

    try:
        from .models.data import YouTubeResponse
    except ImportError:
        from models.data import YouTubeResponse
    data = {}

    def format_value(value: str) -> int:
        return int(parser.parse(value)[0].value * 1_000)

    video = YouTube(url)
    info = YouTubeResponse(**video.vid_info)
    details = info.videoDetails
    if length_limit:
        if int(details.lengthSeconds) >= int(length_limit):
            raise Exception(f"video is longer than {length_limit} seconds")
    channel = Channel(f"https://youtube.com/channel/{details.channelId}")
    c = {
        "name": channel.channel_name,
        "id": channel.channel_id,
        "url": channel.vanity_url
        or f"https://youtube.com/channel/{channel.channel_id}",
    }
    avatars = sorted(
        channel.initial_data["header"]["pageHeaderRenderer"]["content"][
            "pageHeaderViewModel"
        ]["image"]["decoratedAvatarViewModel"]["avatar"]["avatarViewModel"]["image"][
            "sources"
        ],
        key=lambda x: x["width"] + x["height"],
        reverse=True,
    )
    metadata = channel.initial_data["header"]["pageHeaderRenderer"]["content"][
        "pageHeaderViewModel"
    ]["metadata"]["contentMetadataViewModel"]["metadataRows"]
    row = metadata[-1]
    try:
        subscribers = format_value(
            row["metadataParts"][0]["text"]["content"].split(" ", 1)[0]
        )
    except Exception:
        subscribers = 0
    try:
        videos = format_value(
            row["metadataParts"][1]["text"]["content"].split(" ", 1)[0]
        )
    except Exception:
        videos = 0
    try:
        likes = format_value(
            video.initial_data["contents"]["twoColumnWatchNextResults"]["results"][
                "results"
            ]["contents"][0]["videoPrimaryInfoRenderer"]["videoActions"][
                "menuRenderer"
            ][
                "topLevelButtons"
            ][
                0
            ][
                "segmentedLikeDislikeButtonViewModel"
            ][
                "likeButtonViewModel"
            ][
                "likeButtonViewModel"
            ][
                "toggleButtonViewModel"
            ][
                "toggleButtonViewModel"
            ][
                "defaultButtonViewModel"
            ][
                "buttonViewModel"
            ][
                "title"
            ]
        )
    except Exception:
        likes = 0
    try:
        v = video.initial_data["engagementPanels"][0][
            "engagementPanelSectionListRenderer"
        ]["header"]["engagementPanelTitleHeaderRenderer"]["contextualInfo"]["runs"][0][
            "text"
        ]
        try:
            comments = int(v)
        except Exception:
            comments = format_value(v)
    except Exception:
        comments = 0
    statistics = {"likes": likes, "comments": comments}
    c["avatar"] = avatars[0]
    c["statistics"] = {
        "subscribers": subscribers,
        "videos": videos,
        "views": channel.views,
    }
    c["description"] = channel.description
    downloadAddr = video.streams.get_highest_resolution()
    if download:
        data["file"] = downloadAddr.download("files/videos", filename=f"{tuuid()}.mp4")
    filesize = downloadAddr.filesize_approx
    downloadAddr = downloadAddr.url
    for key, value in details.dict().items():
        if key == "thumbnail":
            data["thumbnails"] = value.get("thumbnails", [])
        elif key == "shortDescription":
            if not data.get("description"):
                data["description"] = value
            else:
                data["description"] = value
        elif key == "viewCount":
            statistics["views"] = int(value)
        elif key == "lengthSeconds":
            data["length"] = int(value)
        elif key in ("channelId", "author"):
            continue
        else:
            data[key] = value
    data["statistics"] = statistics
    data["downloadAddr"] = downloadAddr
    data["filesize"] = filesize
    data["channel"] = c
    return data


async def extract(content: str, *args: Any, **kwargs: Any):
    if not (match := YOUTUBE_WILDCARD.search(content)):
        return None
    data = await download(match.string, *args, **kwargs)
    return YouTubeVideo(**data)


def repost(bot: Client, message: Message) -> Optional[str]:
    if not (match := YOUTUBE_WILDCARD.search(message.content)):
        return None
    else:
        bot.dispatch("youtube_repost", message, match.string)
