import asyncio
import datetime
import os
from contextlib import asynccontextmanager, contextmanager, suppress
from datetime import timezone
from io import BytesIO
from pathlib import Path
from typing import (Any, AsyncGenerator, Generator, List, Literal, Optional,
                    Union)

import httpx
import humanize
import tuuid
from anyio import Path as AsyncPath
from DataProcessing.models.Instagram.raw_post import (  # type: ignore
    InstagramPost, Item)
from discord import Color, Embed, File
from loguru import logger as log
from system.patch.context import Context
from system.worker import offloaded
from tornado.httpclient import HTTPClientError as CurlError  # noqa

from .curl import get_curl
from .file_types import guess_extension

axel_sem = asyncio.BoundedSemaphore(16)

cache_path = "/root/honest/bot/cache"


def to_embed(self: Item, ctx: Context) -> Union[Embed, List[Embed]]:
    embed = Embed(description=self.caption.text, color=Color.from_str("#DD829B"))
    embed.set_author(
        name=f"{str(self.owner.full_name)} (@{str(self.owner.username)})",
        icon_url=self.owner.profile_pic_url
        or "https://eros.rest/static/Default_pfp.jpg",
    )
    icon_url = (
        "https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png"
    )
    footer_text = f"""❤️ {self.like_count.humanize() if self.like_count else 0} 👀 {self.play_count.humanize() if self.play_count else 0} 💬 {self.comment_count.humanize() if self.comment_count else 0} ∙ {str(ctx.author)} ∙ {humanize.naturaltime(datetime.datetime.fromtimestamp(self.taken_at, tz=timezone.utc), when = datetime.datetime.now(tz=timezone.utc))}"""
    if self.media_type == 8:
        embeds = []
        for i, media in enumerate(self.carousel_media, start=1):
            e = embed.copy()
            e.set_image(url=media.image_versions2.candidates[0].url)
            e.set_footer(
                text=f"{footer_text} ∙ Page {i}/{len(self.carousel_media)}",
                icon_url=icon_url,
            )
            embeds.append(e)
        return embeds
    elif self.media_type == 2:
        embed.set_footer(text=footer_text, icon_url=icon_url)
        return embed
    else:
        embed.set_image(url=self.image_versions2.candidates[0].url)
        embed.set_footer(text=footer_text, icon_url=icon_url)
        return embed


Item.to_embed = to_embed


@offloaded
def read_file(path: str, mode: Optional[str] = "rb"):
    with open(path, mode) as file:
        data = file.read()
    return file


@offloaded
def write_file(path: str, mode: str, data: Any):
    with open(path, mode) as file:
        file.write(data)
    return


async def post_to_message(ctx: Context, post: InstagramPost):
    post = post.items[0]
    embed = post.to_embed(ctx)
    if post.media_type == 2:
        video_url = post.video_versions[0].url
        path = await download_data(video_url)
        filename = guess_extension(video_url)
        file = File(fp=BytesIO(path), filename=filename.name)
        return await ctx.send(embed=embed, file=file)
    elif post.media_type == 1:
        return await ctx.send(embed=embed)
    elif post.media_type == 8:
        return await ctx.paginate(embed)
    else:
        return await ctx.fail("That post has no **MEDIA**")


@asynccontextmanager
async def borrow_temp_file(
    base="/tmp", extension=None
) -> AsyncGenerator[Union[AsyncPath, None], None]:
    if not extension:
        extension = ""
    file = AsyncPath(f"{base}/{tuuid.tuuid()}{extension}")
    try:
        yield file
    finally:
        await file.unlink(missing_ok=True)


@contextmanager
def borrow_temp_file_sync(base="/tmp", extension=None) -> Generator[Path, None, None]:
    from pathlib import Path

    if not extension:
        extension = ""
    file = Path(f"{base}/{tuuid.tuuid()}{extension}")
    try:
        yield file
    finally:
        file.unlink(missing_ok=True)


async def get_standard_avatar():
    return "https://eros.rest/static/Default_pfp.jpg"


async def delete_asset(file_path: str, ttl: int):
    await asyncio.sleep(ttl)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False


async def download_data(url: str):
    if url.startswith("https://scontent.cdninstagram.com/v/") and "mp4" in url:
        download_data = await axel_fetch(url)
    else:
        download_data = await fetch_standard(url)
    return download_data


async def redistribute_asset(url: str, ttl: int, wait: Optional[bool] = True) -> str:
    async def download(url: str, path: str):
        if url.startswith("https://scontent.cdninstagram.com/v/") and "mp4" in url:
            download_data = await axel_fetch(url)
        else:
            download_data = await fetch_standard(url)
        await write_file(path, "wb", download_data)
        return True

    file_type = guess_extension(url)
    extension = file_type.extension
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    path = f"{cache_path}/{file_type.name}"
    if wait is False:
        asyncio.ensure_future(download(url, path))
    else:
        await download(url, path)
    asyncio.ensure_future(delete_asset(path, ttl))
    return path


async def fetch_standard(url):
    htx = httpx.AsyncClient()
    curl = get_curl()
    try:
        r = await curl.fetch(url)
        return bytes(r.body)
    except CurlError as e:
        if e.code == 410:
            log.warning("HTTP GONE for {} - Returning standard avatar", url)
            return await get_standard_avatar()
        log.warning("Curl failed: {} - retrying...", e)
        r = await htx.get(url)
        r.raise_for_status()
        return bytes(r.content)


async def axel_fetch(url: str) -> bytes:
    async with borrow_temp_file() as tmp, axel_sem:
        proc = await asyncio.create_subprocess_exec(
            "axel",
            *["-n", "3", "--quiet", "--output", str(tmp), url],
            stdout=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        return await tmp.read_bytes()
