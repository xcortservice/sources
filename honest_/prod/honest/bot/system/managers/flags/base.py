from discord.ext.commands import FlagConverter


class Flags(
    FlagConverter,
    case_insensitive=True,
    prefix="-",
    delimiter=" ",
):
    pass
