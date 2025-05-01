import logging
import glob
import os
import importlib
import psutil
import asyncio
import math
import datetime
from collections import defaultdict

from typing import List, Optional, cast, Dict, Any, Union
from pathlib import Path
from aiohttp import ClientSession
from colorama import Fore

from discord import (
    Intents,
    Message,
    Guild,
    AuditLogEntry,
    HTTPException,
    Activity,
    ActivityType,
    AllowedMentions,
    PartialMessageable,
    ChannelType,
    User,
    Member,
    ClientUser,
    TextChannel,
    Embed,
)
from discord.ext.commands import AutoShardedBot, ExtensionError

from greed.framework.ipc import IPC
from greed.framework.help import GreedHelp
from greed.framework.discord import Context, CommandErrorHandler, hierarchy
from greed.framework.cluster import Cluster
from greed.framework.pagination import Paginator

from greed.shared.config import (
    Authentication,
    Configuration,
)
from greed.shared.clients import postgres
from greed.shared.clients.postgres import Database

# from greed.shared.clients.settings import Settings
from greed.shared.clients.redis import Redis
from greed.shared.clients.dask import DaskClient
from greed.shared.snipes import Snipe
from greed.framework.script import Script

logger = logging.getLogger("greed/main")


class BotCache:
    def __init__(self):
        self.forcenick = defaultdict(dict)
        self._blacklist = {}
        self._hierarchy = {}
        self.autoresponders = defaultdict(dict)
        self.autoreacts = defaultdict(dict)
        self.afk = defaultdict(dict)
        self.prefixes = defaultdict(str)
        self.settings = defaultdict(dict)
        self.welcome = defaultdict(dict)
        self.leave = defaultdict(dict)


