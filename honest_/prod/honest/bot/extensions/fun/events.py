from asyncio import ensure_future
from logging import getLogger

from discord import (Client, Embed, File, Guild, Member, TextChannel, Thread,
                     User)
from discord.ext.commands import (Cog, CommandError, command, group,
                                  has_permissions)
from loguru import logger
from system.patch.context import Context

log = getLogger(__name__)


def l(message: str):
    log.info(message)
    logger.info(message)


class FunEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self._last_message = None

    @Cog.listener("on_valid_message")
    async def add_message_history(self, ctx: Context):
        ensure_future(self.bot.redis.add_message(ctx.message))

    @Cog.listener("on_redis_message")
    async def redis_message(self, message):
        self._last_message = message
        l(f"received message from redis: {message}")


async def setup(bot: Client):
    await bot.add_cog(FunEvents(bot))
