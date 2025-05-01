from typing import Dict, List, Union

from data.variables import DISCORD_ID, DISCORD_ROLE_MENTION, PERMISSION_LIST
from discord import Role as DiscordRole
from discord import utils
from discord.ext import commands
from fast_string_match import closest_match
from system.patch.context import Context


def find_role(ctx: Context, argument: str) -> DiscordRole:
    role = (
        utils.find(lambda r: r.name.lower() == argument.lower(), ctx.guild.roles)
        or utils.find(lambda r: argument.lower() in r.name.lower(), ctx.guild.roles)
        or utils.find(
            lambda r: r.name.lower().startswith(argument.lower()),
            ctx.guild.roles,
        )
    )
    return role


class AssignedRole(commands.RoleConverter):
    async def convert(self, ctx: Context, arg: str):
        self.assign = True
        role = None
        arguments = [arg]
        roles = []
        for argument in arguments:
            role = None
            argument = argument.lstrip().rstrip()
            try:
                role = await super().convert_(ctx, argument)
            except Exception:
                pass
            _roles = {r.name: r for r in ctx.guild.roles if r.is_assignable()}
            if role is None:
                if match := DISCORD_ID.match(argument):
                    role = ctx.guild.get_role(int(match.group(1)))
                elif match := DISCORD_ROLE_MENTION.match(argument):
                    role = ctx.guild.get_role(int(match.group(1)))
                else:
                    if not (role := find_role(ctx, argument)):
                        if match := closest_match(
                            argument.lower(), list(_roles.keys())
                        ):
                            try:
                                role = _roles[match]
                            except Exception:
                                role = None
                        else:
                            role = None
                if not role or role.is_default():
                    for role in ctx.guild.roles:
                        if (
                            argument.lower() in role.name.lower()
                            or role.name.lower() == argument.lower()
                            or role.name.lower().startswith(argument.lower())
                        ):
                            if role.is_assignable():
                                role = role
                    if not role:
                        raise commands.RoleNotFound(argument)
            if self.assign is True:
                if role < ctx.author.top_role or ctx.author.id == ctx.guild.owner_id:
                    if (
                        role <= ctx.guild.me.top_role
                        or ctx.author.id in ctx.bot.owner_ids
                        or ctx.author.id == ctx.guild.owner_id
                    ):
                        roles.append(role)
                    else:
                        raise commands.CommandError(
                            f"{role.mention} is **above my role**"
                        )
                else:
                    if role == ctx.author.top_role and ctx.author != ctx.guild.owner:
                        m = "the same as your top role"
                    else:
                        m = "above your top role"
                    raise commands.CommandError(f"{role.mention} is **{m}**")
            else:
                roles.append(role)
        return roles[0]


class Role(commands.RoleConverter):
    async def convert(self, ctx: Context, arg: str):
        self.assign = False
        role = None
        roles = []
        arguments = [arg]
        for argument in arguments:
            role = None
            argument = argument.lstrip().rstrip()
            try:
                role = await super().convert_(ctx, argument)
            except Exception:
                pass
            _roles = {r.name: r for r in ctx.guild.roles if r.is_assignable()}
            if role is None:
                if match := DISCORD_ID.match(argument):
                    role = ctx.guild.get_role(int(match.group(1)))
                elif match := DISCORD_ROLE_MENTION.match(argument):
                    role = ctx.guild.get_role(int(match.group(1)))
                else:
                    if not (role := find_role(ctx, argument)):
                        if match := closest_match(
                            argument.lower(), list(_roles.keys())
                        ):
                            try:
                                role = _roles[match]
                            except Exception:
                                role = None
                        else:
                            role = None
                if not role or role.is_default():
                    for role in ctx.guild.roles:
                        if (
                            argument.lower() in role.name.lower()
                            or role.name.lower() == argument.lower()
                            or role.name.lower().startswith(argument.lower())
                        ):
                            if role.is_assignable():
                                role = role
                    if not role:
                        raise commands.RoleNotFound(argument)
            roles.append(role)
        return roles[0]


class MultipleRoles(commands.RoleConverter):
    async def convert(self, ctx: Context, arg: str):
        self.assign = True
        role = None
        if " , " in arg:
            arguments = arg.split(" , ")
        elif "," in arg:
            arguments = arg.split(",")
        else:
            arguments = [arg]
        roles = []
        for argument in arguments:
            role = None
            argument = argument.lstrip().rstrip()
            try:
                role = await super().convert_(ctx, argument)
            except Exception:
                pass
            _roles = {r.name: r for r in ctx.guild.roles if r.is_assignable()}
            if role is None:
                if match := DISCORD_ID.match(argument):
                    role = ctx.guild.get_role(int(match.group(1)))
                elif match := DISCORD_ROLE_MENTION.match(argument):
                    role = ctx.guild.get_role(int(match.group(1)))
                else:
                    if not (role := find_role(ctx, argument)):
                        if match := closest_match(
                            argument.lower(), list(_roles.keys())
                        ):
                            try:
                                role = _roles[match]
                            except Exception:
                                role = None
                        else:
                            role = None
                if not role or role.is_default():
                    for role in ctx.guild.roles:
                        if (
                            argument.lower() in role.name.lower()
                            or role.name.lower() == argument.lower()
                            or role.name.lower().startswith(argument.lower())
                        ):
                            if role.is_assignable():
                                role = role
                    if not role:
                        raise commands.RoleNotFound(argument)
            roles.append(role)
        return roles


class FakePermission(commands.Converter):
    async def convert(self, ctx: Context, argument: str):
        if "," in argument:
            permissions = [
                l.rstrip().lstrip().replace(" ", "_").lower()
                for l in argument.split(",")
            ]
        else:
            permissions = [argument.strip().rstrip().replace(" ", "_").lower()]
        for permission in permissions:
            if permission not in PERMISSION_LIST:
                raise commands.BadArgument(f"Invalid permission: {permission}")
        return permissions
