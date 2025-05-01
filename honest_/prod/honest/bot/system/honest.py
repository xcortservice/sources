# from system.managers.logger import make_dask_sink
# make_dask_sink("Honest") # logger overwritting
import discord_ios
import os
import traceback
from asyncio import ensure_future, gather, sleep
from contextlib import suppress
from datetime import datetime, timedelta
from os import getpid
from pathlib import Path
from typing import Any, List, Optional, Union

import tuuid
from aiohttp import ClientSession
from data.config import CONFIG
from discord import (AllowedMentions, AuditLogEntry, CustomActivity,
                     Embed, Guild, HTTPException, Intents, Member, Message,
                     Streaming, User, abc, utils)
from discord.ext import commands
from discord.ext.commands import (AutoShardedBot, BotMissingPermissions,
                                  when_mentioned_or)
from discord.globals import get_global, set_global # type: ignore
from loguru import logger
from psutil import Process
from .classes.builtins import get_error
from tools import lock
from tornado.ioloop import IOLoop

from .classes import Script
from .classes.cache import cache
from .classes.database import Database, Record
from .classes.exceptions import EmbedError
from .classes.objects import RedisMock
from .classes.redis import HonestRedis
from .managers import get_statistics
from .managers.errors import Errors
from .managers.watcher import RebootRunner
from .patch import Help
from .patch.context import Context
from .services import setup
from .services.bot.levels import Level, LevelSettings
from .services.bot.snipe import Snipe
from .services.socials import repost
from .worker import start_dask

set_global("logger", logger)
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_RETAIN"] = "True"


async def get_lines():
    lines = 0
    for directory in [x[0] for x in os.walk("./") if ".git" not in x[0]]:
        for file in os.listdir(directory):
            if file.endswith(".py"):
                lines += len(open(f"{directory}/{file}", "r").read().splitlines())

    return lines


