from __future__ import annotations

import discord

from contextlib import suppress
from typing import TYPE_CHECKING

from discord import Member, Role
from discord.ext.commands import (
    BadArgument,
    CommandError,
    MemberConverter,
    RoleConverter,
    RoleNotFound,
    Converter,
)
from discord.utils import find

if TYPE_CHECKING:
    from greed.framework import Context


class GoodRole(Converter):
    async def convert(
        self, ctx: Context, argument: str
    ) -> discord.Role:
        try:
            role = await RoleConverter().convert(
                ctx, argument
            )
        except BadArgument:
            role = discord.utils.get(
                ctx.guild.roles, name=argument
            )

        if (
            ctx.author.id in ctx.bot.owner_ids
            or ctx.author.id == ctx.guild.owner_id
        ):
            return role

        if role is None:
            raise BadArgument(
                f"No role called **{argument}** found!"
            )

        if role.position >= ctx.guild.me.top_role.position:
            raise BadArgument(
                f"{role.mention} is higher than my highest role!"
            )

        if role.position >= ctx.author.top_role.position:
            raise BadArgument(
                f"{role.mention} is higher than your highest role!"
            )

        return role


class FuzzyRole(RoleConverter):
    async def convert(
        self, ctx: Context, argument: str
    ) -> Role:
        with suppress(CommandError, BadArgument):
            return await super().convert(ctx, argument)

        role = find(
            lambda r: (
                r.name.lower() == argument.lower()
                or r.name.lower() in argument.lower()
            ),
            ctx.guild.roles,
        )
        if not role:
            raise RoleNotFound(argument)

        return role


class StrictRole(FuzzyRole):
    check_dangerous: bool
    check_integrated: bool
    allow_default: bool

    def __init__(
        self,
        *,
        check_dangerous: bool = False,
        check_integrated: bool = True,
        allow_default: bool = False,
    ) -> None:
        self.check_dangerous = check_dangerous
        self.check_integrated = check_integrated
        self.allow_default = allow_default
        super().__init__()

    @staticmethod
    def dangerous(role: Role) -> bool:
        return any(
            value
            and permission
            in (
                "administrator",
                "kick_members",
                "ban_members",
                "manage_guild",
                "manage_roles",
                "manage_channels",
                "manage_expressions",
                "manage_webhooks",
                "manage_nicknames",
                "mention_everyone",
            )
            for permission, value in role.permissions
        )

    async def check(self, ctx: Context, role: Role) -> None:
        if ctx.author.id in ctx.bot.owner_ids:
            return True

        if self.check_dangerous and self.dangerous(role):
            raise BadArgument(
                f"{role.mention} is a dangerous role and cannot be assigned!"
            )

        if self.check_integrated and role.managed:
            raise BadArgument(
                f"{role.mention} is an integrated role and cannot be assigned!"
            )

        if not self.allow_default and role.is_default():
            raise BadArgument(
                f"{role.mention} is the default role and cannot be assigned!"
            )

        if (
            role >= ctx.guild.me.top_role
            and ctx.bot.user.id != ctx.guild.owner_id
        ):
            raise BadArgument(
                f"{role.mention} is higher than my highest role!"
            )

        if (
            role >= ctx.author.top_role
            and ctx.author.id != ctx.guild.owner_id
        ):
            raise BadArgument(
                f"{role.mention} is higher than your highest role!"
            )

    async def convert(
        self, ctx: Context, argument: str
    ) -> Role:
        role = await super().convert(ctx, argument)
        await self.check(ctx, role)
        return role


class TouchableMember(MemberConverter):
    """
    Check if a member is punishable.
    """

    allow_author: bool

    def __init__(
        self, *, allow_author: bool = False
    ) -> None:
        self.allow_author = allow_author
        super().__init__()

    async def check(
        self, ctx: Context, member: Member
    ) -> None:
        if ctx.author.id in ctx.bot.owner_ids:
            return True

        if ctx.command.qualified_name in [
            "role",
            "role add",
            "role remove",
            "picperms",
        ]:
            return True

        if member.id in ctx.bot.owner_ids:
            raise BadArgument(
                f"You're not allowed to **{ctx.command.qualified_name}** a bot owner!"
            )

        if ctx.author == member and not self.allow_author:
            raise BadArgument(
                f"You're not allowed to **{ctx.command.qualified_name}** yourself!"
            )

        if (
            member.top_role >= ctx.author.top_role
            and ctx.author.id != ctx.guild.owner_id
        ):
            raise BadArgument(
                f"You're not allowed to **{ctx.command.qualified_name}** {member.mention} due to hierarchy!"
            )

    async def convert(
        self, ctx: Context, argument: str
    ) -> Member:
        member = await super().convert(ctx, argument)
        await self.check(ctx, member)
        return member
