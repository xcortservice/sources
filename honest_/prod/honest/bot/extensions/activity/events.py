from discord import Client, Guild, Member, User
from discord.ext.commands import Cog


class ScreentimeEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot


async def setup(bot: Client):
    await bot.add_cog(ScreentimeEvents(bot))
