from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    TypeAlias,
    Union,
    Literal,
    TYPE_CHECKING,
    Callable,
    Mapping,
)

from cashews import cache
from discord import (
    Embed,
    Interaction,
    SelectOption,
)

from discord.ext.commands import (
    Cog,
    Command,
    Group,
    MinimalHelpCommand,
)
from discord.ext.commands.flags import MISSING
from discord.ui import Select, View
from pydantic import BaseModel, ConfigDict

from greed.framework.pagination import Paginator

if TYPE_CHECKING:
    from greed.framework import Context
    from greed.framework.pagination import Paginator
    from greed.framework import FlagConverter, short_timespan

StringDict: TypeAlias = Dict[str, str]

RESTRICTED_CATEGORIES = [
    "owner",
    "jishaku",
    "errors",
    "developer",
]


@dataclass
class FlagData:
    name: str
    description: str
    default: Any = None
    is_required: bool = False
    annotation: Any = None

    def format(self) -> str:
        if not self.is_required:
            argument = ""
            if isinstance(self.default, timedelta):
                argument = f"={short_timespan(self.default)}"
            elif not isinstance(self.default, bool):
                if (
                    hasattr(self.annotation, "__origin__")
                    and self.annotation.__origin__ is Literal
                ):
                    options = "|".join(str(arg) for arg in self.annotation.__args__)
                    argument = f"={options}"
                else:
                    argument = f"={self.default}"
            return f"`--{self.name}{argument}`"
        return f"`--{self.name}`"


class CommandExample(BaseModel):
    command_name: str
    example_text: str

    def __str__(self) -> str:
        text = self.example_text
        if "@user" in text:
            try:
                bot = self.context.bot
                author_name = (
                    next(
                        (user.name for user in bot.users if user.id in bot.owner_ids),
                        "user",
                    )
                    if bot and bot.users
                    else "user"
                )
                text = text.replace("@user", f"@{author_name}")
            except:
                pass
        return f"{self.command_name} {text}"


class ParamExample(BaseModel):
    model_config = ConfigDict(extra="allow")

    user: str = "@user"
    member: str = "@user"
    target: str = "@user"
    author: str = "@user"
    users: str = "@user1 @user2"
    members: str = "@member1 @member2"
    mentions: str = "@user1 @user2"
    role: str = "@role"
    roles: str = "@role1 @role2"
    role_name: str = "Moderator"
    channel: str = "#channel"
    channels: str = "#channel1 #channel2"
    category: str = "General"
    thread: str = "#thread"
    reason: str = "broke rules"
    content: str = "your message here"
    text: str = "some text"
    title: str = "my title"
    description: str = "cool server"
    name: str = "boosters"
    new_name: str = "admins"
    message: str = "hello world"
    query: str = "search term"
    duration: str = "7d"
    time: str = "24h"
    interval: str = "30m"
    delay: str = "10s"
    history: str = "1d"
    timeout: str = "1h"
    date: str = "2023-04-15"
    amount: str = "5"
    count: str = "10"
    limit: str = "25"
    number: str = "3"
    pages: str = "2"
    max: str = "100"
    min: str = "1"
    quantity: str = "7"
    image: str = "image.png"
    attachment: str = "file.png"
    file: str = "document.pdf"
    avatar: str = "profile.jpg"
    banner: str = "banner.png"
    command: str = "help"
    cmd: str = "ban"
    color: str = "#ff0000"
    emoji: str = "😄"
    url: str = "https://example.com"
    event: str = "message"
    event_names: str = "join leave"
    assign_role: str = "@member_role"
    prefix: str = "!"
    mode: str = "strict"
    filter: str = "nsfw"
    position: str = "2"
    action: str = "kick"
    level: str = "3"
    settings: str = "notifications"
    permission: str = "manage_messages"
    id: str = "123456789..."
    language: str = "english"
    timezone: str = "UTC"


