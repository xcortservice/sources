from discord import (Client, Embed, File, Guild, Member, TextChannel, Thread,
                     User)
from discord.ext.commands import (Cog, CommandError, command, group,
                                  has_permissions)


class Economy(Cog):
    def __init__(self, bot: Client):
        self.bot = bot


async def setup(bot: Client):
    await bot.add_cog(Economy(bot))
