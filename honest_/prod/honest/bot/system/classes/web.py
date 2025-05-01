import datetime
import json as jsonn
import socket
import traceback
from asyncio import ensure_future
from base64 import b64decode
from collections import defaultdict
from typing import Dict, FrozenSet, Iterable

import orjson
from data.config import CONFIG
from discord import Client
from discord.ext import tasks
from discord.ext.commands import AutoShardedBot, Cog
from loguru import logger
from sanic import Sanic, file, json, raw, response
from sanic.request import Request
from sanic.router import Route
from sanic_cors import CORS
from tuuid import tuuid

from ..patch.help import map_check
from ..worker import offloaded
from .github import GithubPushEvent

ADDRESS = CONFIG["webserver"]

DOMAIN = f"api.{CONFIG['domain']}"


def check_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except socket.error:
            return True  # Port is in use
    return False  # Port is available


@offloaded
def check_port(port: int):
    EXCLUDED = ["cloudflared"]
    import subprocess

    result = subprocess.run(
        ["sudo", "lsof", "-n", f"-i:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Check and print output
    lines = result.stdout.splitlines()
    data = []
    row_names = [
        "command",
        "pid",
        "user",
        "fd",
        "type",
        "device",
        "size/off",
        "node",
        "range",
        "status",
    ]
    for i, line in enumerate(lines, start=1):
        if i != 1:
            rows = [m for m in line.split(" ") if m != ""]
            data.append(
                {row_names[num - 1]: value for num, value in enumerate(rows, start=1)}
            )
    return [d for d in data if d.get("name") not in EXCLUDED]


@offloaded
def kill_process(data: list):
    import subprocess

    killed_processes = []
    for d in data:
        if d["pid"] in killed_processes:
            continue
        try:
            subprocess.run(
                ["kill", "-9", str(d["pid"])],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            killed_processes.append(d["pid"])
        except Exception:
            pass
    return True


#
class WebServer(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.app = Sanic(name=f"{self.bot.user.name.title().replace(' ', '-')}")
        cors = CORS(self.app, resources={r"/*": {"origins": "*"}})  # noqa: F841
        self.server = None
        self._commands = None
        self.statistics = None
        self.domain = DOMAIN
        self.assets = {}
        self.app.add_route(self.commands, "/", methods=["GET", "POST", "OPTIONS"])
        self.app.add_route(
            self.lastfm_token, "/lastfm", methods=["GET", "POST", "OPTIONS"]
        )
        self.app.add_route(
            self.statistics_, "/statistics", methods=["GET", "POST", "OPTIONS"]
        )
        self.app.add_route(self.status, "/status", methods=["GET", "POST", "OPTIONS"])
        self.app.add_route(self.asset, "/asset/<path>", methods=["GET", "OPTIONS"])
        self.app.add_route(
            self.github, "/github", methods=["POST", "PUT", "GET", "OPTIONS"]
        )
        self.app.add_route(self.avatar, "/avatar", methods=["GET", "OPTIONS"])
        self.app.add_route(self.shards, "/shards", methods=["GET", "OPTIONS"])
        self.app.add_route(
            self.message_logs, "/logs/<identifier>", methods=["GET", "OPTIONS"]
        )

    async def lastfm_token(self, request: Request):
        logger.info(request.url)
        await self.bot.db.execute(
            """INSERT INTO lastfm_data (user_id, token) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET token = excluded.token""",
            request.url.split("?user_id=", 1)[1].split("&", 1)[0],
            request.url.split("&token=", 1)[1],
        )
        return json({"message": "Token saved"})

    @tasks.loop(minutes=1)
    async def redump_loop(self):
        logger.info("dumping statistics and commands to the webserver")
        try:
            self._commands = await self.dump_commandsXD()
            self.statistics = {
                "guilds": len(self.bot.guilds),
                "users": sum(self.bot.get_all_members()),
            }
            await self.bot.redis.set("statistics", orjson.dumps(self.statistics))
            await self.bot.redis.set("commands", orjson.dumps(self._commands))
        except Exception as error:
            exc = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            logger.error(
                f"Unhandled exception in internal background task redump_loop. {type(error).__name__:25} > \n {error} \n {exc}"
            )

    @Cog.listener("on_guild_remove")
    async def decrease_guilds(self, guild):
        self.statistics["guilds"] -= 1
        self.statistics["users"] = sum(self.bot.get_all_members())
        await self.bot.redis.set("statistics", orjson.dumps(self.statistics))

    @Cog.listener("on_guild_add")
    async def increase_guilds(self, guild):
        self.statistics["guilds"] += 1
        self.statistics["users"] = sum(self.bot.get_all_members())
        await self.bot.redis.set("statistics", orjson.dumps(self.statistics))

    async def run(self):
        if check_port_in_use(ADDRESS["host"], ADDRESS["port"]):
            await kill_process(await check_port(ADDRESS["port"]))
        self.server = await self.app.create_server(
            **ADDRESS, return_asyncio_server=True
        )

        if self.server is None:
            return

        await self.server.startup()
        await self.server.serve_forever()

    async def dump_commandsXD(self):
        commands = {"categories": []}

        def get_usage(command):
            if not command.clean_params:
                return "None"
            return ", ".join(m for m in [str(c) for c in command.clean_params.keys()])

        def get_aliases(command):
            if len(command.aliases) == 0:
                return ["None"]
            return command.aliases

        def get_category(command):
            if "settings" not in command.qualified_name:
                return command.cog_name
            else:
                return "settings"

        excluded = ["webserver", "jishaku", "developer", "git"]
        for command in self.bot.walk_commands():
            description = command.description or command.help
            if cog := command.cog_name:
                if cog.lower() in excluded:
                    continue
                if command.hidden or not description:
                    continue
                cog_name = command.cog_name.replace("Commands", "")
                if not commands.get(cog_name):
                    commands[cog_name] = []
                if not command.perms:
                    permissions = ["send_messages"]
                else:
                    permissions = command.perms
                if len(command.checks) > 0:
                    permissions.extend(
                        [
                            map_check(c).replace("`", "")
                            for c in command.checks
                            if map_check(c)
                        ]
                    )
                permissions = list(set(permissions))
                cog_name = command.extras.get("cog_name", cog_name)
                commands[cog_name].append(
                    {
                        "name": command.qualified_name,
                        "help": description or "",
                        "brief": (
                            [permissions.replace("_", " ").title()]
                            if not isinstance(permissions, list)
                            else [_.replace("_", " ").title() for _ in permissions]
                        ),
                        "usage": (
                            [
                                f"{k.replace('_', ' or ')}"
                                for k in command.clean_params.keys()
                            ]
                            if not command.qualified_name == "help"
                            else ["command or group"]
                        ),
                        "example": command.example or "",
                    }
                )
        return commands

    async def commands(self, request: Request):
        if not self._commands or len(list(self._commands.keys())) == 1:
            self._commands = await self.dump_commandsXD()
        return json(self._commands)

    async def send_update(self, data: GithubPushEvent):
        channel = self.bot.get_channel(CONFIG["updates_channel_id"])
        if not channel:
            raise TypeError("THE UPDATES CHANNEL ID IS INVALID NIGNOG")
        try:
            _ = await channel.send(embed=data.to_embed)
        except Exception:
            _ = None
            pass
        #self.bot.dispatch("github_commit", data)
        return _

    async def github(self, request: Request):
        import orjson

        data = request.json
        data = GithubPushEvent(**data)
        ensure_future(self.send_update(data))
        self.bot.dispatch("github_commit", data)
        return json({"status": "Success"}, status=200)

    async def statistics_(self, request: Request):
        if not self.statistics:
            self.statistics = {
                "guilds": len(self.bot.guilds),
                "users": sum(self.bot.get_all_members()),
            }
        return json(self.statistics)

    async def avatar(self, request: Request):
        byte = await self.bot.user.avatar.read()
        return raw(byte, status=200, content_type="image/png")

    async def shards(self, request: Request):
        data = {}
        for sh in self.bot.shards:
            shard = self.bot.get_shard(sh)
            if shard.is_ws_ratelimited():
                status = "Partial Outage"
            else:
                status = "Operational"
            data[str(shard.id)] = {}
            members = [
                len(guild.members)
                for guild in self.bot.guilds
                if guild.shard_id == shard.id
            ]
            shard_guilds = [
                int(g.id) for g in self.bot.guilds if g.shard_id == shard.id
            ]
            data[str(shard.id)]["shard_id"] = shard.id
            data[str(shard.id)]["shard_name"] = f"Shard {shard.id}"
            data[str(shard.id)]["status"] = status
            data[str(shard.id)]["guilds"] = len(shard_guilds)
            data[str(shard.id)]["users"] = sum(members)
            data[str(shard.id)]["latency"] = round(shard.latency * 1000)
            data[str(shard.id)]["pinged"] = int(datetime.datetime.now().timestamp())
            data[str(shard.id)]["uptime"] = int(self.bot.startup_time.timestamp())
            data[str(shard.id)]["guild_ids"] = shard_guilds
        return json(data)

    async def status(self, request: Request):
        data = []
        if isinstance(self.bot, AutoShardedBot):
            for shard_id, shard in self.bot.shards.items():
                guilds = [g for g in self.bot.guilds if g.shard_id == shard_id]
                users = sum([len(g.members) for g in guilds])
                data.append(
                    {
                        "guilds": str(len(guilds)),
                        "id": str(shard_id),
                        "ping": f"{round(shard.latency * 1000)}ms",
                        "uptime": str(self.bot.startup_time.timestamp()),
                        "users": str(users),
                    }
                )
        else:
            data.append(
                {
                    "guilds": str(len(self.bot.guilds)),
                    "id": "-1",
                    "ping": f"{round(self.bot.latency * 1000)}ms",
                    "uptime": str(self.bot.startup_time.timestamp()),
                    "users": str(sum(self.bot.get_all_members())),
                }
            )
        return json(data)

    async def message_logs(self, request: Request, identifier: str):
        date_format = "%Y-%m-%d %H:%M:%S %Z%z"
        if not (
            entry := await self.bot.db.fetchrow(
                """SELECT guild_id, channel_id, created_at, expires_at, messages FROM message_logs WHERE id = $1""",
                identifier,
            )
        ):
            return json({"message": "Log entry not found"}, status=404)
        else:
            if entry.expires_at:
                expiration = entry.expires_at.strftime(date_format)
            else:
                expiration = None
            messages = jsonn.loads(entry.messages)
            data = {
                "guild_id": entry.guild_id,
                "channel_id": entry.channel_id,
                "created_at": entry.created_at.strftime(date_format),
                "expires_at": expiration,
                "messages": messages,
            }
            return json(data, status=200)

    async def asset(self, request: Request, path: str):
        if not (entry := self.assets.get(path.split(".")[0])):
            return json({"message": "File not found"}, status=404)
        image_data, content_type = entry
        return raw(image_data, status=200, content_type=content_type)

    async def add_asset(self, b64_string: str, **kwargs):
        content_type, base64_str = (
            b64_string.split(",")[0].split(":")[1].split(";")[0],
            b64_string.split(",")[1],
        )
        image_data = b64decode(base64_str)
        name = kwargs.pop("name", tuuid())
        await self.bot.redis.set(name, orjson.dumps([image_data, content_type]), ex=500)
        return f"https://api.{self.domain}/asset/{name}"

    async def cog_load(self):
        self.redump_loop.start()
        self.bot.loop.create_task(self.run())

    async def cog_unload(self):
        self.redump_loop.stop()
        self.bot.loop.create_task(self.server.close())


async def setup(bot: Client):
    await bot.add_cog(WebServer(bot))