class CommandFormatter:
    PARAM_TYPE_EXAMPLES: ClassVar[Dict[str, str]] = {
        "user": "@user",
        "member": "@user",
        "role": "@homies",
        "channel": "#general",
        "textchannel": "#general",
        "guild": "stmpsupport",
        "server": "stmpsupport",
        "bool": "yes",
        "int": "5",
        "float": "5",
        "number": "5",
        "str": "{name}",
        "string": "{name}",
    }

    @staticmethod
    def add_flag_formatting(annotation: Type[FlagConverter], embed: Embed) -> None:
        flags = annotation.get_flags()
        required_flags = []
        optional_flags = []

        for name, flag in flags.items():
            flag_data = FlagData(
                name=name,
                description=flag.description,
                default=flag.default,
                is_required=flag.default is MISSING,
                annotation=flag.annotation,
            )

            if flag_data.is_required:
                required_flags.append(flag_data.format())
            else:
                optional_flags.append(flag_data.format())

        if required_flags:
            embed.add_field(
                name="Required Flags",
                value="\n".join(required_flags),
                inline=True,
            )
        if optional_flags:
            embed.add_field(
                name="Optional Flags",
                value="\n".join(optional_flags),
                inline=True,
            )

    @staticmethod
    def get_syntax(command: Command) -> str:
        if command.usage:
            return f"{command.qualified_name} {command.usage}".strip()

        if isinstance(command, Group):
            return f"{command.qualified_name} (subcommand) (args)"

        #    if isinstance(command, Group):
        #        if not command.commands and command.help:
        #            return f"{command.qualified_name} (subcommand) (args)"
        #        return f"{command.qualified_name}"
        #

        params = [
            f"<{name}>" if param.default == param.empty else f"[{name}]"
            for name, param in command.clean_params.items()
        ]
        return f"{command.qualified_name} {' '.join(params)}".strip()

    @staticmethod
    @cache(ttl="1h")
    async def get_param_examples() -> Dict[str, str]:
        return ParamExample().model_dump()

    @classmethod
    async def generate_examples(cls, command: Command) -> List[str]:
        if not hasattr(command, "clean_params") or not command.clean_params:
            return []

        ex = f"{command.qualified_name} "
        param_examples = await cls.get_param_examples()
        author_name = cls._get_author_name(command)

        for name, param in command.clean_params.items():
            name_lower = name.lower() if name else ""
            param_annotation = getattr(param, "annotation", None)
            param_empty = getattr(param, "empty", None)
            param_type = (
                str(param_annotation).lower()
                if param_annotation is not None and param_annotation != param_empty
                else ""
            )
            example_value = None

            if name_lower in param_examples:
                example_value = param_examples[name_lower]
            elif not example_value:
                for key, value in param_examples.items():
                    if key in name_lower:
                        example_value = value
                        break
            elif not example_value:
                for (
                    type_str,
                    example,
                ) in cls.PARAM_TYPE_EXAMPLES.items():
                    if type_str in param_type:
                        example_value = example
                        break
            elif not example_value:
                example_value = name

            if example_value and "@user" in str(example_value):
                example_value = example_value.replace("@user", f"@{author_name}")
            if example_value and "{name}" in str(example_value):
                example_value = example_value.format(name=name)

            ex += f"{example_value} " if example_value else ""

        return [ex.strip()]

    @staticmethod
    def _get_author_name(command: Command) -> str:
        author_name = "user"
        if hasattr(command, "context"):
            ctx = getattr(command, "context")
            if hasattr(ctx, "author") and hasattr(ctx.author, "name"):
                author_name = ctx.author.name
        return author_name

    @classmethod
    async def get_example(cls, command: Command) -> Optional[str]:
        author_name = cls._get_author_name(command)

        if hasattr(command, "example") and command.example:
            example_text = command.example
            if "@user" in example_text:
                example_text = example_text.replace("@user", f"@{author_name}")
            return str(
                CommandExample(
                    command_name=command.qualified_name,
                    example_text=example_text,
                )
            )

        for source_attr in ("usage", "help"):
            source = getattr(command, source_attr, None)
            if source and "example:" in source.lower():
                if example_match := re.search(
                    r"example:?\s*(.*?)(?:\n|$)",
                    source,
                    re.IGNORECASE,
                ):
                    example_text = example_match.group(1).strip()
                    if "@user" in example_text:
                        example_text = example_text.replace("@user", f"@{author_name}")
                    return str(
                        CommandExample(
                            command_name=command.qualified_name,
                            example_text=example_text,
                        )
                    )

        if isinstance(command, Group):
            if hasattr(command, "commands") and command.commands:
                try:
                    subcommand = next(iter(command.commands), None)
                    if subcommand:
                        return f"{command.qualified_name} {subcommand.name}"
                except (StopIteration, TypeError):
                    pass
            return f"{command.qualified_name} (subcommand)"

        if hasattr(command, "clean_params") and command.clean_params:
            if generated := await cls.generate_examples(command):
                result = generated[0]

                if hasattr(command, "clean_params"):
                    for (
                        name,
                        param,
                    ) in command.clean_params.items():
                        name_lower = name.lower()
                        param_type = (
                            str(param.annotation).lower()
                            if hasattr(param, "annotation")
                            and param.annotation != getattr(param, "empty", None)
                            else ""
                        )

                        if any(
                            user_term in name_lower or user_term in param_type
                            for user_term in [
                                "user",
                                "member",
                                "target",
                                "author",
                            ]
                        ):
                            result = result.replace("@user", f"@{author_name}")
                            break

                return result

        return None


