from discord.ext.commands import CheckFailure, CommandError, check

from .context import Context


def is_booster():
    async def predicate(ctx: Context) -> bool:
        if ctx.author.premium_since:
            return True
        if ctx.author.id in ctx.bot.owner_ids:
            return True
        else:
            raise CommandError("you have not boosted the server.")

    return check(predicate)


def guild_owner():
    async def predicate(ctx: Context) -> bool:
        if ctx.author.id == ctx.guild.owner_id or ctx.author.id in ctx.bot.owner_ids:
            return True
        raise CommandError("you aren't the guild owner.")

    return check(predicate)


def is_staff():
    async def predicate(ctx: Context) -> bool:
        if ctx.author.id in ctx.bot.owner_ids:
            return True
        return False

    return check(predicate)
