import asyncio
import datetime
import typing
from collections import deque

import discord

from system.classes.exceptions import SnipeError


class Snipe(object):
    def __init__(self: "Snipe", bot: discord.Client):
        self.bot = bot
        self.data = {}

    async def add_entry(
        self: "Snipe", type: str, message: typing.Union[discord.Message, tuple]
    ):
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
                "message": message[1].message.jump_url,
                "reaction": (
                    str(message[1]) if message[1].is_custom_emoji() else str(message[1])
                ),
                "author": {
                    "id": message[0].id,
                    "name": message[0].name,
                    "avatar": message[0].display_avatar.url,
                },
            }
            message = message[1].message
        if type.lower() == "snipe":
            if f"s-{message.channel.id}" not in self.data.keys():
                self.data[f"s-{message.channel.id}"] = deque(maxlen=100)
            else:
                if len(self.data[f"s-{message.channel.id}"]) == 100:
                    self.data[f"s-{message.channel.id}"].pop()
            self.data[f"s-{message.channel.id}"].insert(0, entry)
        elif type.lower() == "editsnipe":
            if f"es-{message.channel.id}" not in self.data.keys():
                self.data[f"es-{message.channel.id}"] = deque(maxlen=100)
            else:
                if len(self.data[f"es-{message.channel.id}"]) == 100:
                    self.data[f"es-{message.channel.id}"].pop()
            self.data[f"es-{message.channel.id}"].insert(0, entry)
        else:
            if f"rs-{message.channel.id}" not in self.data.keys():
                self.data[f"rs-{message.channel.id}"] = deque(maxlen=100)
            else:
                if len(self.data[f"rs-{message.channel.id}"]) == 100:
                    self.data[f"rs-{message.channel.id}"].pop()
            self.data[f"rs-{message.channel.id}"].insert(0, entry)

        return entry

    async def add_reaction_history(
        self, payload: discord.RawReactionActionEvent
    ) -> bool:
        if payload.user_id == self.bot.user.id:
            return
        guild_id = int(payload.guild_id)
        message_id = int(payload.message_id)
        channel_id = int(payload.channel_id)
        emoji = str(payload.emoji)
        ts = datetime.datetime.now()
        await self.bot.db.execute(
            """INSERT INTO reaction_history (guild_id, channel_id, message_id, reaction, user_id, ts) VALUES($1, $2, $3, $4, $5, $6) ON CONFLICT(guild_id, channel_id, message_id, reaction, user_id) DO UPDATE SET ts = excluded.ts""",
            guild_id,
            channel_id,
            message_id,
            emoji,
            int(payload.user_id),
            ts,
        )
        return True

    async def get_entry(
        self: "Snipe", channel: discord.TextChannel, type: str, index: int
    ):
        if type.lower() == "snipe":
            if data := self.data.get(f"s-{channel.id}"):
                if len(data) < index - 1:
                    raise SnipeError(
                        f"There are **not** `{index}` **deleted messages**"
                    )
                try:
                    return (data[index - 1], len(data))
                except Exception:
                    raise SnipeError(
                        f"There are **not** `{index}` **deleted messages**"
                    )

            else:
                raise SnipeError(
                    f"There are **no deleted messages** in {channel.mention}"
                )
        elif type.lower() == "editsnipe":
            if data := self.data.get(f"es-{channel.id}"):
                if len(data) < index - 1:
                    raise SnipeError(
                        f"There are **not** `{index}` **edits made** recently"
                    )
                try:
                    return (data[index - 1], len(data))
                except Exception:
                    raise SnipeError(
                        f"There are **not** `{index}` **deleted messages**"
                    )
            else:
                raise SnipeError(
                    f"There are **no messages edited** in {channel.mention}"
                )
        else:
            if data := self.data.get(f"rs-{channel.id}"):
                if len(data) < index - 1:
                    raise SnipeError(
                        f"There has **not** been `{index}` **reactions removed** recently"
                    )
                try:
                    return (data[index - 1], len(data))
                except Exception:
                    raise SnipeError(
                        f"There has **not** been `{index}` **reactions removed**"
                    )
            else:
                raise SnipeError(
                    f"There are **no reaction removals** for **{channel.mention}**"
                )

    async def delete_entry(
        self: "Snipe", channel: discord.TextChannel, type: str, index: int
    ):
        if type.lower() == "snipe":
            if data := self.data.get(f"s-{channel.id}"):
                self.data[f"s-{channel.id}"].remove(data[index - 1])
            else:
                raise SnipeError(f"There are **not** `{index}` **deleted messages**")
        elif type.lower() == "editsnipe":
            if data := self.data.get(f"es-{channel.id}"):
                self.data[f"es-{channel.id}"].remove(data[index - 1])
            else:
                raise SnipeError(f"There are **not** `{index}` **edits made** recently")
        else:
            if data := self.data.get(f"rs-{channel.id}"):
                self.data[f"rs-{channel.id}"].remove(data[index - 1])
            else:
                raise SnipeError(
                    f"There has **not** been `{index}` **reactions removed** recently"
                )

    async def clear_entries(self: "Snipe", channel: discord.TextChannel):
        async def pop_entry(f: str, channel: discord.TextChannel):
            try:
                self.data.pop(f"{f}{channel.id}")
            except Exception:
                pass

        await asyncio.gather(*[pop_entry(f, channel) for f in ["s-", "es-", "rs-"]])
        return True