class Honest(AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=self.get_prefix,
            allowed_mentions=AllowedMentions(users=True, roles=False, everyone=False),
            activity=CustomActivity(name="🔗 honest.rocks/discord"),
            strip_after_prefix=True,
            intents=Intents().all(),
            case_insensitive=True,
            auto_update=False,
            owner_ids=CONFIG["owners"],
            anti_cloudflare_ban=True,
            help_command=None,
            shard_count=1,
            *args,
            **kwargs,
        )
        self.process = Process(getpid())
        self.config = CONFIG
        self.filled = False
        self.ioloop: IOLoop
        self.db = Database()
        self.errors = Errors(self)
        self.color = 0x747F8D
        self.status_filter = dict()
        self.redis = HonestRedis()
        self.snipes = Snipe(self)
        self.object_cache = RedisMock()
        self.startup_time = datetime.now()
        self.invite_regex = r"(https?://)?(www.|canary.|ptb.)?(discord.gg|discordapp.com/invite|discord.com/invite)[\/\\]?[a-zA-Z0-9]+/?"
        self.dm_blacklist: List[int] = list()
        self.command_dict = None
        self.webserver = None
        self.blacktea_matches = {}
        self.blackjack_matches = []
        self.blacktea_messages = {}
        self.runner = RebootRunner(self, ["extensions", "system", "data"])
        self.loaded = False
        self._closing_task = None
        self._cd = commands.CooldownMapping.from_cooldown(
            5.0, 10.0, commands.BucketType.user
        )

    async def close(self):
        """Overrides built-in close()"""
        await self.webserver.server.close()
        await self.db.close()
        try:
            await super().close()
            os._exit(0)
        except Exception:
            pass
        os._exit(0)

    async def get_prefix(self: "Honest", message: Message):
        server = await self.db.fetchval(
            """SELECT prefix FROM config WHERE guild_id = $1""", message.guild.id
        )
        user = await self.db.fetchval(
            """SELECT prefix FROM user_config WHERE user_id = $1""", message.author.id
        )
        if not server:
            server = ","
        if user:
            if message.content.strip().startswith(user):
                return when_mentioned_or(user)(self, message)
        return when_mentioned_or(server)(self, message)

    async def setup_dask(self: "Honest"):
        self.dask = await start_dask(self, "127.0.0.1:8787")

    def get_command_dict(self: "Honest") -> list:
        if self.command_dict:
            return self.command_dict

        def get_command_invocations(command, prefix=""):
            invocations = []

            base_command = prefix + command.name
            invocations.append(base_command)

            for alias in command.aliases:
                invocations.append(prefix + alias)

            if isinstance(command, commands.Group):
                for subcommand in command.commands:
                    sub_invocations = get_command_invocations(
                        subcommand, prefix=base_command + " "
                    )
                    for alias in command.aliases:
                        sub_invocations.extend(
                            get_command_invocations(
                                subcommand, prefix=prefix + alias + " "
                            )
                        )
                        invocations.extend(sub_invocations)

            return invocations

        self.command_dict = []
        for command in self.walk_commands():
            for invocation in get_command_invocations(command):
                self.command_dict.append(invocation)
        return self.command_dict

    async def setup_database(self: "Honest") -> bool:
        with open("data/postgresql.sql", "r") as file:
            queries = file.read().split(";")
        failed = []
        for query in queries:
            query = f"{query};"
            if "EXISTS" in query:
                table_name = query.split("EXISTS ", 1)[1].split(" (")[0]
            try:
                await self.db.execute(query)
            except Exception as e:
                failed.append((table_name, get_error(e)))
        if len(failed) == 0:
            logger.info(
                f"Executed All of the {len(queries)} Database Queries Successfully"
            )
        else:
            logger.info(
                f"Failed to do queries to the following tables {', '.join(f[0] for f in failed)}"
            )
            errors = "\n".join(f"{f[0]} - {f[1]}" for f in failed)
            logger.info(f"Errors: \n{errors}\n{query}")
        return True

    async def __load(self: "Honest", cog: str):
        try:
            await self.load_extension(cog)
            logger.info(f"Loaded {cog}")
        except commands.errors.ExtensionAlreadyLoaded:
            pass
        except Exception as e:
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.info(f"Failed to load {cog} due to exception: {tb}")

    async def load_cogs(self: "Honest"):
        tasks = []
        inner_files = ["commands", "events"]
        for path in Path("extensions/").glob("*"):
            if "__pycache__" not in str(path):
                cog_path = "extensions." + str(path).split("extensions/")[1].replace(
                    "/", "."
                ).replace("\\", ".")
                for file in inner_files:
                    tasks.append(self.__load(f"{cog_path}.{file}"))
        await gather(*tasks)

    async def setup_hook(self: "Honest"):
        self.http.iterate_local_addresses = True
        self.session = ClientSession()
        await self.setup_emojis()
        self.ioloop = IOLoop.current()
        await self.load_extension("jishaku")
        await self.setup_dask()
        self.levels = Level(0.5, self)
        await self.db.connect()
        await self.redis.from_url()
        self.redis.bot = self
        await self.redis.setup_pubsub(channel="Honest1")
        await setup(self)
        await self.setup_database()
        self.check(self.command_check)

    async def command_check(self: "Honest", ctx: Context):
        COOLDOWN_MAPPING = {
            "guild": ctx.guild.id,
            "channel": ctx.channel.id,
            "user": ctx.author.id,
            "member": ctx.author.id,
        }
        missing_perms = []
        if await self.db.fetchrow(
            """SELECT * FROM blacklists WHERE object_id = $1 AND object_type = $2""",
            ctx.author.id,
            "user",
        ):
            return False
        if await self.db.fetchrow(
            """SELECT * FROM blacklists WHERE object_id = $1 AND object_type = $2""",
            ctx.guild.id,
            "guild",
        ):
            return False
        if not ctx.channel.permissions_for(ctx.guild.me).send_messages:
            missing_perms.append("send_messages")
        if not ctx.channel.permissions_for(ctx.guild.me).embed_links:
            missing_perms.append("embed_links")
        if not ctx.channel.permissions_for(ctx.guild.me).attach_files:
            missing_perms.append("attach_files")
        if len(missing_perms) > 0:
            raise BotMissingPermissions(missing_perms)
        c = "" if not ctx.aliased else "a"
        if retry_after := await ctx.bot.object_cache.ratelimited(
            f"rl:user_commands{c}{ctx.author.id}", 2, 4
        ):
            raise commands.CommandOnCooldown(None, retry_after, None)
        if cooldown_override := ctx.command.extras.get("cooldown"):

            if len(cooldown_override) == 2:
                limit, timeframe = cooldown_override
                cooldown_type = "member"
            else:
                limit, timeframe, cooldown_type = cooldown_override

            if retry_after := await ctx.bot.object_cache.ratelimited(
                f"rl:{ctx.command.qualified_name}{c}:{COOLDOWN_MAPPING.get(cooldown_type.lower())}",
                limit,
                timeframe,
            ):
                raise commands.CommandOnCooldown(
                    ctx.command, retry_after, cooldown_type
                )
        if ctx.command.qualified_name in (
            await self.db.fetchval(
                """SELECT disabled_commands FROM config WHERE guild_id = $1""",
                ctx.guild.id,
            )
            or []
        ):
            return False
        return True

    async def create_embed(self: "Honest", code: str, **kwargs: Any):
        builder = Script(code, **kwargs)
        await builder.compile()
        return builder

    async def process_commands(self: "Honest", message: Message):
        return await super().process_commands(message)

    async def user_count(self: "Honest") -> int:
        return sum(i for i in self.get_all_members())

    async def guild_count(self: "Honest") -> int:
        return len(self.guilds)

    async def channel_count(self: "Honest") -> int:
        return sum(len(i.channels) for i in self.guilds)

    async def role_count(self: "Honest") -> int:
        return sum(len(i.roles) for i in self.guilds)

    async def send_embed(
        self: "Honest",
        destination: Union[Context, abc.GuildChannel],
        code: str,
        **kwargs: Any,
    ):
        view = kwargs.pop("view", None)
        k = {}
        if view:
            k["view"] = view
        builder = await self.create_embed(code, **kwargs)
        try:
            return await builder.send(destination, **k)
        except HTTPException as exc:
            if exc.code == 50006:
                return await destination.send(
                    **self.build_error(
                        "Something went wrong while parsing this embed script."
                    )
                )
        except EmbedError as error:
            return await destination.send(
                embed=Embed(color=CONFIG["colors"]["warning"], description=str(error))
            )
            raise

    async def send_exception(self: "Honest", ctx: Context, exception: Exception):
        code = tuuid.tuuid()
        tb = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
        await self.db.execute(
            """INSERT INTO traceback (command, error_code, error_message, guild_id, channel_id, user_id, content) VALUES($1, $2, $3, $4, $5, $6, $7)""",
            ctx.command.qualified_name if ctx.command else "repost",
            code,
            tb,
            ctx.guild.id,
            ctx.channel.id,
            ctx.author.id,
            ctx.message.content,
        )
        return await ctx.send(
            content=f"{code}",
            embed=Embed(
                description=f"{CONFIG['emojis']['warning']} {ctx.author.mention}: An error occurred while performing command **{ctx.command.qualified_name if ctx.command else 'repost'}**. Use the given error code to report it to the developers in the [support server](https://{CONFIG.get('domain')}/discord)",
                color=0xE69705,
            ),
        )

    @cache(key="emojis", ttl=300)
    async def get_emojis(self: "Honest"):
        return await self.fetch_application_emojis()

    @lock("DM")
    async def send(
        self: "Honest",
        member: Member,
        content: str,
        embed_code: Optional[bool] = False,
        *args: Any,
        **kwargs: Any,
    ):
        rl = await self.object_cache.ratelimited("DMS", 10, 30)
        if rl != 0:
            await sleep(rl)
        if member.id in self.dm_blacklist:
            return
        if embed_code:
            try:
                return await self.send_embed(
                    member, content, embed_code, *args, **kwargs
                )
            except Exception:
                self.dm_blacklist.append(member.id)
        else:
            try:
                return await member.send(*args, **kwargs)
            except Exception:
                self.dm_blacklist.append(member.id)

    async def check_member(
        self,
        member: Member,
        guild: Guild,
        config: Record,
        dispatch: Optional[bool] = True,
    ) -> tuple:
        whitelist = config.whitelist or []
        if config.raid_status is True and member.id not in whitelist:
            if datetime.now() > config.raid_expires_at:
                await self.db.execute(
                    """UPDATE antiraid SET raid_triggered_at = NULL, raid_expires_at = NULL WHERE guild_id = $1""",
                    guild.id,
                )
            else:
                return True, config.join_punishment, "Raid is active"
        if member.id in whitelist:
            return False, None, None
        if (
            config.new_accounts is True
            and member.created_at
            < datetime.now() - timedelta(days=config.new_account_threshold)
        ):
            return True, config.new_account_punishment, "New Account"
        if config.no_avatar and not member.avatar:
            return True, config.no_avatar_punishment, "No Avatar"
        if (
            await self.object_cache.ratelimited(
                f"raid:{guild.id}", config.join_threshold, 60
            )
            != 0
        ):
            expiration = datetime.now() + timedelta(minutes=10)
            await self.db.execute(
                """INSERT INTO antiraid (guild_id, raid_status, raid_triggered_at, raid_expires_at) VALUES($1, $2, $3, $4) ON CONFLICT(guild_id) DO UPDATE SET raid_status = excluded.raid_status, raid_triggered_at = excluded.raid_triggered_at, raid_expires_at = excluded.raid_expires_at""",
                guild.id,
                True,
                datetime.now(),
                expiration,
            )
            self.dispatch("raid", member, guild, expiration)
            return True, config.join_punishment, "Mass Join"

        return False, None, None

    async def check_raid(self, member: Member) -> tuple:
        guild = member.guild

        async def execute():
            if not (
                config := await self.db.fetchrow(
                    """SELECT * FROM antiraid WHERE guild_id = $1""", guild.id
                )
            ):
                return False
            value = False
            async with self.locks[f"antiraid:{guild.id}"]:
                punish, punishment_value, reason = await self.check_member(
                    member, guild, config
                )
                if punish:
                    if punishment_value == 1:
                        await member.kick(reason=reason)
                        value = True
                    else:
                        await member.ban(reason=reason)
                        value = True
            return value

        _ = await execute()
        if not _:
            whitelist = await self.db.fetchrow(
                """SELECT whitelist, whitelist_whitelist FROM config WHERE guild_id = $1""",
                member.guild.id,
            )
            if whitelist:
                if whitelist.whitelist:
                    if member.id not in whitelist.whitelist_whitelist:
                        return self.dispatch("unwhitelisted_join", member)
            await self.dispatch_welcome(member)
            if not member.pending:
                self.dispatch(
                    "member_agree",
                    member,
                )

    async def create_emoji(self: "Honest", name: str, data: bytes):
        app_emojis = await self.get_emojis()
        for emoji in app_emojis:
            if emoji.name == name:
                return emoji
        return await self.create_application_emoji(name=name, image=data)

    async def on_ready(self: "Honest"):
        if not self.loaded:
            await self.levels.setup(self)
            await self.load_cogs()
            await self.load_extension("system.classes.web")
            self.webserver = self.get_cog("WebServer")
            await self.runner.start()
            self.statistics = await get_statistics(self)

    async def on_message(self: "Honest", message: Message):
        with suppress(AttributeError):
            if (
                not (message.author.bot)
                and (message.channel.permissions_for(message.guild.me).send_messages)
                and (message.guild)
                and self.is_ready()
            ):
                ctx = await self.get_context(message)
                self.dispatch("context", ctx)
                if not ctx.valid:
                    self.dispatch("valid_message", ctx)
                    if message.content.lower().startswith(self.user.name.lower()):
                        self.dispatch("media_repost", ctx)
                    if await self.db.fetchval(
                        """SELECT reposting FROM config WHERE guild_id = $1 AND reposting = TRUE""",
                        ctx.guild.id,
                    ):
                        repost(self, message)
                self.dispatch("afk_check", ctx)
                if message.mentions_bot(strict=True):
                    if (
                        await self.object_cache.ratelimited(
                            f"prefix_pull_message:{ctx.guild.id}", 3, 5
                        )
                        == 0
                    ):
                        guild_prefix, user_prefix = await ctx.display_prefix(False)
                        user_prefix_value = (
                            f"\nyour user prefix: `{user_prefix}`"
                            if user_prefix
                            else ""
                        )
                        return await ctx.normal(
                            f"the guild's prefix is: `{guild_prefix}` `{user_prefix_value}`"
                        )
            await self.process_commands(message)

    async def on_message_edit(self: "Honest", before: Message, after: Message):
        if before.content != after.content and not after.author.bot:
            await self.on_message(after)

    async def on_command_error(self: "Honest", ctx: Context, exception: Exception):
        return await self.errors.handle_exceptions(ctx, exception)

    async def dispatch_welcome(self: "Honest", member: Member) -> None:
        if not (
            config := await self.db.fetchrow(
                """SELECT welcome_message, welcome_channel FROM config WHERE guild_id = $1""",
                member.guild.id,
            )
        ):
            return
        if not config.welcome_message or not config.welcome_channel:
            return
        if not (welcome_channel := member.guild.get_channel(config.welcome_channel)):
            return
        self.dispatch(
            "welcome", member.guild, member, welcome_channel, config.welcome_message
        )

    async def on_member_join(self: "Honest", member: Member) -> None:
        return await self.check_raid(member)

    async def on_audit_log_entry_create(self, entry: AuditLogEntry) -> None:
        if not self.is_ready() or not entry.guild:
            return

        event = "audit_log_entry_" + entry.action.name
        self.dispatch(
            event,
            entry,
        )

    async def on_member_remove(self: "Honest", member: Member) -> None:
        if member.premium_since:
            self.dispatch(
                "member_unboost",
                member,
            )
        if not (
            config := await self.db.fetchrow(
                """SELECT leave_message, leave_channel FROM config WHERE guild_id = $1""",
                member.guild.id,
            )
        ):
            return
        if (not config.leave_message) or (not config.leave_channel):
            return
        if not (leave_channel := member.guild.get_channel(config.leave_channel)):
            return
        self.dispatch(
            "leave", member.guild, member, leave_channel, config.leave_message
        )

    async def on_user_update(self: "Honest", before: User, after: User):
        if not all(
            [
                before.global_name != after.global_name,
                before.name != after.name,
                before.display_name != after.name,
            ]
        ):
            if before.name != after.name:
                self.dispatch("username_submit", before.name)
            self.dispatch("username_change", before, after)
        if before.display_avatar.key != after.display_avatar.key:
            self.dispatch("avatar_change", before, after)

    async def on_member_update(self, before: Member, member: Member) -> None:
        if before.display_avatar.key != member.display_avatar.key:
            self.dispatch("avatar_change", before, member)
        if before.nick and not member.nick:
            self.dispatch("username_change", before, member)
        if before.nick and member.nick:
            if before.nick != member.nick:
                self.dispatch("username_change", before, member)
        if before.pending and not member.pending:
            self.dispatch(
                "member_agree",
                member,
            )
            await self.dispatch_welcome(member)

        if booster_role := member.guild.premium_subscriber_role:
            if (booster_role in before.roles) and (booster_role not in member.roles):
                self.dispatch(
                    "member_unboost",
                    before,
                )

            elif (
                system_flags := member.guild.system_channel_flags
            ) and system_flags.premium_subscriptions:
                return
            elif (booster_role not in before.roles) and (booster_role in member.roles):
                self.dispatch(
                    "member_boost",
                    member,
                )
                if not (
                    config := await self.db.fetchrow(
                        """SELECT boost_message, boost_channel FROM config WHERE guild_id = $1""",
                        member.guild.id,
                    )
                ):
                    return
                if not config.boost_message or not config.boost_channel:
                    return
                if not (
                    boost_channel := member.guild.get_channel(config.boost_channel)
                ):
                    return
                self.dispatch(
                    "boost", member.guild, member, boost_channel, config.boost_message
                )
        else:
            if not before.premium_since and member.premium_since:
                self.dispatch("member_boost", member)
            elif before.premium_since and not member.premium_since:
                self.dispatch("member_unboost", before)

    def run(self: "Honest"):
        super().run(self.config["token"])

    @cache(ttl="1m", key="context:{message.id}")
    async def get_context_cached(self: "Honest", message: Message) -> Context:
        return await super().get_context(message, cls=Context)

    async def get_context(self: "Honest", message: Message, **kwargs) -> Context:
        if kwargs.pop("cached", True) is False:
            context = await super().get_context(message, cls=Context)
        else:
            context = await self.get_context_cached(message)
        if not self.filled and self.is_ready():
            await self._fill(context)
            self.filled = True
        return context

    @cache(key="fetch_message:{message_id}", ttl=300)
    async def fetch_message(self: "Honest", channel: abc.GuildChannel, message_id: int):
        if message := utils.get(self.cached_messages, id=message_id):
            return message
        try:
            return await channel.fetch_message(message_id)
        except HTTPException:
            return None

    async def get_reference(self: "Honest", message: Message):
        if message.reference:
            if msg := message.reference.cached_message:
                return msg
            else:
                g = self.get_guild(message.reference.guild_id)
                if not g:
                    return None
                c = g.get_channel(message.reference.channel_id)
                if not c:
                    return None
                return await self.fetch_message(c, message.reference.message_id)
        return None

    async def setup_emojis(self: "Honest"):
        if not CONFIG["emojis"]["interface"].get("lock", "") not in ("", ""):
            for p in Path("assets/emojis").glob("*"):
                path_name = str(p).split("/")[-1]
                if path_name.lower() == "embeds":
                    for image in p.glob("*"):
                        emoji_name = str(image).split("/")[-1].split(".")[0]
                        if CONFIG["emojis"].get(emoji_name, "") != "":
                            continue
                        with open(str(image), "rb") as file:
                            image_bytes = file.read()
                        emoji = await self.create_emoji(emoji_name, image_bytes)
                        CONFIG["emojis"][emoji_name] = str(emoji)
                else:
                    if (
                        list(CONFIG["emojis"].get(path_name.lower(), {}).values())[0]
                        != ""
                    ):
                        continue
                    CONFIG["emojis"][path_name.lower()] = {}
                    for image in p.glob("*"):
                        emoji_name = str(image).split("/")[-1].split(".")[0]
                        with open(str(image), "rb") as file:
                            image_bytes = file.read()
                        emoji = await self.create_emoji(emoji_name, image_bytes)
                        CONFIG["emojis"][path_name.lower()][emoji_name] = str(emoji)
            with open("data/config.py", "w") as file:
                value = """
from discord import Intents  
from dotenv import load_dotenv
import os

load_dotenv(verbose = True)"""
                value += f"\nCONFIG = {CONFIG}"
                file.write(value)
            logger.info("Successfully setup all Emojis and the configuration")
            await self.close()