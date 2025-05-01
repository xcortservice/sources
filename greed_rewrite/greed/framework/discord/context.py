import discord

from greed.framework.tools import Button, View
from greed.framework.pagination import Paginator

# from greed.shared.clients.settings import Settings

from discord import (
    ButtonStyle,
    Colour,
    Embed,
    Guild,
    HTTPException,
    Interaction,
    Member,
    Message,
)
from discord.ext.commands import (
    Context as DefaultContext,
    UserInputError,
)
from discord.types.embed import EmbedType
from discord.ui import button
from discord.utils import cached_property

from datetime import datetime
from typing import Optional, Any
from xxhash import xxh32_hexdigest
from typing import TYPE_CHECKING, Literal, List
from contextlib import suppress

if TYPE_CHECKING:
    from greed.framework import Greed
    from greed.shared.config import Configuration

MESSAGE_TYPES = Literal["approved", "warned", "denied", "neutral", "currency"]


class Context(DefaultContext):
    bot: "Greed"
    config: "Configuration"
    guild: Guild  # type: ignore

    @cached_property
    def replied_message(self) -> Optional[Message]:
        reference = self.message.reference
        if reference and isinstance(reference.resolved, Message):
            return reference.resolved

        return None

    @property
    def color(self) -> Colour:
        return Colour.dark_embed()

    async def embed(
        self,
        message: str,
        message_type: MESSAGE_TYPES,
        edit: Optional[Message] = None,
        color: Optional[Colour] = None,
        tip: Optional[str] = None,
        **kwargs,
    ) -> Message:
        """
        Send an embed with a message type.

        Supported message types: approved, warned, denied, neutral, currency
        """
        if message_type == "neutral":
            emoji = ""
        elif message_type == "currency":
            emoji = "💵"
            color = Colour.green()
        else:
            emoji = getattr(self.config.emojis.context, message_type)

        embed = Embed(
            description=f"{emoji} {self.author.mention}: {message}",
            color=color or getattr(self.config.colors, message_type),
        )
        if tip:
            embed.set_footer(text=f"Tip: {tip}")

        if edit:
            await edit.edit(embed=embed)
            return edit

        return await self.send(embed=embed, **kwargs)

    async def warn(
        self,
        message: str,
        delete_after: bool = False,
        patch: Optional[Message] = None,
        *args: Any,
    ) -> Message:
        """
        Sends a warning message, or edits an existing message if patch is provided.
        """
        if args:
            formatted_args = "\n".join(args)
            message += "\n" + formatted_args

        embed = Embed(
            color=self.config.colors.warned,
            description=f"{self.config.emojis.context.warned} {self.author.mention}: {message}",
        )

        if patch:
            await patch.edit(embed=embed)
            return patch

        try:
            return await self.send(embed=embed)
        except discord.NotFound:
            return await super().send(embed=embed)

    async def prompt(
        self,
        *args: str,
        timeout: int = 60,
    ) -> Literal[True]:
        key = xxh32_hexdigest(f"prompt:{self.author.id}:{self.command.qualified_name}")

        async with self.bot.redis.get_lock(key):
            embed = Embed(
                description="\n".join(
                    ("" if len(args) == 1 or index == len(args) - 1 else "") + str(arg)
                    for index, arg in enumerate(args)
                ),
            )

            view = Confirmation(self, timeout=timeout)

            try:
                view.message = await self.send(embed=embed, view=view)
            except HTTPException as exc:
                raise UserInputError("Failed to send prompt message!") from exc

            await view.wait()

            if view.value is True:
                return True

            if view.message:
                with suppress(HTTPException):
                    await view.message.delete()

            raise UserInputError("Confirmation prompt wasn't approved!")

    async def confirm(
        self,
        *args: str,
        user: Member,
        timeout: int = 60,
    ) -> bool:
        """
        An interactive reaction confirmation dialog.

        Raises UserInputError if the user denies the prompt.
        """
        key = xxh32_hexdigest(f"confirm:{self.author.id}:{self.command.qualified_name}")

        async with self.bot.redis.get_lock(key):
            embed = Embed(
                description="\n".join(
                    ("" if len(args) == 1 or index == len(args) - 1 else "") + str(arg)
                    for index, arg in enumerate(args)
                ),
            )
            view = Approve(self, user=user, timeout=timeout)

            try:
                await self.send(embed=embed, view=view)
            except HTTPException as exc:
                raise UserInputError("Failed to send prompt message!") from exc

            await view.wait()

            if view.value is True:
                return True

            raise UserInputError("Confirmation prompt wasn't approved!")

    async def paginate(
        self,
        entries: List[str],
        *,
        embed: Optional[Embed] = None,
        per_page: int = 10,
        counter: bool = True,
        show_entries: bool = False,
        delete_after: Optional[float] = None,
    ) -> None:
        paginator = Paginator(
            self,
            entries,
            embed=embed,
            per_page=per_page,
            counter=counter,
            show_entries=show_entries,
            delete_after=delete_after,
        )
        await paginator.start()

    async def send_help(self, command=None) -> Optional[Message]:
        if not hasattr(self, "bot") or not hasattr(self, "command"):
            return None

        help_command = self.bot.get_command("help")
        if help_command:
            if isinstance(command, str):
                return await help_command(self, command=command)
            elif command:
                return await help_command(self, command=command.qualified_name)
            return await help_command(self)
        return await super().send_help(command)


