from __future__ import annotations

import re

from contextlib import suppress
from typing import (
    TYPE_CHECKING,
    List,
    Literal,
    Optional,
    Tuple,
    TypedDict,
    cast,
)

from discord import (
    ActionRow,
    AllowedMentions,
    ButtonStyle,
    Embed,
    Guild,
    GuildSticker,
    Member,
    Message,
    StandardSticker,
    TextChannel,
    Thread,
    VoiceChannel,
    Webhook,
)
from discord.ui import Button, View
from discord.utils import find, utcnow

from .engine.embed import EmbedBuilder
from .engine.node import Node
from .variables import Block, parse

if TYPE_CHECKING:
    from greed.framework.discord import Context
    from greed.framework import Greed


class ScriptData(TypedDict):
    content: Optional[str]
    embeds: List[Embed]
    view: View
    stickers: List[GuildSticker | StandardSticker]


class Script:
    template: str
    blocks: List[Block | Tuple[str, Block]]
    nodes: List[Node]

    def __init__(
        self,
        template: str,
        blocks: List[Block | Tuple[str, Block]] = [],
    ) -> None:
        self.template = template
        self.blocks = blocks
        self._fixed_template = parse(
            self.template, self.blocks
        )
        self.nodes = Node.find(self._fixed_template)

    def __repr__(self) -> str:
        return f"<Script nodes={len(self.nodes)} {self.template=}>"

    def __str__(self) -> str:
        return self.template

    def __bool__(self) -> bool:
        return bool(
            self.content
            or self.embeds
            or self.view.children
            or self.stickers
        )

    @property
    def fixed_template(self) -> str:
        return self._fixed_template

    @property
    def content(self) -> Optional[str]:
        return self.data["content"]

    @property
    def embeds(self) -> List[Embed]:
        return self.data["embeds"][:10]

    @property
    def view(self) -> View:
        return self.data["view"]

    @property
    def stickers(
        self,
    ) -> List[GuildSticker | StandardSticker]:
        return self.data["stickers"]

    @property
    def format(self) -> Literal["text", "embed", "sticker"]:
        if (
            self.stickers
            and not self.content
            and not self.embeds
        ):
            return "sticker"
        return (
            "text" if not self.data["embeds"] else "embed"
        )

    @classmethod
    async def convert(
        cls, ctx: Context, argument: str
    ) -> Script:
        script = cls(
            argument, [ctx.guild, ctx.channel, ctx.author]
        )
        if not script:
            raise ValueError(
                "Script nodes were not provided"
            )
        return script

    @classmethod
    def from_message(cls, message: Message) -> Script:
        template: List[str] = []

        if message.system_content:
            template.append(
                f"{{content: {message.system_content}}}"
            )

        for embed in message.embeds:
            template.append("{embed}")
            template.extend(
                f"{{{item}: {getattr(value, 'url', value)}}}"
                for item, value in (
                    ("color", embed.color),
                    ("url", embed.url),
                    ("title", embed.title),
                    ("description", embed.description),
                    ("thumbnail", embed.thumbnail),
                    ("image", embed.image),
                )
                if value
            )

            for field in embed.fields:
                _field: List[str] = [
                    field.name,
                    field.value,
                ]  # type: ignore
                if field.inline:
                    _field.append("inline")

                template.append(
                    f"{{field: {' && '.join(_field)}}}"
                )

            if (footer := embed.footer) and footer.text:
                _footer: List[str] = [footer.text]
                if footer.icon_url:
                    _footer.append(footer.icon_url)

                template.append(
                    f"{{footer: {' && '.join(_footer)}}}"
                )

            if (author := embed.author) and author.name:
                _author: List[str] = [
                    author.name,
                    author.url or "null",
                ]
                if author.icon_url:
                    _author.append(author.icon_url)

                template.append(
                    f"{{author: {' && '.join(_author)}}}"
                )

        if message.components:
            for component in message.components:
                if not isinstance(component, ActionRow):
                    continue

                for child in component.children:
                    if not isinstance(child, Button):
                        continue

                    if child.style != ButtonStyle.link:
                        continue

                    label = child.label
                    url = child.url
                    emoji = child.emoji
                    disabled = child.disabled
                    style = child.style.name.lower()

                    template.append(
                        f"{{button: {style} && {label} && {url} && {emoji}{' && disabled' if disabled else ''}}} "
                    )

        return cls("\n".join(template), [])

    @property
    def data(self) -> ScriptData:
        if hasattr(self, "_data"):
            return self._data

        data: ScriptData = {
            "content": None,
            "embeds": [],
            "view": View(),
            "stickers": [],
        }

        for node in self.nodes:
            if node.name in ("content", "message", "msg"):
                data["content"] = node.value

            elif node.name == "timestamp":
                if not data["embeds"]:
                    data["embeds"].append(Embed())
                data["embeds"][-1].timestamp = utcnow()

            elif node.name == "button":
                parts = node.value.split("&&", 5)

                style_map = {
                    "link": ButtonStyle.link,
                    "blurple": ButtonStyle.primary,
                    "blue": ButtonStyle.primary,
                    "primary": ButtonStyle.primary,
                    "green": ButtonStyle.success,
                    "success": ButtonStyle.success,
                    "grey": ButtonStyle.secondary,
                    "gray": ButtonStyle.secondary,
                    "secondary": ButtonStyle.secondary,
                    "red": ButtonStyle.danger,
                    "danger": ButtonStyle.danger,
                }

                first_part = parts[0].strip().lower()
                if first_part in style_map:
                    style_text = first_part
                    label = (
                        parts[1].strip()
                        if len(parts) > 1
                        else ""
                    )
                    url = (
                        parts[2].strip()
                        if len(parts) > 2
                        else ""
                    )
                    emoji = (
                        parts[3].strip()
                        if len(parts) > 3
                        and parts[3].strip()
                        else None
                    )
                    disabled = False
                    if len(parts) > 4:
                        disabled = (
                            "disabled" in parts[4].strip()
                        )
                else:
                    style_text = "link"
                    label = parts[0].strip()
                    url = (
                        parts[1].strip()
                        if len(parts) > 1
                        else ""
                    )
                    emoji = (
                        parts[2].strip()
                        if len(parts) > 2
                        and parts[2].strip()
                        else None
                    )
                    disabled = False
                    if len(parts) > 3:
                        disabled = (
                            "disabled" in parts[3].strip()
                        )

                if not label or not url:
                    continue

                style = style_map.get(
                    style_text, ButtonStyle.link
                )

                if label.startswith("<"):
                    label, emoji = None, label

                with suppress(ValueError):
                    if style == ButtonStyle.link:
                        data["view"].add_item(
                            Button(
                                style=style,
                                label=label,
                                url=url,
                                emoji=emoji,
                                disabled=disabled,
                            )
                        )
                    else:
                        data["view"].add_item(
                            Button(
                                style=style,
                                label=label,
                                custom_id=url,
                                emoji=emoji,
                                disabled=disabled,
                            )
                        )

            elif node.name == "sticker":
                guild = cast(
                    Optional[Guild],
                    find(
                        lambda g: isinstance(g, Guild),
                        self.blocks,
                    ),
                )
                if not guild:
                    continue

                bot = cast(
                    "Greed", guild._state._get_client()
                )
                sticker = find(
                    lambda s: s.name.lower()
                    == node.value.lower(),
                    list(guild.stickers)
                    + list(bot.wumpus_stickers),
                )
                if sticker:
                    data["stickers"].append(sticker)

            else:
                if node.name == "embed":
                    data["embeds"].append(
                        Embed(color=0x1E1F22)
                    )
                elif not data["embeds"]:
                    data["embeds"].append(
                        Embed(color=0x1E1F22)
                    )

                embed = data["embeds"][-1]
                node.value = parse(node.value, self.blocks)
                EmbedBuilder(embed)(node)

        if not any(
            data.get(key) for key in ("content", "embeds")
        ) and not (
            data["view"].children or data["stickers"]
        ):
            data["content"] = self.fixed_template

        data["embeds"] = [
            embed for embed in data["embeds"] if embed
        ]

        self._data = data
        return data

    async def send(
        self,
        channel: Context
        | VoiceChannel
        | TextChannel
        | Thread
        | Webhook
        | Member,
        **kwargs,
    ) -> Message:
        if not isinstance(channel, Webhook):
            kwargs["stickers"] = self.stickers

        if "allowed_mentions" not in kwargs:
            kwargs["allowed_mentions"] = AllowedMentions(
                everyone=False,
                roles=False,
                users=True,
                replied_user=False,
            )

        return await channel.send(
            content=self.content,
            embeds=self.embeds,
            view=self.view,
            **kwargs,
        )

    async def edit(
        self,
        message: Message,
        **kwargs,
    ) -> Message:
        webhook: Optional[Webhook] = kwargs.pop(
            "webhook", None
        )

        if "allowed_mentions" not in kwargs:
            kwargs["allowed_mentions"] = AllowedMentions(
                everyone=False,
                roles=False,
                users=True,
                replied_user=False,
            )

        if webhook:
            return await webhook.edit_message(
                message.id,
                content=self.content,
                embeds=self.embeds,
                **kwargs,
            )

        return await message.edit(
            content=self.content,
            embeds=self.embeds,
            view=self.view,
            **kwargs,
        )
