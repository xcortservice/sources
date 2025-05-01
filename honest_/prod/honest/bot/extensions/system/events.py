import uuid
from typing import Any, List

import orjson
from discord import Client, Embed, Guild, Member, User
from discord.ext import tasks
from discord.ext.commands import Cog, CommandError
from loguru import logger
from system.classes.redis import IPCData, IPCResponse
from system.worker import GLOBAL_DASK


class SystemEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.words: List[str] = []

    async def cog_load(self):
        with open("words.json", "rb") as file:
            self.words.extend(orjson.loads(file.read()))
        self.store_statistics.start()

    async def cog_unload(self):
        self.store_statistics.stop()

    @tasks.loop(seconds=30)
    async def store_statistics(self):
        self.bot.num_tasks = sum(
            len(v) for k, v in (await GLOBAL_DASK["client"].processing()).items()
        )

    @Cog.listener("on_redis_message")
    async def redis_listener(self, message: IPCResponse):
        if isinstance(message.data, dict):
            message.data = IPCData(**message.data)
        if message.data.event == "Request":
            func = getattr(self, message.data.endpoint)
            response = {"response": await func(**message.data.data)}
            await self.bot.redis.publish(message.data.source, orjson.dumps(response))
            logger.info(f"published {response} to {message.data.source}")

    async def get_guild_count(self, **kwargs: Any):
        return len(self.bot.guilds)

    async def request(self, endpoint: str, destination: str, **kwargs):
        uuidd = str(uuid.uuid4())
        logger.info(f"waiting for request with uuid {uuidd}")
        data = IPCData(
            event="Request",
            endpoint=endpoint,
            source=getattr(self.bot, "cluster_name", "honest1"),
            destination=destination,
            uuid=uuidd,
            data=kwargs,
        )
        logger.info(f"requesting with data: {data}")
        await self.bot.redis.publish(destination, orjson.dumps(data.dict()))
        response = await self.bot.wait_for(
            "redis_message", check=lambda x: x.data.uuid == uuidd
        )
        return response.data

    def activity(self, member: Member) -> str:
        if member.activity:
            if member.activity.name is not None:
                return member.activity.name
            else:
                return ""
        return ""

    @Cog.listener("on_presence_update")
    async def status_check(self, before: Member, after: Member):
        if self.bot.status_filter.get(after.guild.id, False) is False:
            return

        status = self.activity(after)

        if any(word in status for word in self.words):
            try:
                await after.send(
                    embed=Embed(
                        title="You have been **kicked.**",
                        description="Your status has been detected containing vulgar content, please remove it to rejoin the server.",
                        color=self.bot.color,
                    )
                )
            except Exception:
                pass
            try:
                await after.kick(reason="Vulgar Status Content")
            except Exception:
                pass


async def setup(bot: Client):
    await bot.add_cog(SystemEvents(bot))