class Greed(AutoShardedBot):
    """
    Custom bot class that extends AutoShardedBot.
    """

    database: Database
    redis: Redis
    dask: DaskClient
    version: str = "0.1.0"
    session: ClientSession
    cluster_id: int
    cluster_count: int
    ipc: Optional[IPC]
    _default_prefix: str
    startup_time: datetime.datetime
    config: Configuration
    _ready_shards: set[int] = set()
    snipes: Snipe
    _hierarchy_cache: Dict[int, bool] = {}
    cache: BotCache

    def __init__(
        self,
        cluster_id: int,
        shard_ids: list[int],
        shard_count: int,
    ):
        super().__init__(
            command_prefix=self.get_prefix,
            help_command=GreedHelp(),
            case_insensitive=True,
            strip_after_prefix=True,
            shard_ids=shard_ids,
            shard_count=shard_count,
            owner_ids=Authentication.owner_ids,
            intents=Intents.all(),
            allowed_mentions=AllowedMentions(
                everyone=False,
                roles=False,
                users=True,
                replied_user=False,
            ),
            activity=Activity(
                type=ActivityType.streaming,
                name="🔗 greed.best",
                url=f"https://twitch.tv/greed",
            ),
        )
        self.cluster_id = cluster_id
        self.cluster_count = math.ceil(shard_count / len(shard_ids))
        self.ipc: Optional[IPC] = None
        self._default_prefix = ","
        self.startup_time = datetime.datetime.utcnow()
        self.config = Configuration()
        self.domain = "https://greed.best"
        self.support_server = "https://discord.gg/greedbot"
        self._ready_shards = set()
        self.snipes = Snipe(self)
        self._hierarchy_cache = {}
        self.cache = BotCache()

    def get_message(self, message_id: int) -> Optional[Message]:
        """
        Fetch a message from the cache.
        """
        return self._connection._get_message(message_id)

    async def hierarchy(
        self,
        ctx: Context,
        member: Union[Member, User],
        allow_self: bool = False,
    ) -> bool:

        bot_member = ctx.guild.me
        author = ctx.author

        if isinstance(member, User):
            return True

        if isinstance(member, Member) and bot_member.top_role <= member.top_role:
            await ctx.embed(
                f"I don't have high enough roles to perform this action on {member.mention}",
                "warned",
            )
            return False

        if author.id == member.id:
            if not allow_self:
                await ctx.embed("You cannot use this command on yourself", "warned")
                return False
            return True

        if author.id == ctx.guild.owner_id:
            return True

        if member.id == ctx.guild.owner_id:
            await ctx.embed("You cannot use this command on the server owner", "warned")
            return False

        if isinstance(author, ClientUser) or not hasattr(author, "top_role"):
            return True

        if author.top_role.is_default():
            await ctx.embed(
                "You need roles with permissions to use this command", "warned"
            )
            return False

        if author.top_role <= member.top_role:
            if author.top_role == member.top_role:
                await ctx.embed(
                    "You cannot target users with the same top role as you",
                    "warned",
                )
            else:
                await ctx.embed(
                    "You cannot target users with higher roles than you", "warned"
                )
            return False

        return True

    async def get_guild_prefix(self, guild_id: int) -> str:
        if guild_id == 1354328297835593778:
            prefix = ";"
            return prefix

        cache_key = f"prefix:guild:{guild_id}"

        if cached := await self.redis.get(cache_key):
            return cached

        if res := await self.pool.fetchrow(
            """
            SELECT prefix FROM prefixes 
            WHERE guild_id = $1
            """,
            guild_id,
        ):
            prefix = res["prefix"] or self._default_prefix
            if prefix:
                await self.redis.set(cache_key, prefix, ex=3600)
            return prefix

        return self._default_prefix

    async def get_user_prefix(self, user_id: int) -> Optional[str]:
        cache_key = f"prefix:user:{user_id}"

        if cached := await self.redis.get(cache_key):
            return cached

        if res := await self.pool.fetchrow(
            """
            SELECT prefix 
            FROM selfprefix 
            WHERE user_id = $1
            """,
            user_id,
        ):
            prefix = res["prefix"]
            if prefix:
                await self.redis.set(cache_key, prefix, ex=3600)
            return prefix

        return None

    async def get_prefix(self, message: Message) -> List[str]:
        if not message.guild:
            return [self._default_prefix]

        prefixes = []

        guild_prefix = await self.get_guild_prefix(message.guild.id)
        user_prefix = await self.get_user_prefix(message.author.id)

        if guild_prefix:
            prefixes.append(guild_prefix)
        if user_prefix:
            prefixes.append(user_prefix)
        if not prefixes:
            prefixes.append(self._default_prefix)

        return prefixes

    async def update_guild_prefix(self, guild_id: int, prefix: str) -> None:
        await self.pool.execute(
            """
            INSERT INTO settings (guild_id, prefix)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) 
            DO UPDATE SET prefix = $2
            """,
            guild_id,
            prefix,
        )
        if prefix:
            await self.redis.set(f"prefix:guild:{guild_id}", prefix, ex=3600)
        else:
            await self.redis.delete(f"prefix:guild:{guild_id}")

    async def update_user_prefix(
        self, user_id: int, prefix: Optional[str] = None
    ) -> None:
        if prefix is None:
            await self.pool.execute(
                'UPDATE "user".settings SET prefix = NULL WHERE user_id = $1',
                user_id,
            )
            await self.redis.delete(f"prefix:user:{user_id}")
        else:
            await self.pool.execute(
                """
                INSERT INTO "user".settings (user_id, prefix)
                VALUES ($1, $2)
                ON CONFLICT (user_id) 
                DO UPDATE SET prefix = $2
                """,
                user_id,
                prefix,
            )
            await self.redis.set(f"prefix:user:{user_id}", prefix, ex=3600)

    async def on_shard_ready(self, shard_id: int) -> None:
        """
        Custom on_shard_ready method that logs shard status.
        """
        logger.info(f"Shard {shard_id} is ready, starting post-connection setup...")

        try:
            logger.info(
                f"Shard ID {Fore.LIGHTGREEN_EX}{shard_id}{Fore.RESET} has {Fore.LIGHTGREEN_EX}spawned{Fore.RESET}."
            )

            await Cluster().coordinator.wait_for_shard(shard_id)

            self._ready_shards.add(shard_id)

            if len(self._ready_shards) == len(self.shard_ids):
                logger.info(
                    f"{Fore.LIGHTGREEN_EX}All shards connected!{Fore.RESET} "
                    f"Cluster {self.cluster_id} is now ready to serve {len(self.guilds)} guilds."
                )

        except Exception as e:
            logger.error(f"Error in shard {shard_id} ready handler: {e}")
            raise

    async def on_shard_resumed(self, shard_id: int) -> None:
        """
        Custom on_shard_resumed method that logs shard status.
        """
        logger.info(
            f"Shard ID {Fore.LIGHTGREEN_EX}{shard_id}{Fore.RESET} has {Fore.LIGHTYELLOW_EX}resumed{Fore.RESET}."
        )
        self._ready_shards.add(shard_id)

        if len(self._ready_shards) == len(self.shard_ids):
            logger.info(
                f"{Fore.LIGHTGREEN_EX}All shards reconnected!{Fore.RESET} "
                f"Cluster {self.cluster_id} is now ready to serve {len(self.guilds)} guilds."
            )

    async def notify(self, guild: Guild, *args, **kwargs) -> Optional[Message]:
        """
        Send a message to the first available channel.
        """
        if not isinstance(guild, Guild):
            logger.error(f"Expected Guild object, got {type(guild).__name__}")
            return

        if (
            guild.system_channel
            and guild.system_channel.permissions_for(guild.me).send_messages
        ):
            try:
                return await guild.system_channel.send(*args, **kwargs)
            except HTTPException:
                return

        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                try:
                    return await channel.send(*args, **kwargs)
                except HTTPException:
                    break

    async def load_patches(self) -> None:
        """
        Load all patches in the framework directory.
        """
        for module in glob.glob(
            "vesta/framework/discord/patches/**/*.py",
            recursive=True,
        ):
            if module.endswith("__init__.py"):
                continue
            module_name = (
                module.replace(os.path.sep, ".").replace("/", ".").replace(".py", "")
            )
            try:
                importlib.import_module(module_name)
                logger.info(f"Patched: {module}")
            except (ModuleNotFoundError, ImportError) as e:
                logger.error(f"Error importing {module_name}: {e}")

    async def _load_extensions(self) -> None:
        """
        Load all plugins in the framework directory.
        """
        loaded_count = 0
        jishaku_loaded = False

        for extension in sorted(Path("greed/plugins").glob("*")):
            if extension.name.startswith(("_", ".")):
                continue

            package = (
                extension.stem
                if extension.is_file() and extension.suffix == ".py"
                else (
                    extension.name
                    if extension.is_dir() and (extension / "__init__.py").exists()
                    else None
                )
            )

            if not package:
                continue

            try:
                if not jishaku_loaded:
                    await self.load_extension("jishaku")
                    print("Loaded jishaku")
                    jishaku_loaded = True
                await self.load_extension(f"greed.plugins.{package}")
                loaded_count += 1
                logger.info(f"Loaded extension: {package}")
            except ExtensionError as exc:
                logger.error(
                    f"Failed to load extension {package}: {exc}",
                    exc_info=True,
                )

    async def _load_cache(self):
        """Initialize all cache data from database"""
        try:
            autoresponder_rows = await self.db.fetch(
                """SELECT guild_id, trig, response, strict, reply FROM autoresponder"""
            )
            for row in autoresponder_rows:
                guild_id = row["guild_id"]
                trig = row["trig"]
                if guild_id not in self.cache.autoresponders:
                    self.cache.autoresponders[guild_id] = {}
                self.cache.autoresponders[guild_id][trig] = {
                    "response": row["response"],
                    "strict": row["strict"],
                    "reply": row["reply"],
                }

            autoreact_rows = await self.db.fetch(
                """SELECT guild_id, keyword, reaction FROM autoreact"""
            )
            for row in autoreact_rows:
                guild_id = row["guild_id"]
                keyword = row["keyword"]
                if guild_id not in self.cache.autoreacts:
                    self.cache.autoreacts[guild_id] = {}
                self.cache.autoreacts[guild_id][keyword] = row["reaction"]

            prefix_rows = await self.db.fetch(
                """SELECT guild_id, prefix FROM prefixes"""
            )
            for row in prefix_rows:
                self.cache.prefixes[row["guild_id"]] = row["prefix"]

            welcome_rows = await self.db.fetch(
                """SELECT guild_id, channel_id, message FROM welcome"""
            )
            for row in welcome_rows:
                guild_id = row["guild_id"]
                self.cache.welcome[guild_id] = {
                    "channel": row["channel_id"],
                    "message": row["message"]
                }

            leave_rows = await self.db.fetch(
                """SELECT guild_id, channel_id, message FROM leave"""
            )
            for row in leave_rows:
                guild_id = row["guild_id"]
                self.cache.leave[guild_id] = {
                    "channel": row["channel_id"],
                    "message": row["message"]
                }

            logger.info("Successfully loaded all cache data")

        except Exception as e:
            logger.error(f"Error loading cache data: {e}")
            raise

    async def setup_hook(self) -> None:
        """
        Initialize bot resources with cluster awareness
        """
        self.session = ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_0 like Mac OS X; en-us)"
                " AppleWebKit/532.9 (KHTML, like Gecko) Version/4.0.5 Mobile/8A293 Safari/6531.22.7"
            },
        )

        self.redis = await Redis.from_url()
        self.glory_cache = await Redis.from_url()
        logger.info("Connected to Redis")

        if self.cluster_id == 0:
            self.database = await postgres.connect()
            logger.info("Connected to PostgreSQL")

            self.dask = await DaskClient.from_url()
            logger.info("Connected to Dask cluster")

            await self.redis.set("vesta:resources:ready", "1")
            logger.info("Shared resources initialized")
        else:
            while not await self.redis.get("vesta:resources:ready"):
                await asyncio.sleep(1)
                logger.info("Waiting for shared resources...")

            self.database = await postgres.connect()
            self.dask = await DaskClient.from_url()
            logger.info("Connected to shared resources")

        await self._load_cache()
        logger.info("Cache initialized")

        tasks = []
        tasks.append(self.load_patches())
        tasks.append(self._load_extensions())
        await asyncio.gather(*tasks)
        logger.info("Loaded patches and packages")

        self.ipc = IPC(self)
        await self.ipc.start()
        logger.info("IPC system initialized")

        self.ipc.add_handler("get_shards", self._handle_get_shards)

        from greed.plugins.config.giveaways.views import GiveawayView

        self.add_view(GiveawayView())
        logger.info("Added persistent Giveaway View")

        from greed.plugins.voicemaster import VmButtons

        self.add_view(VmButtons(self))
        logger.info("Added persistent Voicemaster Buttons View")

        from greed.plugins.voicemaster.views import VoicemasterInterface

        self.add_view(VoicemasterInterface(self))
        logger.info("Added persistent Voicemaster Interface View")

        self._connection._command_sync_flags = 0
        return await super().setup_hook()

    async def _handle_get_shards(self, _: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Handle get_shards IPC requests.
        """
        shard_info = {}
        for shard_id, shard in self.shards.items():
            guilds = len([g for g in self.guilds if g.shard_id == shard_id])
            users = sum(g.member_count for g in self.guilds if g.shard_id == shard_id)
            shard_info[str(shard_id)] = {
                "guilds": guilds,
                "users": users,
                "latency": round(shard.latency * 1000),
            }
        return shard_info

    async def get_context(self, message: Message, *, cls=Context) -> Context:
        """
        Custom get_context method that adds the config attribute to the context.
        """
        context = await super().get_context(message, cls=cls)
        context.config = self.config
        return context

    async def on_command_error(self, context: Context, exception: Exception) -> None:
        """
        Custom error handler for commands.
        """
        from greed.framework.errors import handle_command_error
        await handle_command_error(context, exception)

    async def close(self) -> None:
        """
        Cleanup resources and close the bot
        """
        if self.ipc:
            await self.ipc.cleanup()
        await self.session.close()
        await self.database.close()
        await self.redis.close()
        if hasattr(self, "dask"):
            await self.dask.close()
        await super().close()

    async def start(self, *, reconnect: bool = True) -> None:
        """
        Start the bot with proper shard coordination.
        """
        try:
            self._connection._guild_subscriptions = False

            await super().start(Authentication.token, reconnect=reconnect)

            self._connection._guild_subscriptions = True

            try:
                await self.tree.sync()
            except Exception as e:
                logger.error(f"Error syncing commands: {e}")

        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise

    @property
    def pool(self) -> Database:
        """
        Convenience property to access the database.
        """
        return self.database

    @property
    def db(self) -> Database:
        """
        Convenience property to access the database.
        """
        return self.database

    async def on_audit_log_entry_create(self, entry: AuditLogEntry):
        """
        Custom on_audit_log_entry_create method that dispatches events.
        """
        if not self.is_ready():
            return

        event = f"audit_log_entry_{entry.action.name}"
        self.dispatch(event, entry)

    async def process_commands(self, message: Message) -> None:
        """
        Custom process_commands method that handles command processing.
        """
        if message.author.bot:
            logger.debug(f"Ignoring bot message from {message.author}")
            return

        if not hasattr(self, "_blacklist_cache"):
            self._blacklist_cache = {}

        if message.author.id not in self._blacklist_cache:
            blacklisted = cast(
                bool,
                await self.pool.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1
                        FROM blacklist
                        WHERE user_id = $1
                    )
                    """,
                    message.author.id,
                ),
            )
            self._blacklist_cache[message.author.id] = blacklisted
        else:
            blacklisted = self._blacklist_cache[message.author.id]

        if blacklisted:
            logger.info(f"Blocked blacklisted user: {message.author.id}")
            return

        if message.guild:
            channel = message.channel
            perms = channel.permissions_for(message.guild.me)
            if not (perms.send_messages and perms.embed_links and perms.attach_files):
                logger.warning(
                    f"Missing permissions in {message.guild.name} #{channel.name}: "
                    f"send_messages={perms.send_messages}, "
                    f"embed_links={perms.embed_links}, "
                    f"attach_files={perms.attach_files}"
                )
                return

        ctx = await self.get_context(message)
        logger.debug(f"Context created: valid={ctx.valid}, command={ctx.command}")

        if not ctx.valid:
            if message.content.startswith(self._default_prefix):
                try:
                    command = (
                        message.content[len(self._default_prefix) :]
                        .strip()
                        .split()[0]
                        .lower()
                    )
                    logger.debug(f"Checking command: {command}")
                    if message.guild:
                        enabled = await self.db.fetchval(
                            """
                            SELECT enabled 
                            FROM stats.config 
                            WHERE guild_id = $1
                            """,
                            message.guild.id,
                        )
                        logger.debug(f"Wordstats enabled: {enabled}")
                        if enabled:
                            custom_command = await self.db.fetchrow(
                                """
                                SELECT word 
                                FROM stats.custom_commands 
                                WHERE guild_id = $1 AND command = $2
                                """,
                                message.guild.id,
                                command,
                            )
                            logger.debug(f"Custom command found: {custom_command}")
                            if custom_command:
                                wordstats = self.get_cog("WordStats")
                                logger.debug(f"WordStats cog found: {wordstats}")
                                if wordstats:
                                    await wordstats.process_custom_command(ctx, command)
                                    logger.debug("Custom command processed")
                                    return

                        alias_cog = self.get_cog("Alias")
                        if alias_cog and await alias_cog.process_aliases(ctx):
                            logger.debug("Alias processed")
                            return

                    logger.debug(f"Invalid command with prefix: {command}")
                except IndexError:
                    logger.debug("Empty command with prefix")
                    return
            return

        if (
            ctx.invoked_with
            and isinstance(message.channel, PartialMessageable)
            and message.channel.type != ChannelType.private
        ):
            logger.warning(
                f"Discarded partial message (ID: {message.id}) in channel: {message.channel}"
            )
        else:
            try:
                await self.invoke(ctx)
                if ctx.command:
                    logger.info(
                        f"Command {ctx.command.name} executed "
                        f"by {ctx.author} ({ctx.author.id}) "
                        f"in {ctx.guild.name if ctx.guild else 'DM'}"
                    )
            except Exception as e:
                logger.error(
                    f"Error executing command '{ctx.command.name if ctx.command else 'unknown'}': {e}",
                    exc_info=True,
                )

        if not ctx.valid:
            self.dispatch("message_without_command", ctx)

    def _get_total_shards(self) -> int:
        """
        Calculate total number of shards across all clusters
        """
        return 4

    def _get_shard_ids(self) -> list[int]:
        """
        Calculate shard IDs for this cluster
        """
        shards_per_cluster = self._get_total_shards() // (psutil.cpu_count() or 1)
        start = self.cluster_id * shards_per_cluster
        return list(range(start, start + shards_per_cluster))

    async def guild_count(self) -> int:
        """
        Get the total number of guilds the bot is in across all clusters.

        Returns:
            The total number of guilds
        """
        if not self.ipc:
            return len(self.guilds)

        responses = await self.ipc.broadcast("get_guild_count")
        total_guilds = len(self.guilds)

        for cluster_id, count in responses.items():
            if isinstance(count, int):
                total_guilds += count

        return total_guilds

    async def user_count(self) -> int:
        """
        Get the total number of users the bot can see across all clusters.

        Returns:
            The total number of users
        """
        if not self.ipc:
            return sum(guild.member_count for guild in self.guilds)

        responses = await self.ipc.broadcast("get_user_count")
        total_users = sum(guild.member_count for guild in self.guilds)

        for cluster_id, count in responses.items():
            if isinstance(count, int):
                total_users += count

        return total_users

    def get_timestamp(
        self, dt: Optional[datetime.datetime] = None, style: str = "R"
    ) -> str:
        if dt is None:
            dt = datetime.datetime.now()

        if style == "R":
            delta = dt - datetime.datetime.now()
            if delta.total_seconds() < 0:
                return f"<t:{int(dt.timestamp())}:R>"
            return f"<t:{int(dt.timestamp())}:R>"
        elif style == "f":
            return f"<t:{int(dt.timestamp())}:f>"
        elif style == "F":
            return f"<t:{int(dt.timestamp())}:F>"
        elif style == "d":
            return f"<t:{int(dt.timestamp())}:d>"
        elif style == "D":
            return f"<t:{int(dt.timestamp())}:D>"
        elif style == "t":
            return f"<t:{int(dt.timestamp())}:t>"
        elif style == "T":
            return f"<t:{int(dt.timestamp())}:T>"
        else:
            return f"<t:{int(dt.timestamp())}:f>"

    async def check_bot_hierarchy(self, guild: Guild) -> bool:
        """
        Check if the bot's role is in the top 5 roles of the guild.

        Args:
            guild: The guild to check

        Returns:
            bool: True if bot's role is in top 5, False otherwise

        Note:
            Results are cached for 1 minute to reduce API calls
        """
        try:
            if guild.id in self._hierarchy_cache:
                return self._hierarchy_cache[guild.id]

            if not guild.me:
                return False

            roles = sorted(guild.roles, key=lambda x: x.position, reverse=True)[:5]
            result = guild.me.top_role in roles

            self._hierarchy_cache[guild.id] = result
            asyncio.create_task(self._clear_hierarchy_cache(guild.id))

            return result
        except Exception as e:
            logger.error(f"Error checking bot hierarchy in guild {guild.id}: {e}")
            return False

    async def _clear_hierarchy_cache(self, guild_id: int) -> None:
        """
        Clear the hierarchy cache for a guild after 1 minutes.

        Args:
            guild_id: The guild ID to clear from cache
        """
        await asyncio.sleep(60)
        self._hierarchy_cache.pop(guild_id, None)

    async def on_ready(self) -> None:
        """
        Handle post-startup tasks
        """
        logger.info(f"Bot is ready! Connected to {len(self.guilds)} guilds")

        for guild in self.guilds:
            try:
                await guild.chunk()
            except Exception as e:
                logger.warning(f"Failed to chunk guild {guild.id}: {e}")
                continue

    async def create_embed(self, code: str, **kwargs):
        """Creates an embed from the given code using the Script class."""
        builder = Script(code, kwargs.get("user", None))
        return builder

    def build_error(self, message: str) -> dict:
        """Builds an error embed dictionary."""
        return {
            "embed": Embed(
                color=0xffffff,
                description=f"<:warn:1356196281273548820> {message}",
            )
        }

    async def send_embed(self, destination: TextChannel, code: str, **kwargs):
        """Sends an embed to the specified channel using the Script class."""
        view = kwargs.pop("view", None)
        builder = await self.create_embed(code, **kwargs)
        try:
            return await builder.send(destination, view=view)
        except HTTPException as exc:
            if exc.code == 50006:
                return await destination.send(
                    **self.build_error(
                        "Something went wrong while parsing this embed script."
                    )
                )
            raise


__all__ = ("Greed", "Context", "Paginator")
