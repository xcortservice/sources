from typing import Union
import discord
from discord.ext import commands
from discord.ext.commands import Context, CommandError
from discord.errors import HTTPException, NotFound
from greed.framework.script import Script


def get_message(parameter: str) -> str:
    vowels = "aeiouAEIOU"
    article = (
        "an"
        if parameter[0] in vowels and parameter.lower() not in ("user", "member")
        else "a"
    )
    return f"Provide {article} **{parameter.title()}**"


async def handle_command_error(ctx: Context, exception: Exception) -> None:
    error = getattr(exception, "original", exception)

    if isinstance(exception, commands.BadArgument):
        return await ctx.embed(str(exception).replace('"', "**"), "warned")

    elif isinstance(exception, commands.MissingRequiredArgument):
        return await ctx.embed(
            get_message(exception.param.name.replace("role_input", "role")), "warned"
        )

    elif isinstance(exception, commands.MissingPermissions):
        if ctx.author.id in ctx.bot.owner_ids:
            return await ctx.reinvoke()
        missing_permissions = [
            p.replace("_", " ").title() for p in exception.missing_permissions
        ]
        return await ctx.embed(
            f"**{', '.join(missing_permissions)}** permissions are required", "warned"
        )

    elif isinstance(exception, commands.BotMissingPermissions):
        missing_permissions = [
            p.replace("_", " ").title() for p in exception.missing_permissions
        ]
        return await ctx.embed(
            f"**{', '.join(missing_permissions)}** permissions are required", "warned"
        )

    elif isinstance(exception, commands.CommandOnCooldown):
        return await ctx.embed(
            f"Command is on a ``{exception.retry_after:.2f}s`` **cooldown**", "warned"
        )

    elif isinstance(exception, (commands.MemberNotFound, commands.UserNotFound)):
        return await ctx.embed("I couldn't find that **member**", "warned")

    elif isinstance(exception, commands.RoleNotFound):
        return await ctx.embed("I couldn't find that **role**", "warned")

    elif isinstance(exception, commands.ChannelNotFound):
        return await ctx.embed("I couldn't find that **channel**", "warned")

    elif isinstance(exception, commands.EmojiNotFound):
        return await ctx.embed("I couldn't find that **emoji**", "warned")

    elif isinstance(exception, HTTPException):
        if exception.code == 50013:
            return await ctx.embed("I am missing sufficient permissions!", "warned")
        elif exception.code == 50035:
            return await ctx.embed("I wasn't able to send the message!", "warned")

    elif isinstance(exception, NotFound):
        if exception.code == 10003:
            return await ctx.embed("**Channel** not found", "warned")
        elif exception.code == 10008:
            return await ctx.embed("**Message** not found", "warned")
        elif exception.code == 10007:
            return await ctx.embed("**Member** not found", "warned")
        elif exception.code == 10011:
            return await ctx.embed("**Role** not found", "warned")
        elif exception.code == 10013:
            return await ctx.embed("**User** not found", "warned")
        elif exception.code == 10014:
            return await ctx.embed("**Emoji** not found", "warned")
        elif exception.code == 10015:
            return await ctx.embed("**Webhook** not found", "warned")

    elif isinstance(error, Script.EmbedError):
        return await ctx.embed(str(error), "warned")

    elif isinstance(error, CommandError):
        return await ctx.embed(str(exception), "warned")
