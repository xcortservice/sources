from .context import Context

from typing import Any, TYPE_CHECKING
from contextlib import suppress

from discord import (
    Forbidden,
    Guild,
    HTTPException,
    Invite,
    Member,
    NotFound,
    User,
)
from discord.ext.commands import (
    BadFlagArgument,
    BadInviteArgument,
    BadLiteralArgument,
    BadUnionArgument,
    ChannelNotFound,
    CheckFailure,
    CommandError,
    CommandInvokeError,
    CommandNotFound,
    CommandOnCooldown,
    DisabledCommand,
    FlagError,
    MaxConcurrencyReached,
    MemberNotFound,
    MessageNotFound,
    MissingFlagArgument,
    MissingPermissions,
    MissingRequiredArgument,
    MissingRequiredAttachment,
    MissingRequiredFlag,
    NSFWChannelRequired,
    NotOwner,
    RangeError,
    RoleNotFound,
    TooManyFlags,
    UserNotFound,
)

if TYPE_CHECKING:
    from greed.framework.discord import (
        format_timespan,
        human_join,
        plural,
    )


class CommandErrorHandler:
    """
    Custom command error handler for Greed.
    """
    async def on_command_error(
        self, ctx: Context, exc: CommandError
    ) -> Any:
        """
        Custom on_command_error method that handles command errors.
        """
        if not ctx.channel:
            return

        if not ctx.guild:
            can_send = True
        else:
            guild_me = ctx.guild.get_member(ctx.bot.user.id)
            can_send = (
                ctx.channel.permissions_for(
                    guild_me
                ).send_messages
                and ctx.channel.permissions_for(
                    guild_me
                ).embed_links
            )

        if not can_send:
            return

        if isinstance(
            exc,
            (
                CommandNotFound,
                DisabledCommand,
                NotOwner,
            ),
        ):
            return

        elif isinstance(
            exc,
            (
                MissingRequiredArgument,
                MissingRequiredAttachment,
                BadLiteralArgument,
            ),
        ):
            return await ctx.send_help(ctx.command)

        elif isinstance(exc, FlagError):
            if isinstance(exc, TooManyFlags):
                return await ctx.embed(
                    f"You specified the **{exc.flag.name}** flag more than once!",
                    "warned",
                )

            elif isinstance(exc, MissingRequiredFlag):
                return await ctx.embed(
                    f"You must specify the **{exc.flag.name}** flag!",
                    "warned",
                )

            elif isinstance(exc, MissingFlagArgument):
                return await ctx.embed(
                    f"You must specify a value for the **{exc.flag.name}** flag!",
                    "warned",
                )

        if isinstance(exc, CommandInvokeError):
            return await ctx.embed(exc.original, message_type="warned")

        elif isinstance(exc, MaxConcurrencyReached):
            if ctx.command.qualified_name in (
                "lastfm set",
                "lastfm index",
            ):
                return

            return await ctx.embed(
                f"This command can only be used **{plural(exc.number):time}** per **{exc.per.name}** concurrently!",
                "warned",
            )

        elif isinstance(exc, CommandOnCooldown):
            if exc.retry_after > 30:
                return await ctx.embed(
                    f"This command is currently on cooldown!\nTry again in **{format_timespan(exc.retry_after)}**",
                    "warned",
                )

            return await ctx.message.add_reaction("⏰")

        elif isinstance(exc, BadUnionArgument):
            if exc.converters == (Member, User):
                return await ctx.embed(
                    f"No **{exc.param.name}** was found matching **{ctx.current_argument}**!\nIf the user is not in this server, try using their **ID** instead",
                    "warned",
                )

            elif exc.converters == (Guild, Invite):
                return await ctx.embed(
                    f"No server was found matching **{ctx.current_argument}**!",
                    "warned",
                )

            else:
                return await ctx.embed(
                    f"Casting **{exc.param.name}** to {human_join([f'`{c.__name__}`' for c in exc.converters])} failed!",
                    "warned",
                )

        elif isinstance(exc, MemberNotFound):
            return await ctx.embed(
                f"No **member** was found matching **{exc.argument}**!",
                "warned",
            )

        elif isinstance(exc, UserNotFound):
            return await ctx.embed(
                f"No **user** was found matching `{exc.argument}`!",
                "warned",
            )

        elif isinstance(exc, RoleNotFound):
            return await ctx.embed(
                f"No **role** was found matching **{exc.argument}**!",
                "warned",
            )

        elif isinstance(exc, ChannelNotFound):
            return await ctx.embed(
                f"No **channel** was found matching **{exc.argument}**!",
                "warned",
            )

        elif isinstance(exc, BadInviteArgument):
            return await ctx.embed(
                "Invalid **invite code** provided!",
                "warned",
            )

        elif isinstance(exc, MessageNotFound):
            return await ctx.embed(
                "The provided **message** was not found!\n Try using the **message URL** instead"
                "warned",
            )

        elif isinstance(exc, RangeError):
            label = ""
            if (
                exc.minimum is None
                and exc.maximum is not None
            ):
                label = f"no more than `{exc.maximum}`"
            elif (
                exc.minimum is not None
                and exc.maximum is None
            ):
                label = f"no less than `{exc.minimum}`"
            elif (
                exc.maximum is not None
                and exc.minimum is not None
            ):
                label = f"between `{exc.minimum}` and `{exc.maximum}`"

            if label and isinstance(exc.value, str):
                label += " characters"

            return await ctx.embed(
                f"The input must be {label}!", "warned"
            )

        elif isinstance(exc, MissingPermissions):
            permissions = human_join(
                [
                    f"`{permission}`"
                    for permission in exc.missing_permissions
                ],
                final="and",
            )
            _plural = (
                "s"
                if len(exc.missing_permissions) > 1
                else ""
            )

            return await ctx.embed(
                f"You're missing the {permissions} permission{_plural}!",
                "warned",
            )

        elif isinstance(exc, NSFWChannelRequired):
            return await ctx.embed(
                "This command can only be used in NSFW channels!",
                "warned",
            )

        elif isinstance(exc, CommandError):
            if isinstance(
                exc, (HTTPException, NotFound)
            ) and not isinstance(
                exc, (CheckFailure, Forbidden)
            ):
                if "Unknown Channel" in exc.text:
                    return
                return await ctx.embed(
                    exc.text.capitalize(), "warned"
                )

            if isinstance(
                exc, (Forbidden, CommandInvokeError)
            ):
                error = (
                    exc.original
                    if isinstance(exc, CommandInvokeError)
                    else exc
                )

                if isinstance(error, Forbidden):
                    perms = ctx.guild.me.guild_permissions
                    missing_perms = []

                    if not perms.manage_channels:
                        missing_perms.append(
                            "`manage_channels`"
                        )
                    if not perms.manage_roles:
                        missing_perms.append(
                            "`manage_roles`"
                        )

                    error_msg = (
                        f"I'm missing the following permissions: {', '.join(missing_perms)}\n"
                        if missing_perms
                        else "I'm missing required permissions. Please check my role's permissions and position.\n"
                    )

                    return await ctx.embed(
                        error_msg,
                        f"Error: {str(error)}",
                        "warned",
                    )

                return await ctx.embed(str(error), "warned")

            origin = getattr(exc, "original", exc)
            with suppress(TypeError):
                if any(
                    forbidden in origin.args[-1]
                    for forbidden in (
                        "global check",
                        "check functions",
                        "Unknown Channel",
                    )
                ):
                    return

            return await ctx.embed(*origin.args, "warned")

        else:
            return await ctx.send_help(ctx.command)
