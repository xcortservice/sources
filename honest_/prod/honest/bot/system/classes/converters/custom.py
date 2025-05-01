import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import discord
import humanfriendly
from aiohttp import ClientResponse
from aiohttp import ClientSession as Session
from discord import Client
from discord.ext.commands import CommandError, Converter, Group
from discord.ext.commands import GuildConverter as GuildConv
from fast_string_match import closest_match
from system.patch.context import Context

from ..embed import Script


class EmbedConverter(Converter):
    async def convert(self, ctx: Context, argument: str):
        c = argument
        c = c.replace("{level}", "")
        try:
            s = Script(c, ctx.author, channel=ctx.channel)
            await s.compile()
        except Exception as e:
            raise e
        return argument


class Boolean(Converter):
    async def convert(self, ctx: Context, argument: str):
        true = ["enable", "on", "yes", "t", "e", "y", "true"]
        false = ["disable", "off", "no", "f", "d", "n", "false"]
        if argument.lower() in true:
            return True
        elif argument.lower() in false:
            return False
        else:
            raise CommandError(f"{argument[:20]} is not a valid setting")


GLOBAL_COMMANDS = {}


def find_command(bot, query):
    query = query.lower()
    if len(GLOBAL_COMMANDS) == 4000:
        _commands = [c for c in bot.walk_commands()]
        commands = {}
        # commands = [c for c in _commands if c.qualified_name.startswith(query) or query in c.qualified_name]
        for command in _commands:
            if isinstance(command, Group):
                aliases = command.aliases
                for cmd in command.walk_commands():
                    for a in aliases:
                        commands[
                            f"{cmd.qualified_name.replace(f'{command.qualified_name}', f'{a}')}"
                        ] = cmd
                    commands[cmd.qualified_name] = cmd
                commands[command.qualified_name] = command
            else:
                commands[command.qualified_name] = command
                for alias in command.aliases:
                    commands[alias] = command
        GLOBAL_COMMANDS.update(commands)
    if not bot.command_dict:
        bot.get_command_dict()
    if query in bot.command_dict:
        return bot.get_command(query)
    if MATCH := closest_match(query, bot.command_dict):
        return bot.get_command(MATCH)
    else:
        return None


class CommandConverter(Converter):
    async def convert(self, ctx: Context, argument: str):
        argument = argument.replace("_", " ").lower()
        if not (command := find_command(ctx.bot, argument)):
            raise CommandError(f"Could not find a command named `{argument[:25]}`")
        return command


class AntiNukeAction(Converter):
    async def convert(self, ctx: Context, argument: str):
        _action_ = argument.lower().lstrip().rstrip()
        if _action_ in ("strip", "stripstaff"):
            return "stripstaff"
        elif _action_ == "ban":
            return "ban"
        elif _action_ == "kick":
            return "kick"
        else:
            raise CommandError(
                "the only valid actions are `ban`, `kick`, and `stripstaff`"
            )


async def get_int(argument: str):
    t = ""
    for s in argument:
        try:
            d = int(s)
            t += f"{d}"
        except Exception:
            pass
    return t


class Timeframe(Converter):
    async def convert(self, ctx: Context, argument: str):
        try:
            converted = humanfriendly.parse_timespan(argument)
        except Exception:
            converted = humanfriendly.parse_timespan(
                f"{await get_int(argument)} minutes"
            )
        if converted >= 40320:
            raise CommandError("discord's API is limited to `28 days` for timeouts")
        return converted


def validate_discord_guild_id(guild_id: str) -> bool:
    # Check if the guild_id consists only of digits and is 17 to 19 digits long
    return bool(re.fullmatch(r"^\d{17,19}$", guild_id))


async def get_a_response(response: ClientResponse):
    try:
        return await response.json()
    except Exception:

        pass
    try:
        return await response.text()
    except Exception:
        pass
    return await response.read()


async def get_response(response: ClientResponse):
    if response.content_type == "text/plain":
        return await response.text()
    elif response.content_type.startswith(("image/", "video/", "audio/")):
        return await response.read()
    elif response.content_type == "text/html":
        return await response.text()
    elif response.content_type in (
        "application/json",
        "application/octet-stream",
        "text/javascript",
    ):
        try:
            data: Dict = await response.json(content_type=None)
        except Exception:
            return response
    else:
        return None


def convert_str(s: str) -> Optional[int]:
    try:
        integer = int(s)
        if validate_discord_guild_id(s):
            return integer
        else:
            return None
    except Exception:
        return None


async def fetch_guild(guild_id: int) -> Tuple[int, Any]:
    async with Session() as session:
        async with session.get(
            f"https://discord.com/api/v10/guilds/{guild_id}",
            headers={"Authentication": f"Bot {os.environ['TOKEN']}"},
        ) as response:
            data = await get_response(response)
            status = int(response.status)
    return status, data


def get_valid_ints(message: Union[discord.Message, str]) -> list:
    content = message if isinstance(message, str) else message.content
    try:
        try:
            if " " not in content:
                g = int(content)
                if check := validate_discord_guild_id(content):
                    return [g]
        except Exception:
            pass
    except Exception:
        pass
    return [
        convert_str(d)
        for d in (part for part in content.split() for part in part.split())
        if convert_str(d) is not None
    ]


async def fetch_invite(bot: Client, invite: Union[discord.Invite, str]) -> int:
    if isinstance(invite, str):
        invite = await bot.fetch_invite(invite)
        guild = invite.guild
        if isinstance(guild, discord.Guild):
            return guild.id
        elif isinstance(guild, discord.Object):
            return guild.id
        else:
            try:
                return invite.guild.id
            except Exception:
                return invite.id
    if isinstance(invite, discord.Invite):
        guild = invite.guild
        if isinstance(guild, discord.Guild):
            return guild.id
        elif isinstance(guild, discord.Object):
            return guild.id
        else:
            try:
                return invite.guild.id
            except Exception:
                return invite.id
    return None


class GConverter(Converter):
    async def convert(self, ctx: Context, argument: str) -> Optional[int]:
        if "https://" in argument:
            invite = await ctx.bot.fetch_invite(argument)
            guild = invite.guild
            if isinstance(guild, discord.Guild):
                return guild.id
            elif isinstance(guild, discord.Object):
                return guild.id
            else:
                try:
                    return invite.guild.id
                except Exception:
                    return invite.id
        else:
            try:
                return int(argument)
            except Exception:
                return None


class GuildConverter(Converter):
    async def convert(self, ctx: Context, argument: str) -> Optional[int]:
        try:
            invites = ctx.message.invites
            if invites:
                invite = await ctx.bot.fetch_invite(invites[0])
                guild = invite.guild
                if isinstance(guild, discord.Guild):
                    return guild.id
                elif isinstance(guild, discord.Object):
                    return guild.id
                else:
                    try:
                        return invite.guild.id
                    except Exception:
                        return invite.id
            else:
                try:
                    guild = await GuildConv().convert(ctx, argument)
                    if guild:
                        return guild.id
                except Exception:
                    pass
                ints = get_valid_ints(argument)
                if len(ints) == 0:
                    raise CommandError("No Guild IDS were Found")
                return ints[0]
        except Exception:
            return None


class Expiration(Converter):
    async def convert(self, ctx: Context, argument: str):
        try:
            converted = humanfriendly.parse_timespan(argument)
        except Exception:
            converted = humanfriendly.parse_timespan(
                f"{await get_int(argument)} minutes"
            )
        if ctx.command:
            if ctx.command.qualified_name == "timeout":
                if converted >= 40320:
                    raise CommandError(
                        "discord's API is limited to `28 days` for timeouts"
                    )
        return converted
