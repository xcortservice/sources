import traceback
from typing import Union

import discord
from aiohttp.client_exceptions import (ClientConnectorError,
                                       ClientHttpProxyError,
                                       ClientProxyConnectionError,
                                       ClientResponseError, ContentTypeError)
from discord.errors import HTTPException, Forbidden
from discord.ext import commands
from discord.ext.commands import (CheckFailure, CommandError,
                                  MaxConcurrencyReached, UserInputError)
from loguru import logger
from pomice import TrackLoadError

from ..classes.exceptions import EmbedError, SnipeError
from ..patch.alias import AliasConverter, CommandAlias, handle_aliases
from ..patch.context import Context


def codeblock(value: str):
    return f"```{value}```"


def multi_replace(text: str, to_replace: dict, once: bool = False) -> str:
    for r1, r2 in to_replace.items():
        if r1 in text:
            if once:
                text = text.replace(str(r1), str(r2), 1)
            else:
                text = text.replace(str(r1), str(r2))

    return text


def get_message(parameter: str) -> str:
    """
    Returns a grammatically correct message indicating a missing parameter.

    Args:
        parameter (str): The name of the missing parameter.

    Returns:
        str: A message indicating the missing parameter with correct grammar.
    """
    vowels = "aeiouAEIOU"
    article = (
        "an"
        if parameter[0] in vowels and parameter.lower() not in ("user", "member")
        else "a"
    )
    return f"Provide {article} **{parameter.title()}**"


