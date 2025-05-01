from __future__ import annotations

import re
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Literal,
    Optional,
)

from aiohttp import ClientSession
from discord import (
    Asset,
    Forbidden,
    HTTPException,
    Member,
    Message,
    NotFound,
    User,
)
from discord.ext.commands import (
    BadArgument,
    CommandError,
    Converter,
    MemberConverter,
    MemberNotFound,
    UserConverter,
    UserNotFound,
)
from yarl import URL

if TYPE_CHECKING:
    from greed.framework import Greed, Context


MEDIA_URL_PATTERN = re.compile(
    r"(?:http\:|https\:)?\/\/.*\.(?P<mime>png|jpg|jpeg|webp|gif|mp4|mp3|mov|wav|ogg|zip)"
)


class PartialAttachment:
    url: str
    buffer: bytes
    filename: str
    content_type: Optional[str]

    def __init__(
        self,
        url: URL | Asset | str,
        buffer: bytes,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ):
        self.url = str(url)
        self.buffer = buffer
        self.extension = (
            content_type.split("/")[-1]
            if content_type
            else "bin"
        )
        self.filename = (
            filename or f"unknown.{self.extension}"
        )
        self.content_type = content_type

    def __str__(self) -> str:
        return self.filename

    def is_image(self) -> bool:
        return (
            self.content_type.startswith("image")
            if self.content_type
            else False
        )

    def is_video(self) -> bool:
        return (
            self.content_type.startswith("video")
            if self.content_type
            else False
        )

    def is_audio(self) -> bool:
        return (
            self.content_type.startswith("audio")
            if self.content_type
            else False
        )

    def is_gif(self) -> bool:
        return (
            self.content_type == "image/gif"
            if self.content_type
            else False
        )

    def is_archive(self) -> bool:
        return (
            self.content_type.startswith("application")
            if self.content_type
            else False
        )

    @staticmethod
    async def read(url: URL | str) -> tuple[bytes, str]:
        async with ClientSession() as client:
            async with client.get(url) as resp:
                if (
                    resp.content_length
                    and resp.content_length
                    > 50 * 1024 * 1024
                ):
                    raise CommandError(
                        "Attachment exceeds the decompression limit!"
                    )

                elif resp.status == 200:
                    buffer = await resp.read()
                    return (buffer, resp.content_type)

                elif resp.status == 404:
                    raise NotFound(resp, "asset not found")

                elif resp.status == 403:
                    raise Forbidden(
                        resp, "cannot retrieve asset"
                    )

                else:
                    raise HTTPException(
                        resp, "failed to get asset"
                    )

    @classmethod
    def get_attachment(
        cls, message: Message
    ) -> Optional[str]:
        if message.attachments:
            return message.attachments[0].url

        elif message.stickers:
            return message.stickers[0].url

        elif message.embeds:
            if message.embeds[0].image:
                return message.embeds[0].image.url

            elif message.embeds[0].thumbnail:
                return message.embeds[0].thumbnail.url

    @classmethod
    async def convert(
        cls, ctx: Context, argument: str
    ) -> "PartialAttachment":
        try:
            member = await MemberConverter().convert(
                ctx, argument
            )
        except CommandError:
            pass
        else:
            buffer, content_type = await cls.read(
                member.display_avatar.url
            )
            return cls(
                member.display_avatar,
                buffer,
                None,
                content_type,
            )

        if not MEDIA_URL_PATTERN.match(argument):
            raise BadArgument(
                "The provided **URL** couldn't be validated!"
            )

        url = argument
        buffer, content_type = await cls.read(url)
        return cls(url, buffer, None, content_type)

    @classmethod
    async def fallback(
        cls, ctx: Context
    ) -> "PartialAttachment":
        attachment_url: Optional[str] = None

        if ctx.replied_message:
            attachment_url = cls.get_attachment(
                ctx.replied_message
            )

        else:
            async for message in ctx.channel.history():
                attachment_url = cls.get_attachment(message)
                if attachment_url:
                    break

        if not attachment_url:
            raise BadArgument(
                "You must provide an attachment!"
            )

        buffer, content_type = await cls.read(
            attachment_url
        )
        return cls(
            attachment_url,
            buffer,
            f"{ctx.author.id}.{attachment_url.split('.')[-1].split('?')[0]}",
            content_type,
        )
