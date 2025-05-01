
from discord.ext.commands import (
    CommandError,
    Cog,
    group,
    command,
    has_permissions
)
from discord import (
    Client,
    Embed,
    File,
    User,
    Member,
    Message,
    Guild,
    TextChannel,
    Thread
)
from system.patch.context import Context

class LastFMEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    async def check_blacklist(self, message: Message):
        if await self.bot.db.fetchrow("""SELECT * FROM lastfm.command_blacklist WHERE guild_id = $1 AND user_id = $2""", message.guild.id, message.author.id):
            return False
        else:
            return True


    @Cog.listener("on_valid_message")
    async def on_custom_command(self, ctx: Context):
        if cc_ := await self.bot.db.fetch("""SELECT command, user_id, public FROM lastfm.commands WHERE guild_id = $1""", ctx.guild.id, cached = False):
            for cc in cc_:
                if not cc.public and not ctx.author.id == cc.user_id:
                    continue
                if cc.command.lower() in ctx.message.content.lower().split(" "):
                    if await self.check_blacklist(ctx.message):
                        await ctx.invoke(self.bot.get_command("nowplaying"))

async def setup(bot: Client):
    await bot.add_cog(LastFMEvents(bot))