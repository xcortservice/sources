from typing import Literal, Optional

from discord.ext.commands import flag

from .base import Flags as FlagConverter


class ScreenshotFlags(FlagConverter, delimiter=" "):
    wait: Optional[int] = flag(
        default=None, description="An optional wait time in seconds."
    )
    wait_for: Optional[Literal["domcontentloaded", "networkidle", "load", "commit"]] = (
        flag(
            name="waituntil",
            aliases=["event", "wu"],
            default="domcontentloaded",
            description="Specify the wait condition. One of 'domcontentloaded', 'networkidle', 'load', or 'commit'.",
        )
    )
    full_page: bool = flag(
        name="fullpage",
        aliases=["full", "fp"],
        default=False,
        description="screenshot the entire page in one image",
    )
