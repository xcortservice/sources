import json

from discord.ext import commands
from discord.ext.commands import (
    MissingPermissions,
    CommandError,
    check,
    Converter,
)

from greed.framework import Context


class ValidPermission(Converter):
    async def convert(self, ctx: Context, argument: str):
        """
        Convert the argument to a valid permission.
        """
        valid_permissions = [p[0] for p in ctx.author.guild_permissions]

        if not argument in valid_permissions:
            prefix = getattr(ctx, "clean_prefix", ",")
            return await ctx.embed(
                f"This is **not** a valid permission. Please run `{prefix}fakepermissions permissions` to check all available permissions!",
                message_type="warned",
            )

        return argument


def has_permissions(**permissions):
    async def predicate(ctx: Context):
        """
        Check if the user has permissions to use the command.
        """
        if ctx.author.id in ctx.bot.owner_ids or (
            "guild_owner" in permissions and ctx.author.id == ctx.guild.owner_id
        ):
            return True

        author_permissions = [p[0] for p in ctx.author.guild_permissions if p[1]]
        if any(p in author_permissions for p in permissions):
            return True

        roles = ", ".join(str(r.id) for r in ctx.author.roles)
        results = await ctx.bot.pool.fetch(
            """
            SELECT permission 
            FROM fake_permissions 
            WHERE guild_id = $1 
            AND role_id IN ({roles})
            """,
            ctx.guild.id,
        )

        for result in results:
            fake_perms = json.loads(result[0])
            if "administrator" in fake_perms or any(
                p in fake_perms for p in permissions
            ):
                return True

        raise MissingPermissions([p for p in permissions])

    return commands.check(predicate)


def is_donator():
    async def predicate(ctx: Context):
        """
        Verify if the author is a donator.
        """
        if ctx.author.id in ctx.bot.owner_ids:
            return True

        record = await ctx.bot.pool.fetchrow(
            """
            SELECT user_id 
            FROM donators 
            WHERE user_id = $1
            """,
            ctx.author.id,
        )

        if record:
            return True

        raise CommandError(
            f"You must be a **donator** to use `{ctx.command.qualified_name}` - [**Discord Server**](https://discord.gg/greed)"
        )

    return check(predicate)


commands.has_permissions = has_permissions
