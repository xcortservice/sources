from typing import Literal, Optional

from discord.ext.commands import flag

from .base import Flags as FlagConverter


class ModerationFlags(FlagConverter, delimiter=" "):
    reason: Optional[str] = flag(
        aliases=["r"],
        default="No Reason provided",
        description="give a reason for the moderation action taken",
    )
