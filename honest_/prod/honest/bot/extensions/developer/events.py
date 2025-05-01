import asyncio
from discord import Client
from discord.ext import tasks
from discord.ext.commands import Cog
from loguru import logger
from system.classes.builtins import get_error



class DeveloperEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    async def cog_load(self):
        self.global_ban_loop.start()

    async def cog_unload(self):
        self.global_ban_loop.stop()

    @tasks.loop(minutes=1)
    async def global_ban_loop(self):
        try:
            i = 0
            for ban in await self.bot.db.fetch("""SELECT user_id FROM global_ban"""):

                if not (user := self.bot.get_user(ban.user_id)):
                    continue

                for mutual in user.mutual_guilds:
                    member = mutual.get_member(ban.user_id)
                    if member.is_bannable:
                        await member.ban(reason="Global Ban")
                        i += 1
            logger.info(f"successfully executed {i} global bans")
        except Exception as e:
            logger.info(f"unhandled exception in global_ban_loop: {get_error(e)}")

async def setup(bot: Client):
    await bot.add_cog(DeveloperEvents(bot))
