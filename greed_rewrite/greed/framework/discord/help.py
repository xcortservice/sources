from typing import TYPE_CHECKING, Any, List, Mapping, cast

from discord.ext.commands import MinimalHelpCommand, Cog, Command, Group

if TYPE_CHECKING:
    from greed.framework import Context, Greed


class Helper:
    ctx: "Context"
    bot: "Greed"

    async def send_bot_help(self, mapping: Mapping[Cog | None, List[Command]]) -> None:
        raise NotImplementedError()

    async def send_command_help(self, command: Command) -> None:
        raise NotImplementedError()

    async def send_error_message(self, error: str) -> None:
        raise NotImplementedError()

    async def send_cog_help(self, cog: Cog) -> None:
        raise NotImplementedError()

    async def send_group_help(self, group: Group) -> None:
        raise NotImplementedError()


class Help(MinimalHelpCommand):
    extensions: List[Helper] = []

    def __init__(self, **options: Any) -> None:
        self.bot: "Greed" = cast("Greed", self.context.bot)
        self.ctx: "Context" = cast("Context", self.context)
        self._load_extensions()
        super().__init__(**options)

    def _load_extensions(self) -> None: ...

    async def send_bot_help(self, mapping: Mapping[Cog | None, List[Command]]) -> None:
        return await super().send_bot_help(mapping)

    async def send_command_help(self, command: Command) -> None:
        return await super().send_command_help(command)

    async def send_error_message(self, error: str) -> None:
        return await super().send_error_message(error)

    async def send_cog_help(self, cog: Cog) -> None:
        return await super().send_cog_help(cog)

    async def send_group_help(self, group: Group) -> None:
        return await super().send_group_help(group)