class CategorySelect(Select):
    def __init__(self, categories: Dict[str, Cog]) -> None:
        self.categories = categories
        self.embed = None
        options = [SelectOption(label=key, value=key) for key in categories]
        super().__init__(placeholder="Select a Category", options=options)

    async def callback(self, interaction: Interaction) -> None:
        if not self.embed:
            if interaction.message and interaction.message.embeds:
                self.embed = interaction.message.embeds[0].copy()
            else:
                return

        if not (category := self.categories.get(self.values[0])):
            return

        embed = copy.deepcopy(self.embed)
        embed.clear_fields()
        embed.title = f"`Category: ` {category.__cog_name__}"

        groups = set()
        commands = []
        total_commands = 0

        try:
            walk_commands = (
                list(category.walk_commands())
                if hasattr(category, "walk_commands")
                else []
            )

            visible_commands = [cmd for cmd in walk_commands if not cmd.hidden]
            total_commands = len(visible_commands)

            for command in visible_commands:
                if isinstance(command, Group) and command.parent is None:
                    groups.add(command.name)
                    commands.append(command.name)
                elif not isinstance(command, Group) and command.parent is None:
                    commands.append(command.name)
        except Exception:
            commands = ["Error loading commands"]
            total_commands = 0

        description = category.__doc__ or ""
        cmds_display = (
            ", ".join(f"{name}*" if name in groups else name for name in commands)
            or "No Commands Present"
        )

        embed.description = f"{description}\n```{cmds_display}```"
        embed.set_footer(text=f"Commands: {total_commands}")

        await interaction.response.edit_message(embed=embed)


class CategorySelector(View):
    def __init__(self, ctx: Context, select: CategorySelect) -> None:
        super().__init__(timeout=300)
        self.add_item(select)
        self.ctx = ctx

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.warn("You're not the **author** of this embed!")
        return interaction.user.id == self.ctx.author.id


