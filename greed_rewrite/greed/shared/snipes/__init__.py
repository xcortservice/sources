import discord
import datetime
import typing
import asyncio
from collections import deque
from discord.ext import commands


class SnipeError(commands.errors.CommandError):
    def __init__(self, message: str, **kwargs):
        super().__init__(message)
        self.kwargs = kwargs


class Snipe:
    def __init__(self, bot):
        self.bot = bot
        self.data: dict[str, deque] = {}

    async def add_entry(self, type: str, message: typing.Union[discord.Message, tuple]) -> dict:
        if isinstance(message, discord.Message):
            entry: dict = {
                "timestamp": message.created_at.timestamp(),
                "content": message.content,
                "embeds": [
                    embed.to_dict()
                    for embed in message.embeds[:8]
                    if not embed.type == "image" and not embed.type == "video"
                ],
                "attachments": [
                    attachment.proxy_url
                    for attachment in (
                        message.attachments
                        + list(
                            (embed.thumbnail or embed.image)
                            for embed in message.embeds
                            if embed.type == "image"
                        )
                    )
                ],
                "stickers": [sticker.url for sticker in message.stickers],
                "author": {
                    "id": message.author.id,
                    "name": message.author.name,
                    "avatar": message.author.display_avatar.url,
                },
            }
        else:
            entry: dict = {
                "timestamp": datetime.datetime.now().timestamp(),
                "message": message[0].message.jump_url,
                "reaction": (
                    str(message[0].emoji)
                    if message[0].is_custom_emoji()
                    else str(message[0].emoji)
                ),
                "author": {
                    "id": message[1].id,
                    "name": message[1].name,
                    "avatar": message[1].display_avatar.url,
                },
            }

        key = f"{type.lower()}-{message.channel.id if isinstance(message, discord.Message) else message[0].message.channel.id}"
        if key not in self.data:
            self.data[key] = deque(maxlen=100)
        elif len(self.data[key]) == 100:
            self.data[key].pop()
        self.data[key].insert(0, entry)
        return entry

    async def get_entry(self, channel: discord.TextChannel, type: str, index: int) -> tuple[dict, int]:
        key = f"{type.lower()}-{channel.id}"
        if data := self.data.get(key):
            if len(data) < index:
                raise SnipeError(f"There are **not** `{index}` **deleted messages**")
            try:
                return (data[index - 1], len(data))
            except Exception:
                raise SnipeError(f"There are **not** `{index}` **deleted messages**")
        else:
            return None

    async def delete_entry(self, channel: discord.TextChannel, type: str, index: int) -> None:
        key = f"{type.lower()}-{channel.id}"
        if data := self.data.get(key):
            self.data[key].remove(data[index - 1])
        else:
            raise SnipeError(f"There are **not** `{index}` **deleted messages**")

    async def clear_entries(self, channel: discord.TextChannel) -> bool:
        async def pop_entry(f: str, channel: discord.TextChannel) -> None:
            try:
                self.data.pop(f"{f}{channel.id}")
            except Exception:
                pass

        await asyncio.gather(*[pop_entry(f, channel) for f in ["s-", "es-", "rs-"]])
        return True 