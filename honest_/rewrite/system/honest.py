import uvloop
import asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
import os
import random
import string
import traceback
import discord
from discord import (
    Intents,
    CustomActivity,
    Embed,
    Interaction,
    app_commands
)
from discord.ext.commands import (
    AutoShardedBot,
    errors
)
from discord.utils import utcnow

from system.classes.db import Database
from pathlib import Path
from system.classes.logger import Logger
from system.classes.emojis import EmojiManager
from data.config import CONFIG
from asyncio import gather
from datetime import datetime

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_RETAIN"] = "True"

class Honest(AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=CONFIG['prefix'],
            owner_ids=CONFIG['owners'],
            activity=CustomActivity(name="🔗 honest.rocks/discord"),
            intents=Intents.all(),
            help_command=None,
        )
        self.config = CONFIG
        self.logger = Logger()
        self.db = Database()
        self._user_register_lock = asyncio.Lock()
        self.start_time = utcnow()
        self.warn_emoji = "⚠️"
        self.tree.interaction_check = self.interaction_check
        self.before_invoke(self.before_invoke_handler)
        self._emoji_manager = None

    @property
    def emojis(self):
        """Regular property to access emoji manager"""
        if self._emoji_manager is None:
            self._emoji_manager = EmojiManager(self)
        return self._emoji_manager

    async def run(self: "Honest"):
        await super().start(self.config['token'], reconnect=True)
             
    async def __load(self: "Honest", cog: str):
        try:
            await self.load_extension(cog)
            self.logger.info(f"Loaded {cog}")
        except errors.ExtensionAlreadyLoaded:
            pass
        except Exception as e:
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            self.logger.info(f"Failed to load {cog} due to exception: {tb}")
        
    async def load_cogs(self: "Honest"):
        tasks = []
        extensions_dir = Path("extensions")
        if extensions_dir.exists():
            for category in ["userapp", "hybrid", "prefix"]:
                category_dir = extensions_dir / category / "cogs"
                if category_dir.exists():
                    for cog_file in category_dir.glob("*.py"):
                        if cog_file.name != "__init__.py":
                            cog_path = f"extensions.{category}.cogs.{cog_file.stem}"
                            tasks.append(self.__load(cog_path))
        
        if tasks:
            await gather(*tasks)
        
    async def setup_hook(self: "Honest") -> None:
        """Initialize bot systems"""
        await self.db.initialize()
        await self.emojis.initialize()
        self.warn_emoji = await self.emojis.get("warning", "⚠️")
        await self.load_cogs()
        try:
            await self.load_extension("jishaku")
            self.logger.info("Loaded jishaku")
        except Exception as e:
            self.logger.error(f"Failed to load jishaku: {e}")
        
    async def on_ready(self: "Honest"):
        try:
            synced = await self.tree.sync()
            self.logger.info(f"[MAIN] Synced {len(synced)} command(s)")
        except Exception as e:
            self.logger.error(f"[MAIN] Failed to sync command tree: {e}")
            
        self.logger.info(f"[MAIN] Logged in as {self.user.name}")

    async def _generate_error_code(self) -> str:
        """Generate a random error code asynchronously"""
        chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
        return ''.join(await self.loop.run_in_executor(
            None,
            lambda: random.choices(chars, k=12)
        ))

    async def _send_error_report(self, error_code: str, error: Exception, command_name: str, user: discord.User) -> None:
        error_channel = self.get_channel(self.config['channels'][0]['errors'])
        if not error_channel:
            return
        
        tb = await self.loop.run_in_executor(
            None,
            traceback.format_exception,
            type(error),
            error,
            error.__traceback__
        )
        tb = "".join(tb)
        
        embed = Embed(
            title=f"Error Report | {error_code}",
            color=self.config['embed_colors']['error']
        )
        
        embed.add_field(name="Command", value=f"```{command_name}```", inline=True)
        embed.add_field(name="User", value=f"```{user} ({user.id})```", inline=True)
        embed.add_field(name="Error", value=f"```py\n{tb[:1000]}```", inline=False)
        await error_channel.send(embed=embed)

    async def on_command_error(self, ctx, error):
        if isinstance(error, errors.CommandNotFound):
            return
        
        error = getattr(error, 'original', error)
        error_code = await self._generate_error_code()
        code = f"`{error_code}`"
        
        warn = await self.emojis.get("warning", self.warn_emoji)
        embed = Embed(
            description=f"{warn} {ctx.author.mention}: Error occurred while performing command `{ctx.command.name}`\nUse the given error code to report it to the developers in the [`support server`](https://honest.rocks/discord)",
            color=self.config['embed_colors']['error']
        )
        
        if hasattr(ctx, 'interaction') and ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.send_message(embed=embed)
        else:
            await ctx.send(code, embed=embed)
            
        await self._send_error_report(error_code, error, ctx.command.name, ctx.author)

    async def on_error(self, event, *args, **kwargs):
        error = traceback.format_exc()
        self.logger.error(f"Event error in {event}: {error}")

    async def on_application_command_error(self, interaction: Interaction, error):
        if isinstance(error, app_commands.CommandNotFound):
            return
        
        error = getattr(error, 'original', error)
        error_code = await self._generate_error_code()
        code = f"`{error_code}`"
        
        warn = await self.emojis.get("warning", self.warn_emoji)
        embed = Embed(
            description=f"{warn} {interaction.user.mention}: Error occurred while performing command `{interaction.command.name}`\nUse the error code `{error_code}` to report it to the developers in the [`support server`](https://honest.rocks/discord)",
            color=self.config['embed_colors']['error']
        )
        
        if not interaction.response.is_done():
            await interaction.response.send_message(code, embed=embed)
        else:
            await interaction.followup.send(code, embed=embed)
            
        await self._send_error_report(error_code, error, interaction.command.name, interaction.user)

    async def _register_if_needed(self, user_id: int, username: str, display_name: str) -> None:
        async with self._user_register_lock:  #prevent duplicate registrations
            async with self.db.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1 FROM users WHERE discord_id = %s LIMIT 1", (user_id,))
                    if not await cur.fetchone():
                        await self.db.register_user(
                            discord_id=user_id,
                            username=username,
                            displayname=display_name
                        )
                        self.logger.info(f"[DB] Registered new user: {username} ({user_id})")

    async def interaction_check(self, interaction: Interaction) -> bool:
        asyncio.create_task(self._register_if_needed(
            interaction.user.id,
            interaction.user.name,
            interaction.user.display_name
        ))
        return True

    async def before_invoke_handler(self, ctx):
        asyncio.create_task(self._register_if_needed(
            ctx.author.id,
            ctx.author.name,
            ctx.author.display_name
        ))
