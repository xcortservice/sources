from typing import Optional

from discord.ext.commands import CommandError, Converter, flag
from system.patch.context import Context

from .base import Flags as FlagConverter

ACTIONS = {
    "ban": {
        "aliases": ["b"],
        "value": 0,
    },
    "kick": {
        "aliases": ["k"],
        "value": 1,
    },
}


class ActionConverter(Converter):
    async def convert(self, ctx: Context, argument: str):
        for key, value in ACTIONS.items():
            if argument.lower() in value["aliases"]:
                return ACTIONS[key]["value"]
            if key.lower() == argument.lower():
                return ACTIONS[key]["value"]
        raise CommandError("Available options are `kick` and `ban`")


class AntiRaidParameters(FlagConverter):
    action: Optional[ActionConverter] = flag(
        name="action",
        aliases=["do"],
        default="kick",
        description="The action which will be taken when the threshold is reached.",
    )
    threshold: Optional[int] = flag(
        name="threshold",
        description="The threshold is the number of accounts that can join the server within the time frame.",
    )
    punish: Optional[bool] = flag(
        name="punish",
        aliases=["punishment"],
        description="Whether to punish new accounts that join the server.",
    )
    lock: Optional[bool] = flag(
        name="lock",
        description="Whether to lock all channels when the threshold is reached.",
    )


class ActionParameters(FlagConverter):
    action: Optional[ActionConverter] = flag(
        name="action",
        aliases=["do"],
        default="kick",
        description="The action which will be taken when the threshold is reached.",
    )
