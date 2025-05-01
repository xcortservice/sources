from __future__ import annotations

import asyncio
from contextlib import suppress
from math import ceil
from typing import (
    TYPE_CHECKING,
    Any,
    List,
    Optional,
    TypedDict,
    Union,
    cast,
)

from discord import (
    ButtonStyle,
    Embed,
    HTTPException,
    Interaction,
    Message,
)
from discord.ui import Button, View
from discord.utils import as_chunks

if TYPE_CHECKING:
    from greed.framework.discord import Context


class EmbedField(TypedDict):
    name: str
    value: str
    inline: bool


Pages = Union[List[str], List[Embed]]


class Paginator(View):
    def __init__(
        self,
        ctx: Context,
        pages: Pages | List[EmbedField],
        embed: Optional[Embed] = None,
        per_page: int = 10,
        counter: bool = True,
        show_entries: bool = False,
        delete_after: Optional[float] = None,
    ):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.message = None
        self.show_entries = show_entries
        self.total_entries = len(pages)
        self.pages = self._format_pages(
            pages, embed, per_page, counter
        )
        self.index = 0
        self.delete_after = delete_after
        for button in self.buttons:
            button.callback = self.callback
            self.add_item(button)

    @property
    def buttons(self):
        emojis = self.ctx.config.emojis.paginator
        return [
            Button(
                custom_id="paginator:previous",
                style=ButtonStyle.secondary,
                emoji=emojis.previous,
            ),
            Button(
                custom_id="paginator:next",
                style=ButtonStyle.secondary,
                emoji=emojis.next,
            ),
            Button(
                custom_id="paginator:navigate",
                style=ButtonStyle.secondary,
                emoji=emojis.navigate,
            ),
            Button(
                custom_id="paginator:cancel",
                style=ButtonStyle.secondary,
                emoji=emojis.cancel,
            ),
        ]

    def _format_pages(
        self,
        pages: Pages | List[EmbedField],
        embed: Optional[Embed],
        per_page: int,
        counter: bool,
    ) -> Pages:
        compiled: List = []
        if not embed:
            if all(isinstance(page, str) for page in pages):
                pages = cast(List[str], pages)
                compiled = cast(List[str], [])

                for index, page in enumerate(
                    pages, start=1
                ):
                    if "page" not in page and counter:
                        page = (
                            f"({index}/{len(pages)}) {page}"
                        )

                    page = page.format(
                        page=index, pages=len(pages)
                    )
                    compiled.append(page)

            elif all(
                isinstance(page, Embed) for page in pages
            ):
                pages = cast(List[Embed], pages)
                compiled = cast(List[Embed], [])

                for index, page in enumerate(
                    pages, start=1
                ):
                    if counter:
                        self._add_footer(
                            page, index, len(pages)
                        )

                    compiled.append(page)

        elif all(isinstance(page, str) for page in pages):
            pages = cast(List[str], pages)
            compiled = cast(List[Embed], [])
            total_pages = ceil(len(pages) / per_page)
            offset = 0

            for chunk in as_chunks(pages, per_page):
                prepared = embed.copy()
                prepared.description = (
                    f"{prepared.description or ''}\n\n"
                )

                for page in chunk:
                    if counter:
                        offset += 1
                        prepared.description = (
                            (prepared.description or "")
                            + f"`{str(offset).zfill(2)}` {page}\n"
                        )
                    else:
                        prepared.description = (
                            prepared.description or ""
                        ) + f"{page}\n"

                self._add_footer(
                    prepared, len(compiled) + 1, total_pages
                )
                compiled.append(prepared)

        elif all(isinstance(page, dict) for page in pages):
            pages = cast(List[EmbedField], pages)
            compiled = cast(List[Embed], [])
            total_pages = ceil(len(pages) / per_page)

            for chunk in as_chunks(pages, per_page):
                prepared = embed.copy()
                for field in chunk:
                    field["inline"] = field.get(
                        "inline", False
                    )
                    prepared.add_field(**field)

                self._add_footer(
                    prepared, len(compiled) + 1, total_pages
                )
                compiled.append(prepared)

        elif all(isinstance(page, Embed) for page in pages):
            pages = cast(List[Embed], pages)
            compiled = cast(List[Embed], [])
            total_pages = len(pages)

            for index, page in enumerate(pages, start=1):
                if counter:
                    self._add_footer(
                        page, index, total_pages
                    )

                compiled.append(page)

        if not compiled and embed:
            compiled = [embed]

        return compiled

    def _add_footer(
        self, embed: Embed, page: int, pages: int
    ) -> None:
        if pages == 1:
            return

        to_add: List[str] = []
        if embed.footer.text:
            to_add.append(embed.footer.text)

        if to_add and "{page}" in to_add[0]:
            to_add[0] = to_add[0].format(
                page=page, pages=pages
            )
        else:
            footer_text = f"Page {page}/{pages}"
            if self.show_entries:
                footer_text += (
                    f" ({self.total_entries:,} entries)"
                )
            to_add.append(footer_text)

        embed.set_footer(
            text=" • ".join(to_add),
            icon_url=embed.footer.icon_url,
        )

    async def start(self, **kwargs: Any) -> Message:
        if not self.pages:
            raise ValueError("No pages to paginate")

        delete_after = self.delete_after or cast(
            float, kwargs.pop("delete_after", 0)
        )
        page = self.pages[self.index]
        if len(self.pages) == 1:
            self.message = (
                await self.ctx.send(content=page, **kwargs)
                if isinstance(page, str)
                else await self.ctx.send(
                    embed=page, **kwargs
                )
            )
        else:
            self.message = (
                await self.ctx.send(
                    content=page, view=self, **kwargs
                )
                if isinstance(page, str)
                else await self.ctx.send(
                    embed=page, view=self, **kwargs
                )
            )

        if delete_after:
            await self.ctx.message.delete(
                delay=delete_after
            )
            await self.message.delete(delay=delete_after)

        return self.message

    async def interaction_check(
        self, interaction: Interaction
    ) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.embed(
                "You cannot **interact** with this **paginator**"
            )
        return interaction.user == self.ctx.author

    async def on_timeout(self) -> None:
        if self.message:
            with suppress(HTTPException):
                await self.message.edit(view=None)

    async def wait_for_page(
        self, interaction: Interaction
    ) -> None:
        assert self.message
        for child in self.children:
            child.disabled = True  # type: ignore

        await self.message.edit(view=self)
        embed = Embed(
            # color=config.color.basecolor,
            description=f":1234: What page would you like to skip to?",
        )
        prompt = await interaction.followup.send(
            embed=embed, ephemeral=True, wait=True
        )

        try:
            response = await self.ctx.bot.wait_for(
                "message",
                timeout=6,
                check=lambda m: (
                    m.author == interaction.user
                    and m.channel == interaction.channel
                    and m.content.isdigit()
                    and int(m.content) <= len(self.pages)
                ),
            )
        except asyncio.TimeoutError:
            response = None
        else:
            self.index = int(response.content) - 1
        finally:
            for child in self.children:
                child.disabled = False  # type: ignore

            with suppress(HTTPException):
                await prompt.delete()
                if response:
                    await response.delete()

    async def callback(
        self, interaction: Interaction
    ) -> None:
        assert self.message
        await interaction.response.defer()

        custom_id = interaction.data["custom_id"]  # type: ignore
        if custom_id == "paginator:previous":
            self.index = (
                max(self.index - 1, 0)
                if self.index != 0
                else len(self.pages) - 1
            )
        elif custom_id == "paginator:next":
            self.index = (
                min(self.index + 1, len(self.pages) - 1)
                if self.index != len(self.pages) - 1
                else 0
            )
        elif custom_id == "paginator:navigate":
            await self.wait_for_page(interaction)
        elif custom_id == "paginator:cancel":
            with suppress(HTTPException):
                await self.ctx.channel.delete_messages([
                    self.message,
                    self.ctx.message,
                ])

            return self.stop()

        page = self.pages[self.index]
        with suppress(HTTPException):
            if isinstance(page, str):
                await self.message.edit(
                    content=page, view=self
                )
            else:
                await self.message.edit(
                    embed=page, view=self
                )
