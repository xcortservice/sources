from data.config import CONFIG
from typing import Any, Coroutine, Dict, List, Optional, Union
from discord.ext.commands import Context as DefaultContext
from discord.ext.commands import (Command, CommandError, Group, UserInputError)
class Context(DefaultContext):
    async def send_help(self, option: Optional[Union[Command, Group]] = None):
        try:
            from .help import Help

            if option is None:
                if command := self.command:
                    if command.name != "help":
                        option = command
            h = Help()
            h.context = self
            if not option:
                return await h.send_bot_help(None)
            elif isinstance(option, Group):
                option = (
                    self.bot.get_command(option) if isinstance(option, str) else option
                )
                return await h.send_group_help(option)
            else:
                option = (
                    self.bot.get_command(option) if isinstance(option, str) else option
                )
                return await h.send_command_help(option)
        except Exception as exception:
            return await self.bot.errors.handle_exceptions(self, exception)