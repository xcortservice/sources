from discord import Client, Embed, Guild, Member, User
from discord.ext.commands import (Boolean, Cog, CommandError, command, group,
                                  has_permissions, hybrid_command,
                                  hybrid_group)
from system.patch.context import Context


class SystemCommands(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @hybrid_command(
        name="statusfilter", description="filter slurs out of members' statuses"
    )
    @has_permissions(administrator=True)
    async def statusfilter(self, ctx: Context, state: Boolean):
        self.bot.status_filter[ctx.guild.id] = state
        return await ctx.success(
            f"successfully **{'ENABLED' if state else 'DISABLED'}** status filtering"
        )


async def setup(bot: Client):
    await bot.add_cog(SystemCommands(bot))
