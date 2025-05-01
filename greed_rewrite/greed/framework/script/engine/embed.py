from contextlib import suppress
from inspect import ismethod
from typing import Callable

from discord import Embed

from .node import Node

__all__ = ("EmbedBuilder",)


class EmbedBuilder:
    embed: Embed

    def __init__(self, embed: Embed) -> None:
        self.embed = embed

    def __call__(self, node: Node) -> Embed:
        try:
            func: Callable[[Node], None] = getattr(
                self, node.name.replace(".", "_")
            )
        except AttributeError:
            return self.embed

        if ismethod(func):
            func(node)

        return self.embed

    def color(self, node: Node) -> None:
        with suppress(ValueError):
            self.embed.color = int(
                node.value.lstrip("#"), 16
            )

    def url(self, node: Node) -> None:
        self.embed.url = node.value

    def title(self, node: Node) -> None:
        self.embed.title = node.value

    def description(self, node: Node) -> None:
        self.embed.description = node.value

    def thumbnail(self, node: Node) -> Embed:
        if node.value.lower() in {
            "none",
            "null",
            "false",
            "",
        }:
            return self.embed

        return self.embed.set_thumbnail(url=node.value)

    def image(self, node: Node) -> Embed:
        if node.value.lower() in {
            "none",
            "null",
            "false",
            "",
        }:
            return self.embed

        return self.embed.set_image(url=node.value)

    def field(self, node: Node) -> None:
        parts = node.value.split("&&", 3)
        if len(parts) < 2:
            return

        name, value = map(str.strip, parts[:2])
        inline = len(parts) >= 3 or "inline" in value
        if "inline" in value:
            value = value.replace("inline", "").strip()

        self.embed.add_field(
            name=name, value=value, inline=inline
        )

    def footer(self, node: Node) -> None:
        parts = node.value.split("&&", 2)
        if not parts:
            return

        text = parts[0].strip()
        icon_url = (
            parts[1].strip() if len(parts) >= 2 else None
        )
        self.embed.set_footer(text=text, icon_url=icon_url)

    def author(self, node: Node) -> None:
        parts = node.value.split("&&", 3)
        if not parts:
            return

        name = parts[0].strip()
        icon_url = (
            parts[1].strip() if len(parts) >= 2 else None
        )
        url = parts[2].strip() if len(parts) >= 3 else None

        if icon_url in {"none", "null", "false", ""}:
            icon_url = None

        self.embed.set_author(
            name=name, url=url, icon_url=icon_url
        )

    def author_url(self, node: Node) -> None:
        self.embed.set_author(
            name=self.embed.author.name,
            url=node.value,
            icon_url=self.embed.author.icon_url,
        )

    def author_icon(self, node: Node) -> None:
        self.embed.set_author(
            name=self.embed.author.name,
            url=self.embed.author.url,
            icon_url=node.value,
        )