class Confirmation(View):
    value: Optional[bool]
    message: Message = None

    def __init__(self, ctx: Context, *, timeout: Optional[int] = 60):
        super().__init__(ctx, timeout=timeout)
        self.ctx = ctx
        self.value = None

    async def on_timeout(self) -> None:
        if self.message:
            with suppress(HTTPException):
                await self.message.delete()

    @button(label="Approve", style=ButtonStyle.green)
    async def approve(self, interaction: Interaction, button: Button):
        self.value = True
        await interaction.response.defer()
        if self.message:
            with suppress(HTTPException):
                await self.message.delete()
        self.stop()

    @button(label="Decline", style=ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: Button):
        self.value = False
        await interaction.response.defer()
        if self.message:
            with suppress(HTTPException):
                await self.message.delete()
        self.stop()


class Approve(View):
    def __init__(
        self,
        ctx: Context,
        user: Optional[Member] = None,
        *,
        timeout: Optional[int] = 60,
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.user = user
        self.value = None

    @button(label="Approve", style=ButtonStyle.green)
    async def approve(self, interaction: Interaction):
        if interaction.user != self.user:
            return await interaction.response.send_message(
                f"Only **{self.user}** can respond to this!",
                ephemeral=True,
            )

        self.value = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @button(label="Decline", style=ButtonStyle.danger)
    async def decline(self, interaction: Interaction):
        if interaction.user != self.user:
            return await interaction.response.send_message(
                f"Only **{self.user}** can respond to this!",
                ephemeral=True,
            )

        self.value = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class Embed(discord.Embed):
    def __init__(
        self,
        value: Optional[str] = None,
        *,
        colour: int | Colour | None = None,
        color: int | Colour | None = None,
        title: Any | None = None,
        type: EmbedType = "rich",
        url: Any | None = None,
        description: Any | None = None,
        timestamp: datetime | None = None,
    ):
        description = description or value
        super().__init__(
            colour=colour,
            color=color or 0xCCCCFF,
            title=title,
            type=type,
            url=url,
            description=description[:4096] if description else None,
            timestamp=timestamp,
        )

    def add_field(
        self, *, name: Any, value: Any, inline: bool = True
    ) -> "discord.Embed":
        if not name or (isinstance(name, str) and ("```" in name or "`" in name)):
            return super().add_field(name=name, value=value, inline=inline)
        return super().add_field(name=f"**{name}**", value=value, inline=inline)


discord.Embed = Embed
