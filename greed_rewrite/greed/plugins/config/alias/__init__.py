from __future__ import annotations

import typing
from typing import Optional, Union, TYPE_CHECKING
import discord
from discord.ext import commands
from discord.ext.commands import Context, Command, Group, Converter
from discord.ext.commands.errors import CommandError
from fast_string_match import closest_match
from greed.shared.config import Colors
from greed.framework.pagination import Paginator

if TYPE_CHECKING:
    from greed.framework import Greed


class CommandAlias:
    def __init__(self, command: Union[Command, Group, str], alias: str):
        self.command = command
        self.alias = alias


async def fill_commands(ctx: Context):
    if not hasattr(ctx.bot, "command_list"):
        commands = {}
        for command in ctx.bot.walk_commands():
            commands[command.qualified_name.lower()] = command
            for alias in command.aliases:
                if command.parent is not None:
                    c = f"{command.parent.qualified_name.lower()} "
                else:
                    c = ""
                commands[f"{c}{alias.lower()}"] = command
        ctx.bot.command_list = commands
        del commands
    return ctx.bot.command_list


class CommandConverter(Converter):
    async def convert(
        self, ctx: Context, argument: str
    ) -> Optional[Union[Command, Group]]:
        if not hasattr(ctx.bot, "command_list"):
            await fill_commands(ctx)
        if command := ctx.bot.get_command(argument):
            return command
        else:
            if match := closest_match(
                argument, [c.qualified_name for c in ctx.bot.walk_commands()]
            ):
                return ctx.bot.get_command(match)
            else:
                raise CommandError(f"Cannot find a command named **{argument}**")


class AliasConverter(Converter):
    async def convert(self, ctx: Context, argument: str) -> Optional[CommandAlias]:
        if not hasattr(ctx.bot, "command_list"):
            await fill_commands(ctx)
        if "," not in argument:
            raise CommandError("please include a `,` between the command and alias")
        else:
            command, a = argument.split(",")
            command = command.strip().lower()
            a = a.strip().lower()
            if a in ctx.bot.command_list:
                raise CommandError(
                    f"You cannot alias **{command}** as **{a}** as its already a command"
                )
            else:
                c = await CommandConverter().convert(ctx, command)
                cmd = CommandAlias(command=c, alias=a)
                return cmd


class alias(commands.Cog, name="Alias"):
    def __init__(self, bot: "Greed"):
        self.bot = bot
        self._aliases: dict[int, list[CommandAlias]] = {}

    async def cog_load(self) -> None:
        await self.load_aliases()

    async def load_aliases(self) -> None:
        data = await self.bot.db.fetch(
            "SELECT guild_id, command_name, alias FROM aliases"
        )
        for row in data:
            if row.guild_id not in self._aliases:
                self._aliases[row.guild_id] = []
            command = self.bot.get_command(row.command_name)
            if command:
                self._aliases[row.guild_id].append(CommandAlias(command, row.alias))

    async def process_aliases(self, ctx: Context) -> bool:
        if not ctx.guild or ctx.guild.id not in self._aliases:
            return False

        msg = ctx.message.content.lower()
        msg = msg.replace(ctx.prefix, "")

        for alias_data in self._aliases[ctx.guild.id]:
            if alias_data.alias.lower() in msg.split(" "):
                message = ctx.message
                if isinstance(alias_data.command, str):
                    b = alias_data.command
                else:
                    b = alias_data.command.qualified_name
                message.content = message.content.replace(alias_data.alias, b)
                await self.bot.process_commands(message)
                return True
        return False

    @commands.group(
        name="alias",
        invoke_without_command=True,
        brief="view alias sub commands",
        example=",alias",
    )
    async def alias(self, ctx: Context):
        if ctx.subcommand_passed is not None:
            return
        return await ctx.send_help(ctx.command.qualified_name)

    @alias.command(
        name="add",
        aliases=["create", "a", "c"],
        brief="add an alias for a command",
        example=",alias add ban, byebye",
    )
    @commands.has_permissions(manage_guild=True)
    async def alias_add(self, ctx: Context, *, data: AliasConverter):
        self.bot.alias_kwargs = ctx.kwargs
        await self.bot.db.execute(
            "INSERT INTO aliases (guild_id, command_name, alias) VALUES ($1,$2,$3) ON CONFLICT(guild_id, alias) DO NOTHING",
            ctx.guild.id,
            data.command.qualified_name,
            data.alias,
        )
        if ctx.guild.id not in self._aliases:
            self._aliases[ctx.guild.id] = []
        self._aliases[ctx.guild.id].append(CommandAlias(data.command, data.alias))
        return await ctx.embed(
            f"**Added** `{data.alias}` as an **alias** for `{data.command.qualified_name}`", "approved"
        )

    @alias.command(
        name="remove",
        aliases=["delete", "r", "rem", "del", "d"],
        brief="remove an alias from a command",
        example=",alias remove ban",
    )
    @commands.has_permissions(manage_guild=True)
    async def alias_remove(self, ctx: Context, *, alias: str):
        await self.bot.db.execute(
            "DELETE FROM aliases WHERE guild_id = $1 AND alias = $2",
            ctx.guild.id,
            alias,
        )
        if ctx.guild.id in self._aliases:
            self._aliases[ctx.guild.id] = [
                a for a in self._aliases[ctx.guild.id] if a.alias != alias
            ]
        return await ctx.embed(f"**Removed** `{alias}` custom alias", "approved")

    @alias.command(
        name="list", brief="show all your current command aliases", example="alias list"
    )
    @commands.has_permissions(manage_guild=True)
    async def alias_list(self, ctx: Context):
        data = await self.bot.db.fetch(
            """SELECT command_name, alias FROM aliases WHERE guild_id = $1""",
            ctx.guild.id,
        )
        rows = []
        for i, row in enumerate(data, start=1):
            rows.append(f"`{i}` **{row['command_name']}** - {row['alias']}")
        if len(rows) == 0:
            return await ctx.embed("No **aliases** found", "warned")
        else:
            embed = discord.Embed(title="Aliases", color=Colors().information)
            return await Paginator(ctx, rows, embed=embed).start()


async def setup(bot):
    await bot.add_cog(alias(bot))