class Errors:
    def __init__(self, bot):
        self.bot = bot
        self.ignored = tuple([commands.CommandNotFound, CheckFailure, UserInputError])
        self.debug = False

    def get_rl(self, exception: Exception) -> Union[int, float]:
        if hasattr(exception, "retry_after"):
            return exception.retry_after
        else:
            return 5

    def log_error(self, ctx: Context, exception: Exception) -> None:
        error = getattr(exception, "original", exception)
        exc = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        logger.error(
            f'{type(error).__name__:25} > {ctx.guild} | {ctx.author} "{ctx.message.content}" \n {error} \n {exc}'
        )

    async def handle_exceptions(self, ctx: Context, exception: Exception) -> None:
        bucket = self.bot._cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        self.log_error(ctx, exception)

        if self.debug is True:
            self.log_error(ctx, exception)
        if not isinstance(exception, commands.CommandNotFound):
            if retry_after:  # and type(exception) != commands.CommandNotFound:
                return
        try:
            if msg := getattr(exception, "message"):
                if msg == "lol":
                    return
        except Exception:
            pass

        error = getattr(exception, "original", exception)
        if isinstance(error, TrackLoadError):
            return
        if isinstance(exception, commands.BadArgument):
            return await ctx.warning(
                multi_replace(
                    exception.args[0].lower(),
                    {'"': "**", "int": "number", "str": "text"},
                )[:-1]
                .capitalize()
                .replace("Converting to ", "Converting to a ")
                .replace("for parameter ", "for the parameter ")
                + "."
            )
        if isinstance(exception, commands.BadUnionArgument):
            if await self.bot.object_cache.ratelimited(
                f"rl:cooldown_message{ctx.author.id}", 2, self.get_rl(exception) or 5
            ):
                return
            if "member_channel_role" in exception.args[0].lower():
                return await ctx.warning(
                    "could not find that **member** / **channel** / **role**"
                )
            return await ctx.warning(
                multi_replace(
                    exception.args[0].lower(),
                    {
                        "could not convert": "Could not find that",
                        '"': "**",
                        "into": "into a",
                        "member": "**member**",
                        "user": "**user**",
                        "guild": "**server**",
                        "invite": "**server invite**",
                        "textchannel": "**text channel**",
                        "voicechannel": "**voice channel**",
                        "**text channel** or **voice channel**": "**text or voice channel**",
                        "**voice channel** or **text channel**": "**voice or text channel**",
                        "categorychannel": "**category channel**",
                    },
                )[:-1].capitalize()
                + "."
            )
        elif isinstance(exception, (ClientProxyConnectionError, ClientHttpProxyError)):
            if await self.bot.object_cache.ratelimited(
                f"rl:cooldown_message{ctx.author.id}", 1, self.get_rl(exception) or 5
            ):
                return
            return await ctx.warning(
                "The **API** timed out during the request due to a proxy error"
            )
        elif isinstance(exception, EmbedError):
            if await self.bot.object_cache.ratelimited(
                f"rl:cooldown_message{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(exception.message)
        elif isinstance(exception, SnipeError):
            if await self.bot.object_cache.ratelimited(
                f"rl:cooldown_message{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(str(exception))
        elif isinstance(exception, ClientConnectorError):
            if await self.bot.object_cache.ratelimited(
                f"rl:cooldown_message{ctx.author.id}", 1, self.get_rl(exception) or 5
            ):
                return
            return await ctx.warning("The **API** timed out during the request")

        elif isinstance(exception, ClientResponseError):
            if await self.bot.object_cache.ratelimited(
                f"rl:cooldown_message{ctx.author.id}", 1, self.get_rl(exception) or 5
            ):
                return
            return await ctx.warning(
                f"The third party **API** returned a `{exception.status}`"
                + (
                    f" [*`{exception.message}`*](https://http.cat/{exception.status})"
                    if exception.message
                    else "!"
                )
            )

        elif isinstance(exception, ContentTypeError):
            if await self.bot.object_cache.ratelimited(
                f"rl:cooldown_message{ctx.author.id}", 1, self.get_rl(exception) or 5
            ):
                return
            return await ctx.warning("The **API** returned malformed content!")
        elif isinstance(exception, discord.Forbidden):
            if exception.code == 50101:
                return await ctx.warning(
                    "this server doesn't have enough boosts to perform this action"
                )
        if isinstance(exception, commands.CommandOnCooldown):
            if ctx.author.name == "aiohttp":
                return await ctx.reinvoke()
            if await self.bot.object_cache.ratelimited(
                f"rl:cooldown_message{ctx.author.id}", 1, self.get_rl(exception) or 5
            ):
                return
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(
                f"Command is on a ``{self.get_rl(exception) or 5:.2f}s`` **cooldown**"
            )
        if (
            isinstance(exception, (discord.errors.Forbidden, Forbidden))
            or "Forbidden" in exception.__repr__()
        ):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(str(exception).replace("_", " ").split(":")[-1])
        if isinstance(exception, commands.MissingPermissions):
            if ctx.author.id in self.bot.owner_ids:
                return await ctx.reinvoke()
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            missing_permissions = [
                _.replace("_", " ").title() for _ in exception.missing_permissions
            ]
            return await ctx.warning(
                f"**{', '.join(missing_permissions)}** permissions are required"
            )
        if isinstance(exception, commands.BotMissingPermissions):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            missing_permissions = [
                _.replace("_", " ").title() for _ in exception.missing_permissions
            ]
            return await ctx.warning(
                f"**{', '.join(missing_permissions)}** permissions are required"
            )
        if isinstance(exception, commands.MissingRequiredArgument):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(
                get_message(exception.param.name.replace("role_input", "role"))
            )
        if isinstance(exception, commands.BadArgument):
            error = exception
            tb = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            logger.info(tb)
            exception = (
                str(exception)
                .replace("Member", "**Member**")
                .replace("User", "**User**")
            )
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(f"{exception}")
        if isinstance(exception, commands.BadUnionArgument):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(f"{exception}")
        if isinstance(exception, commands.MemberNotFound):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning("I couldn't find that **member**")
        if isinstance(exception, commands.UserNotFound):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning("I couldn't find that **user**")
        if isinstance(exception, commands.RoleNotFound):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning("I couldn't find that **role**")
        if isinstance(exception, commands.ChannelNotFound):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning("I couldn't find that **channel**")
        if isinstance(exception, commands.EmojiNotFound):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning("I couldn't find that **emoji**")
        if isinstance(exception, HTTPException):
            code: int = exception.code
            if code == 0:
                if await self.bot.object_cache.ratelimited(
                    f"rl:error_message:{ctx.author.id}", 3, 5
                ):
                    return
                return await ctx.warning("Webhooks are **ratelimited** for this guild")
            if code == 50045:
                if await self.bot.object_cache.ratelimited(
                    f"rl:error_message:{ctx.author.id}", 3, 5
                ):
                    return
                return await ctx.warning("That asset is too **large**")

            elif code == 50013:
                if await self.bot.object_cache.ratelimited(
                    f"rl:error_message:{ctx.author.id}", 3, 5
                ):
                    return
                return await ctx.warning(
                    "I need `Administrative_Permissions` to work properly"
                )

            elif code == 60003 and self.application:
                if await self.bot.object_cache.ratelimited(
                    f"rl:error_message:{ctx.author.id}", 3, 5
                ):
                    return
                return await ctx.warning(
                    f"`{self.application.owner}` doesn't have **2FA** enabled!"
                )

            elif code == 50035:
                if await self.bot.object_cache.ratelimited(
                    f"rl:error_message:{ctx.author.id}", 3, 5
                ):
                    return
                return await ctx.warning(
                    f"I wasn't able to send the message!\n>>> {codeblock(exception.text)}"
                )
        if isinstance(exception, commands.CommandNotFound):
            aliases = [
                CommandAlias(command=command_name, alias=alias)
                for command_name, alias in await self.bot.db.fetch(
                    "SELECT command_name, alias FROM aliases WHERE guild_id = $1",
                    ctx.guild.id,
                )
            ]
            return await handle_aliases(ctx, aliases, exception)
        if type(exception) in self.ignored:
            return
        if isinstance(exception, MaxConcurrencyReached):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(
                f"the task `{ctx.command.qualified_name}` is already being ran"
            )
        if isinstance(exception, self.ignored):
            return
        if isinstance(error, self.ignored):
            return
        if type(error) in self.ignored:
            return
        if isinstance(exception, discord.ext.commands.errors.CheckFailure):
            return
        if isinstance(error, CommandError):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(str(exception))
        if (
            isinstance(error, discord.ext.commands.errors.CommandError)
            or isinstance(error, CommandError)
            or isinstance(error, discord.ext.commands.errors.CommandError)
        ):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(str(exception))
        if "Missing Permissions" in str(exception):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            return await ctx.warning(str(exception))
        if await self.bot.object_cache.ratelimited(
            f"rl:error_message:{ctx.author.id}", 3, 5
        ):
            return
        if isinstance(exception, TrackLoadError):
            return await ctx.warning(str(exception))
        if isinstance(exception, discord.NotFound):
            if await self.bot.object_cache.ratelimited(
                f"rl:error_message:{ctx.author.id}", 3, 5
            ):
                return
            if exception.code == "10003":
                return await ctx.warning("**Channel** not found")
            elif exception.code == "10008":
                return await ctx.warning("**Message** not found")
            elif exception.code == "10007":
                return await ctx.warning("**Member** not found")
            elif exception.code == "10011":
                return await ctx.warning("**Role** not found")
            elif exception.code == "10013":
                return await ctx.warning("**User** not found")
            elif exception.code == "10014":
                return await ctx.warning("**Emoji** not found")
            elif exception.code == "10015":
                return await ctx.warning("**Webhook** not found")
            elif exception.code == "10062":
                return
            else:
                self.log_error(ctx, exception)
                return await self.bot.send_exception(ctx, exception)
        if not isinstance(exception, CommandError):
            self.log_error(ctx, exception)
        if not isinstance(exception, (discord.errors.Forbidden, Forbidden)):
            logger.info(f"type of {exception} ({type(exception)}) is not Forbidden")
        return await self.bot.send_exception(ctx, exception)
