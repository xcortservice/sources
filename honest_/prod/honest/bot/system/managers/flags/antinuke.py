from typing import Literal, Optional, Union

from discord.ext.commands import Boolean, CommandError, flag, Range
from system.classes.converters import AntiNukeAction
from system.patch.context import Context

ACTION = Literal["ban", "kick", "stripstaff"]
Parameters = {
    "punishment": {
        "converter": str,
        "aliases": (
            "do",
            "action",
        ),
        "choices": ["ban", "kick", "stripstaff", "strip"],
        "default": "ban",
    },
    "threshold": {"converter": int, "default": 3},
    "command": {"converter": Boolean, "default": False},
}


async def get_parameters(ctx: Context) -> dict:
    try:
        command = ctx.parameters.get("command", False)
        if command:
            # if not isinstance(command, bool):
            #     command = await Boolean().convert(ctx, command)

            try:
                command = await command or False
            except Exception:
                pass
    except Exception:
        command = False
    if ctx.parameters.get("threshold") > 6 or 1 > ctx.parameters.get("threshold"):
        raise CommandError(
            "Invalid value for parameter `threshold`, must be between 1 and 6"
        )
    if p1 := ctx.parameters.get("punishment"):
        punishment = p1
    elif p2 := ctx.parameters.get("action"):
        punishment = p2
    elif p3 := ctx.parameters.get("do"):
        punishment = p3
    else:
        punishment = "kick"
    punishment = punishment.lower().lstrip().rstrip()
    if punishment not in ("ban", "kick", "stripstaff"):
        raise CommandError(
            "Invalid value for parameter `punishment`, must be one of the following valid actions `ban`, `kick` and `stripstaff`"
        )
    new_parameters = {
        "punishment": punishment,
        "threshold": ctx.parameters.get("threshold"),
        "command": command,
    }
    return new_parameters
