from typing import Literal, Optional

from discord.ext.commands import Converter, flag

from system.patch.context import Context
from .base import Flags as FlagConverter


def get_period(timeframe, allow_custom=True):
    if timeframe in ["day", "today", "1day", "24h"] and allow_custom:
        period = "today"
    elif timeframe in ["7day", "7days", "weekly", "week", "1week"]:
        period = "7day"
    elif timeframe in ["30day", "30days", "monthly", "month", "1month"]:
        period = "1month"
    elif timeframe in ["90day", "90days", "3months", "3month"]:
        period = "3month"
    elif timeframe in ["180day", "180days", "6months", "6month", "halfyear"]:
        period = "6month"
    elif timeframe in ["365day", "365days", "1year", "year", "12months", "12month"]:
        period = "12month"
    elif timeframe in ["at", "alltime", "all", "overall"]:
        period = "overall"
    else:
        period = "overall"
    return period


class TimePeriodConverter(Converter):
    async def convert(self, ctx: Context, argument: str):
        timeframe = argument.lower()
        period = get_period(timeframe)
        return period


class ChartTypeConverter(Converter):
    async def convert(self, ctx: Context, argument: str):
        argument = argument.lower()
        if argument in ("artist", "artists", "art"):
            return "artist"
        elif argument in ("album", "albums", "alb"):
            return "album"
        else:
            return "recent"


class CollageFlags(FlagConverter):
    size: Optional[str] = flag(
        name="size", default=None, description="a size in the form of height and width"
    )
    time_period: Optional[TimePeriodConverter] = flag(
        name="timeperiod",
        aliases=["time", "timeframe"],
        default="overall",
        description="the timeperiod of data to add to the collage",
    )
    chart_type: Optional[ChartTypeConverter] = flag(
        name="type",
        aliases=["charttype"],
        default="artist",
        description="the type of data to collage",
    )
