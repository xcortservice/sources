from typing import Optional

from discord.ext.commands import CommandError, Converter, flag
from system.patch.context import Context

from .base import Flags as FlagConverter


class BlackTeaFlags(FlagConverter):
    timeout: Optional[int] = flag(
        name="timeout",
        aliases=["time"],
        default=10,
        description="the amount of seconds players have to type the word",
    )
    lives: Optional[int] = flag(
        name="lives",
        aliases=["life", "lc"],
        default=3,
        description="the amount of lives players have before they are eliminated",
    )
