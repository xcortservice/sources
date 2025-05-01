import re
from asyncio import ensure_future
from io import BytesIO
from os import remove
from typing import List

from aiohttp import ClientSession
from data.variables import INSTAGRAM_POST
from DataProcessing.services.TT.models.post import \
    TikTokPostResponse  # type: ignore
from discord import (Client, Color, Embed, File, Guild, Member, Message,
                     TextChannel, Thread, User)
from discord.ext.commands import (Cog, CommandError, command, group,
                                  has_permissions)
from loguru import logger
from system.patch.context import Context
from system.services.media.video import compress
from system.services.socials.YouTube.main import download, extract
from tools import timeit
from unidecode_rs import decode as unidecode_rs

from .feeds import FEEDS, Feed
from .util import post_to_message


async def to_message(self: TikTokPostResponse, ctx: Context):
    embed = Embed(
        description=unidecode_rs(
            self.itemInfo.itemStruct.contents[0].desc
            if self.itemInfo.itemStruct.contents
            else ""
        ),
        color=Color.from_str("#00001"),
    )
    embed.set_author(
        name=self.itemInfo.itemStruct.author.uniqueId,
        icon_url=self.itemInfo.itemStruct.author.avatarLarger,
    )
    footer_text = f"""❤️ {self.itemInfo.itemStruct.statsV2.diggCount.humanize() if self.itemInfo.itemStruct.statsV2.diggCount else 0} 👀 {self.itemInfo.itemStruct.statsV2.playCount.humanize() if self.itemInfo.itemStruct.statsV2.playCount else 0} 💬 {self.itemInfo.itemStruct.statsV2.commentCount.humanize() if self.itemInfo.itemStruct.statsV2.commentCount else 0} ∙ {str(ctx.author)}"""
    if self.itemInfo.itemStruct.imagePost:
        embeds = []
        total = len(self.itemInfo.itemStruct.imagePost.images)
        for i, image in enumerate(self.itemInfo.itemStruct.imagePost.images, start=1):
            e = embed.copy()
            e.set_footer(
                text=f"{footer_text} ∙ Page {i}/{total}",
                icon_url="https://seeklogo.com/images/T/tiktok-icon-logo-1CB398A1BD-seeklogo.com.png",
            )
            e.set_image(url=image.imageURL)
            embeds.append(e)
        return await ctx.paginate(embeds)
    else:
        if self.itemInfo.itemStruct.video:
            embed.set_footer(
                text=footer_text,
                icon_url="https://seeklogo.com/images/T/tiktok-icon-logo-1CB398A1BD-seeklogo.com.png",
            )
            logger.info(self.itemInfo.itemStruct.video.playAddr)
            async with ClientSession() as session:
                async with session.get(
                    self.itemInfo.itemStruct.video.playAddr,
                    **await ctx.bot.services.tiktok.tt.get_tiktok_headers(),
                ) as response:
                    data = await response.read()
            file = File(fp=BytesIO(data), filename="tiktok.mp4")
            return await ctx.send(file=file, embed=embed)
        else:
            return await ctx.fail("TikTok returned **malformed** content")


TikTokPostResponse.to_message = to_message


class SocialEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.tiktok_regexes = [
            re.compile(
                r"(?:http\:|https\:)?\/\/(?:www\.)?tiktok\.com\/@.*\/(?:photo|video)\/\d+"
            ),
            re.compile(
                r"(?:http\:|https\:)?\/\/(?:www|vm|vt|m).tiktok\.com\/(?:t/)?(\w+)"
            ),
        ]
        self.feeds: List[Feed] = []

    async def cog_load(self):
        for feed in FEEDS:
            self.feeds.append(feed(self.bot))

    async def cog_unload(self):
        for feed in self.feeds:
            await feed.stop()

    @Cog.listener("on_media_repost")
    async def repost_check(self, ctx: Context):
        if results := INSTAGRAM_POST.findall(ctx.message.content):
            return self.bot.dispatch("instagram_repost", ctx, results[0])
        for i, reg in enumerate(self.tiktok_regexes, start=1):
            for content in ctx.message.content.split():
                if match := reg.match(content):
                    url = str(match.string)
                    logger.info(url)
                    return self.bot.dispatch("tiktok_repost", ctx, url)

    @Cog.listener("on_youtube_repost")
    async def youtube_repost(self, message: Message, url: str):
        async with timeit() as timer:
            post = await extract(url, download=True)
        logger.info(f"downloading youtube post took {timer.elapsed} seconds")
        if not post:
            return
        embed = (
            Embed(
                description=f"[{post.title}]({url})",
            )
            .set_author(
                name=f"{post.channel.name}",
                icon_url=post.channel.avatar.url,
                url=post.channel.url,
            )
            .set_footer(
                text=f"💬 {post.statistics.comments.humanize()} comments | 👀 {post.statistics.views.humanize()} views | ❤️ {post.statistics.likes.humanize()}"
            )
        )

        if post.filesize >= message.guild.filesize_limit:
            await compress(post.file, message.guild.filesize_limit)
        file = File(post.file)
        await message.channel.send(embed=embed, file=file)
        remove(post.file)
        return await message.delete()

    @Cog.listener("on_tiktok_repost")
    async def tiktok_repost(self, ctx: Context, url: str):
        post = await self.bot.services.tiktok.fetch_post(url)
        return await post.to_message(ctx)

    @Cog.listener("on_instagram_repost")
    async def instagram_repost(self, ctx: Context, url: str):
        try:
            post = await self.bot.services.instagram.get_post(str(url))
            if post:
                return await post_to_message(ctx, post)
        except Exception as e:
            await ctx.fail("Failed to Fetch Post")
            raise e


async def setup(bot: Client):
    await bot.add_cog(SocialEvents(bot))
