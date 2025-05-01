from __future__ import annotations

import unicodedata

from abc import ABC
from contextlib import (
    asynccontextmanager,
    contextmanager,
    suppress,
)
from io import BytesIO
import logging
from pathlib import Path
from secrets import token_hex
from time import time
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Generator,
    List,
    Optional,
    Tuple,
)
from urllib.parse import urlparse
from anyio import Path as AsyncPath
from cairosvg import svg2png
from colorama import Fore, Style
from colorthief import ColorThief
from jishaku.functools import executor_function
from tornado.escape import url_unescape
from wand.image import Image
from datetime import timedelta
from humanize import precisedelta

from discord import (
    ButtonStyle,
    Color,
    Emoji,
    HTTPException,
    Interaction,
    Member,
    Message,
    PartialEmoji,
    PartialMessage,
    Role,
)
from discord.ext import commands
from discord.ui import (
    Button as OriginalButton,
    View as OriginalView,
)

from .mime_table import mimes
from .formatter import *
from .offload import offloaded

if TYPE_CHECKING:
    from greed.framework import Greed, Context

TMP_ROOT = AsyncPath("/tmp")
CACHE_ROOT = TMP_ROOT / "greed"


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """
    This allows the metaclass used for proper type detection to
    coexist with discord.py's metaclass
    """

    pass


class MixinMeta(
    commands.Cog, ABC, metaclass=CompositeMetaClass
):
    """
    This is the base class for all mixins.
    With well-defined mixins, we can avoid the need for multiple inheritance.
    """

    bot: "Greed"


def fmtseconds(
    seconds: timedelta | float | int,
    unit: str = "microseconds",
) -> str:
    if not isinstance(seconds, timedelta):
        seconds = timedelta(seconds=seconds)

    return precisedelta(seconds, minimum_unit=unit)


async def quietly_delete(
    message: Message | PartialMessage,
) -> None:
    if not isinstance(message, (Message, PartialMessage)):
        raise TypeError(
            f"Expected a Message or PartialMessage, but got {type(message)}"
        )

    if not message.guild:
        return

    if message.channel.permissions_for(
        message.guild.me
    ).manage_messages:
        with suppress(HTTPException):
            await message.delete()


def url_to_mime(url: str) -> tuple[Optional[str], str]:
    suffix = Path(urlparse(url_unescape(url)).path).suffix
    return (mimes.get(suffix, None), suffix)


def get_filename(url: str) -> str:
    return AsyncPath(urlparse(url_unescape(url)).path).name


@asynccontextmanager
async def temp_file(
    extension: str,
) -> AsyncGenerator[AsyncPath, None]:
    await CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_ROOT / f"{token_hex(8)}.{extension}"

    try:
        yield tmp
    finally:
        await tmp.unlink(missing_ok=True)


def unicode_emoji(emoji: str) -> tuple[str, str]:
    characters: list[str] = []
    name: list[str] = []
    for character in emoji:
        characters.append(hex(ord(character))[2:])
        try:
            name.append(unicodedata.name(character))
        except ValueError:
            ...

    if len(characters) == 2 and "fe0f" in characters:
        characters.remove("fe0f")
    if "20e3" in characters:
        characters.remove("fe0f")

    return (
        (
            "https://cdn.jsdelivr.net/gh/jdecked/"
            "twemoji@latest/assets/svg/"
            + "-".join(characters)
            + ".svg"
        ),
        "_".join(name),
    )


@executor_function
def convert_image(buffer: bytes, format: str) -> bytes:
    image = Image(blob=buffer)
    return image.make_blob(format)  # type: ignore


@executor_function
def dominant_color(buffer: BytesIO | bytes) -> Color:
    if isinstance(buffer, bytes):
        buffer = BytesIO(buffer)

    thief = ColorThief(buffer)
    color = thief.get_color()
    return Color.from_rgb(*color)


@executor_function
def enlarge_emoji(
    buffer: bytes, format: str
) -> Tuple[Optional[bytes], str]:
    if format == "svg":
        return (
            svg2png(
                buffer,
                parent_height=1024,
                parent_width=1024,
            ),
            "png",
        )

    with Image(blob=buffer) as image:
        factor = 300 // image.width

        image.interlace_scheme = format
        image.quantize(250)
        image.coalesce()
        image.optimize_layers()
        image.resize(
            width=image.width * factor,
            height=image.height * factor,
            filter="lanczos2sharp",
        )

        return image.make_blob(), format


@contextmanager
def capture_time(
    msg: Optional[str] = None,
    log: Optional[logging.Logger] = None,
) -> Generator:
    start = time()
    if not log:
        logging.getLogger("greed/utils").info("Capturing time")
    if not msg:
        msg = log.findCaller()[2]

    try:
        yield
    finally:
        duration = time() - start
        log.info(
            f"{msg} {Fore.LIGHTWHITE_EX}{Style.DIM}{fmtseconds(duration)}{Fore.RESET}{Style.NORMAL}."
        )


def is_dangerous(role: Role) -> bool:
    return any(
        value
        and permission
        in (
            "administrator",
            "kick_members",
            "ban_members",
            "manage_guild",
            "manage_roles",
            "manage_channels",
            "manage_expressions",
            "manage_webhooks",
            "manage_nicknames",
            "mention_everyone",
        )
        for permission, value in role.permissions
    )


async def strip_roles(
    member: Member,
    *,
    dangerous: bool = False,
    reason: Optional[str] = None,
) -> bool:
    """
    Remove all roles from a member.
    """
    bot = member.guild.me
    if (
        member.top_role >= bot.top_role
        and bot.id != member.guild.owner_id
    ):
        return False

    roles: List[Role] = []
    for role in member.roles[1:]:
        if not role.is_assignable():
            continue

        elif dangerous and not is_dangerous(role):
            continue

        roles.append(role)

    if roles:
        with suppress(HTTPException):
            await member.remove_roles(*roles, reason=reason)
            return True

    return False


class View(OriginalView):
    ctx: Context

    def __init__(self, ctx: Context, *args, **kwargs):
        self.ctx = ctx
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: Interaction):
        raise NotImplementedError

    async def disable_buttons(self) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore

    async def on_timeout(self) -> None:
        self.stop()

    async def interaction_check(
        self, interaction: Interaction
    ) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.embed(
                "You are **not** the author of this embed!"
            )

        return interaction.user == self.ctx.author


class Button(OriginalButton):
    view: View
    custom_id: str

    def __init__(
        self,
        *,
        style: ButtonStyle = ButtonStyle.gray,
        label: str | None = None,
        disabled: bool = False,
        custom_id: str | None = None,
        url: str | None = None,
        emoji: str | Emoji | PartialEmoji | None = None,
        row: int | None = None,
    ):
        super().__init__(
            style=style,
            label=label,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )

    async def callback(self, interaction: Interaction):
        await self.view.callback(interaction, self)


__all__ = (
    "fmtseconds",
    "TMP_ROOT",
    "CACHE_ROOT",
    "MixinMeta",
    "CompositeMetaClass",
    "quietly_delete",
    "url_to_mime",
    "get_filename",
    "temp_file",
    "unicode_emoji",
    "convert_image",
    "dominant_color",
    "capture_time",
    "View",
    "Button",
    "offloaded",
)
