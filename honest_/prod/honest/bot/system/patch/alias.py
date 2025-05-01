from typing import List, Optional, Union

from discord import Message
from discord.ext.commands import Command, Group
from discord.ext.commands.converter import Converter
from discord.ext.commands.errors import CommandError
from discord.ext.commands.view import StringView
from fast_string_match import closest_match

from ..classes.converters.custom import CommandConverter
from .context import Context


class CommandAlias(object):
    def __init__(self, command: Union[Command, Group, str], alias: str):
        self.command = command
        self.alias = alias

    def get_extra_args_from_alias(self, message: Message, prefix: str) -> str:
        """When an alias is executed by a user in chat this function tries to get
        any extra arguments passed in with the call. Whitespace will be trimmed
        from both ends.

        :param message:
        :param prefix:
        :param alias:
        :return:

        """
        known_content_length = len(prefix) + len(self.command)
        extra = message.content[known_content_length:]
        view = StringView(extra)
        view.skip_ws()
        extra = []
        while not view.eof:
            prev = view.index
            word = view.get_quoted_word()
            if len(word) < view.index - prev:
                word = "".join((view.buffer[prev], word, view.buffer[view.index - 1]))
            extra.append(word)
            view.skip_ws()
        return extra


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


class AliasConverter(Converter):
    async def convert(self, ctx: Context, argument: str) -> Optional[CommandAlias]:
        if not hasattr(ctx.bot, "command_list"):
            await fill_commands(ctx)
        if "," not in argument:
            raise CommandError("please include a `,` between the command and alias")
        else:
            command, a = argument.split(",")
            command = command.rstrip().lstrip().lower()
            a = a.rstrip().lstrip().lower()
            if a in ctx.bot.command_list:
                raise CommandError(
                    f"You cannot alias **{command}** as **{a}** as its already a command"
                )
            else:
                c = await CommandConverter().convert(ctx, command)
                cmd = CommandAlias(command=c, alias=a)
                return cmd


async def handle_aliases(
    ctx: Context, aliases: List[CommandAlias], exception: Exception
):
    from loguru import logger

    for a in aliases:
        msg = ctx.message.content.lower()
        msg = msg.replace(ctx.prefix, "")
        if a.alias.lower() in msg.split(" "):
            message = ctx.message
            if isinstance(a.command, str):
                b = a.command
            else:
                b = a.command.qualified_name
            message.content = message.content.lower().replace(
                a.alias.lower(), b.lower()
            )
            ctx = await ctx.bot.get_context(message, cached=False)
            ctx.aliased = True
            logger.info(f"{ctx.message.content}")
            c = await ctx.bot.invoke(ctx)  # noqa: F841
            if ctx.valid:
                return True

    raise exception

    # raise exception