class GreedHelp(MinimalHelpCommand):
    context: Context

    def __init__(self, **options):
        super().__init__(
            command_attrs={
                "help": "Shows help about the bot, a command, or a category of commands.",
                "aliases": ["h"],
            },
            **options,
        )

    def create_main_help_embed(self, ctx: Context) -> Embed:
        embed = Embed(
            description="**information**\n> [ ] = optional, < > = required\n",
        )

        embed.add_field(
            name="Invite",
            value="**[invite](https://discord.com/oauth2/authorize?client_id=1203514684326805524)**  • "
            "**[support](https://discord.gg/greedbot)**  • "
            "**[view on web](https://greed.best)**",
            inline=False,
        )

        embed.set_author(
            name=f"{ctx.bot.user.name}",
            icon_url=ctx.bot.user.display_avatar.url,
        )
        embed.set_footer(text="Select a category from the dropdown menu below")

        return embed

    async def send_bot_help(
        self,
        mapping: Mapping[Union[Any, None], List[Command[Any, Callable[..., Any], Any]]],
    ) -> None:
        bot = self.context.bot
        embed = self.create_main_help_embed(self.context)
        embed.set_thumbnail(url=bot.user.display_avatar.url)

        valid_categories = []
        for cog in mapping.keys():
            if not cog or not getattr(cog, "qualified_name", None):
                continue
            if cog.qualified_name in [
                "Jishaku",
                "Network",
                "Owner",
                "Listeners",
                "Hog",
            ]:
                continue
            if not any(not cmd.hidden for cmd in mapping[cog]):
                continue

            description = None
            if cog.__doc__:
                description = cog.__doc__.strip()
            elif hasattr(cog, "description") and cog.description:
                description = cog.description

            valid_categories.append(
                (cog.qualified_name, description or "No description")
            )

        if not valid_categories:
            await self.context.reply("No commands available.")
            return

        categories = sorted(valid_categories)

        select = Select(
            placeholder="Choose a category...",
            options=[
                SelectOption(
                    label=category[0],
                    value=category[0],
                    description=category[1][:100] if category[1] else "No description",
                )
                for category in categories
            ],
        )

        async def select_callback(interaction: Interaction):
            if interaction.user.id != self.context.author.id:
                await interaction.response.send_message(
                    "You cannot interact with this menu!", ephemeral=True
                )
                return

            selected_category = interaction.data["values"][0]
            selected_cog = next(
                (
                    cog
                    for cog in mapping.keys()
                    if cog and getattr(cog, "qualified_name", None) == selected_category
                ),
                None,
            )

            if not selected_cog:
                return

            commands = mapping[selected_cog]
            visible_commands = [cmd for cmd in commands if not cmd.hidden]

            if not visible_commands:
                await interaction.response.send_message(
                    "No visible commands in this category.", ephemeral=True
                )
                return

            command_list = ", ".join(
                [
                    f"{command.name}*" if isinstance(command, Group) else command.name
                    for command in visible_commands
                ]
            )

            description = None
            if selected_cog.__doc__:
                description = selected_cog.__doc__.strip()
            elif hasattr(selected_cog, "description") and selected_cog.description:
                description = selected_cog.description

            category_embed = Embed(
                title=f"Category: {selected_category}",
                description=(
                    f"{description}\n```\n{command_list}\n```"
                    if description
                    else f"```\n{command_list}\n```"
                ),
            )
            category_embed.set_author(
                name=f"{bot.user.name}", icon_url=bot.user.display_avatar.url
            )
            category_embed.set_footer(
                text=f"{len(visible_commands)} command{'s' if len(visible_commands) != 1 else ''}"
            )

            await interaction.response.edit_message(embed=category_embed, view=view)

        select.callback = select_callback
        view = View(timeout=180)
        view.add_item(select)

        await self.context.reply(embed=embed, view=view)

    async def send_command_help(self, command: Command) -> None:
        try:
            syntax = f"{self.context.clean_prefix}{command.qualified_name} {' '.join([f'({parameter.name})' if not parameter.optional else f'[{parameter.name}]' for parameter in command.arguments])}"
        except AttributeError:
            syntax = f"{self.context.clean_prefix}{command.qualified_name}"

        try:
            permissions = ", ".join(
                [
                    permission.lower().replace("n/a", "None").replace("_", " ")
                    for permission in command.permissions
                ]
            )
        except AttributeError:
            permissions = "None"

        description = None
        if command.brief:
            description = command.brief
        elif command.__doc__:
            description = command.__doc__.strip()
        elif command.help:
            description = command.help

        embed = Embed(
            title=f"Command: {command.qualified_name} • {command.cog_name} module",
            description=f"> {description}" if description else None,
        )

        embed.set_author(
            name=f"{self.context.bot.user.name} help",
            icon_url=self.context.bot.user.avatar.url,
        )

        embed.add_field(
            name="",
            value=f"```Ruby\nSyntax: {syntax}\nExample: {self.context.clean_prefix}{command.qualified_name} {command.example.split(command.qualified_name)[-1].strip() if command.example and command.qualified_name in command.example else command.example or ''}```",
            inline=False,
        )

        embed.add_field(
            name="Permissions",
            value=permissions,
            inline=True,
        )

        embed.set_footer(
            text=f"Aliases: {', '.join(a for a in command.aliases) if len(command.aliases) > 0 else 'none'}",
            icon_url=self.context.author.avatar.url,
        )

        await self.context.reply(embed=embed)

    async def send_group_help(self, group: Group) -> None:
        embeds = []

        if group.help or group.description:
            try:
                syntax = f"{self.context.clean_prefix}{group.qualified_name} {' '.join([f'({parameter.name})' if not parameter.optional else f'[{parameter.name}]' for parameter in group.arguments])}"
            except AttributeError:
                syntax = f"{self.context.clean_prefix}{group.qualified_name}"

            try:
                permissions = ", ".join(
                    [
                        permission.lower().replace("n/a", "None").replace("_", " ")
                        for permission in group.permissions
                    ]
                )
            except AttributeError:
                permissions = "None"

            brief = group.brief or ""

            if permissions != "None" and brief:
                permissions = f"{permissions}"
            elif brief:
                permissions = brief

            embed = Embed(
                title=f"Group: {group.qualified_name} • {group.cog_name} module",
                description=f"> {group.description.capitalize() if group.description else (group.help.capitalize() if group.help else None)}",
            )

            embed.set_author(
                name=f"{self.context.bot.user.name} help",
                icon_url=self.context.bot.user.display_avatar.url,
            )

            embed.add_field(
                name="",
                value=f"```Ruby\nSyntax: {syntax}\nExample: {self.context.clean_prefix}{group.qualified_name} {group.example.split(group.qualified_name)[-1].strip() if group.example and group.qualified_name in group.example else group.example or ''}```",
                inline=False,
            )

            embed.add_field(
                name="Permissions",
                value=f"{permissions}",
                inline=True,
            )

            embed.set_footer(
                text=f"Aliases: {', '.join(a for a in group.aliases) if len(group.aliases) > 0 else 'none'}",
                icon_url=self.context.author.display_avatar.url,
            )

            embeds.append(embed)

        for command in group.commands:
            try:
                syntax = f"{self.context.clean_prefix}{command.qualified_name} {' '.join([f'({parameter.name})' if not parameter.optional else f'[{parameter.name}]' for parameter in command.arguments])}"
            except AttributeError:
                syntax = f"{self.context.clean_prefix}{command.qualified_name}"

            try:
                permissions = ", ".join(
                    [
                        permission.lower().replace("n/a", "None").replace("_", " ")
                        for permission in command.permissions
                    ]
                )
            except AttributeError:
                permissions = "None"

            brief = command.brief or ""

            if permissions != "None" and brief:
                permissions = f"{permissions}"
            elif brief:
                permissions = brief

            embed = Embed(
                title=f"Command: {command.qualified_name} • {command.cog_name} module",
                description=f"> {command.description.capitalize() if command.description else (command.help.capitalize() if command.help else None)}",
            )

            embed.set_author(
                name=f"{self.context.bot.user.name} help",
                icon_url=self.context.bot.user.display_avatar.url,
            )

            embed.add_field(
                name="",
                value=f"```Ruby\nSyntax: {syntax}\nExample: {self.context.clean_prefix}{command.qualified_name} {command.example.split(command.qualified_name)[-1].strip() if command.example and command.qualified_name in command.example else command.example or ''}```",
                inline=False,
            )

            embed.add_field(
                name="Permissions",
                value=f"{permissions}",
                inline=True,
            )

            embed.set_footer(
                text=f"Aliases: {', '.join(a for a in command.aliases) if len(command.aliases) > 0 else 'none'}",
                icon_url=self.context.author.display_avatar.url,
            )

            embeds.append(embed)

        if embeds:
            paginator = Paginator(self.context, embeds)
            await paginator.start()
        else:
            await self.context.reply("No commands available in this group.")

    async def command_not_found(self, string: str) -> None:
        if not string:
            return

        error_message = (
            f"> {self.context.author.mention}: Command `{string}` does not exist"
        )
        embed = Embed(description=error_message)
        await self.context.send(embed=embed)

    async def subcommand_not_found(self, command: str, subcommand: str) -> None:
        if not command or not subcommand:
            return

        error_message = f"> {self.context.author.mention}: Command `{command} {subcommand}` does not exist"
        embed = Embed(description=error_message)
        await self.context.send(embed=embed)
