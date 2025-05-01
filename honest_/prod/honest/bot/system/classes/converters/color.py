from typing import Union

from color_processing import ColorHolder
from discord import Color, Member, User
from discord.ext.commands import (ColorConverter, ColourConverter,
                                  CommandError, Converter)
from loguru import logger
from system.patch.context import Context
from system.worker import offloaded

COLOR = ColorHolder.get_colors(offloaded)


async def get_dominant_color(query: Union[str, Member, User]):
    return await COLOR.get_dominant_color(query)


class ColorConv(Converter):
    async def convert(self, ctx: Context, argument: Union[Color, Member, User, str]):
        if isinstance(argument, (Member, User)):
            argument = await get_dominant_color(argument)
        elif isinstance(argument, Color):
            return argument
        elif argument.lower().startswith("0x"):
            return Color.from_str(argument)
        else:
            argument = str(argument).lower()
            try:
                if argument.startswith("#"):
                    return Color.from_str(argument)
                else:
                    return Color.from_str(f"#{argument}")
            except Exception:
                pass
            try:
                if argument.lower() in ("dom", "dominant"):
                    return Color.from_str(await get_dominant_color(ctx.author))
                else:
                    _ = await COLOR.color_search(argument)
                    return Color.from_str(_[1])
            except Exception as e:
                logger.info(f"Color Converter Errored with : {e}")
                raise CommandError("Invalid color hex given")


class ColorInfo(Converter):
    async def convert(self, ctx: Context, argument: Union[Color, Member, User, str]):
        if argument.lower().startswith("0x"):
            argument = str(Color.from_str(argument))
        elif isinstance(argument, Color):
            argument = str(argument)
        elif isinstance(argument, str):
            if argument.startswith("https://"):
                argument = await get_dominant_color(argument)
        elif isinstance(argument, (User, Member)):
            argument = await get_dominant_color(argument)
        _ = await COLOR.color_info(argument)
        return await _.to_message(ctx)
