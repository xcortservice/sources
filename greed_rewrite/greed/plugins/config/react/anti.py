from __future__ import annotations

from typing import Union
from contextlib import suppress

from discord import (
    Role,
    RawReactionActionEvent,
    Member,
    User,
    Object,
    HTTPException,
    TextChannel
)
from discord.ext.commands import (
    has_permissions,
    group,
    Cog
)

from greed.framework import Greed, Context

class AntiSelfReact(Cog):
    """
    Punishes users for reacting to their own messages.
    """
    def __init__(self, bot: Greed):
        self.bot = bot

    @group(
        name="antiselfreact", 
        aliases=["antisr"]
    )
    @has_permissions(manage_messages=True)
    async def antiselfreact(self, ctx: Context):
        """
        Enable or disable Anti-Self-React in the guild.
        """
        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command)

    @antiselfreact.command(
        name="enable", 
        aliases=["on"]
    )
    @has_permissions(manage_messages=True)
    async def enable(self, ctx: Context):
        """
        Enable Anti-Self-React in the guild.
        """
        await self.bot.db.execute(
            """
            INSERT INTO antisr_guilds (guild_id) 
            VALUES ($1) 
            ON CONFLICT(guild_id) DO NOTHING
            """,
            ctx.guild.id,
        )
        await ctx.embed(
            message="AntiSelfReact has been enabled in this server",
            message_type="approved"
        )

    @antiselfreact.command(
        name="disable", 
        aliases=["off"]
    )
    @has_permissions(manage_messages=True)
    async def disable(self, ctx: Context):
        """
        Disable Anti-Self-React in the guild.
        """
        await self.bot.db.execute(
            """
            DELETE FROM antisr_guilds 
            WHERE guild_id = $1
            """, 
            ctx.guild.id
        )
        await ctx.embed(
            message="AntiSelfReact has been disabled in this server",
            message_type="approved"
        )

    @antiselfreact.command(
        name="add", 
        aliases=["include"]
    )
    @has_permissions(manage_messages=True)
    async def add(self, ctx: Context, user: Member):
        """
        Add a user to the Anti-Self-React list.
        """
        await self.bot.db.execute(
            """
            INSERT INTO antisr_users (guild_id, user_id) 
            VALUES ($1, $2) 
            ON CONFLICT DO NOTHING
            """,
            ctx.guild.id,
            user.id,
        )
        await ctx.embed(
            message=f"{user.mention} has been added to the AntiSelfReact list.",
            message_type="approved"
        )

    @antiselfreact.command(
        name="remove",
        aliases=["exclude"],
    )
    @has_permissions(manage_messages=True)
    async def remove(
        self, 
        ctx: Context, 
        user: Member
    ):
        """
        Remove a user from the Anti-Self-React list.
        """
        await self.bot.db.execute(
            """
            DELETE FROM antisr_users 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            ctx.guild.id,
            user.id,
        )
        await ctx.embed(
            message=f"{user.mention} has been removed from the AntiSelfReact list",
            message_type="approved"
        )

    @antiselfreact.command(
        name="ignore", 
        aliases=["skip"]
    )
    @has_permissions(manage_messages=True)
    async def ignore(
        self, 
        ctx: Context, 
        target: Object
    ):
        """
        Ignore a user or role from Anti-Self-React.
        """
        is_role = isinstance(target, Role)
        await self.bot.db.execute(
            """
            INSERT INTO antisr_ignores (guild_id, target_id, is_role) 
            VALUES ($1, $2, $3) ON CONFLICT DO NOTHING
            """,
            ctx.guild.id,
            target.id,
            is_role,
        )
        await ctx.embed(
            message=f"{'Role' if is_role else 'User'} {target.id} has been ignored.",
            message_type="approved"
        )

    @antiselfreact.command(
        name="unignore", 
        aliases=["unskip"]
    )
    @has_permissions(manage_messages=True)
    async def unignore(
        self, 
        ctx: Context, 
        target: Union[Role, Member, User]
    ):
        """
        Unignore a user or role from Anti-Self-React.
        """
        is_role = isinstance(target, Role)
        await self.bot.db.execute(
            """
            DELETE FROM antisr_ignores 
            WHERE guild_id = $1 
            AND target_id = $2 
            AND is_role = $3
            """,
            ctx.guild.id,
            target.id,
            is_role,
        )
        await ctx.embed(
            message=f"{'Role' if is_role else 'User'} {target.id} is no longer ignored.",
            message_type="approved"
        )

    @Cog.listener("on_raw_reaction_add")
    async def antireact(self, payload: RawReactionActionEvent):
        """
        Handle reaction events and enforce Anti-Self-React.
        """
        if payload.guild_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        if not await self.bot.db.fetchrow(
            """
            SELECT 1 FROM antisr_guilds 
            WHERE guild_id = $1
            """, 
            guild.id
        ):
            return

        with suppress(Exception):
            member = guild.get_member(payload.user_id) or await guild.fetch_member(
                payload.user_id
            )

        channel = guild.get_channel(payload.channel_id)
        if not channel or not isinstance(channel, TextChannel):
            return

        with suppress(Exception):
            message = await channel.fetch_message(payload.message_id)

        if message.author.id != member.id:
            return

        role_ids = [role.id for role in member.roles]
        exempt = await self.bot.db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM antisr_ignores
                WHERE guild_id = $1
                AND (
                    (target_id = $2 AND NOT is_role) OR
                    (target_id = ANY($3::BIGINT[]) AND is_role)
                )
            )
            """,
            guild.id,
            member.id,
            role_ids,
        )

        if exempt:
            return

        if not await self.bot.db.fetchrow(
            """
            SELECT 1 FROM antisr_users 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            guild.id,
            member.id,
        ):
            return

        with suppress(HTTPException):
            await message.remove_reaction(payload.emoji, member)

        with suppress(Exception):
            await member.kick(reason="Anti-Self-React: Reacted to own message")


async def setup(bot: Greed):
    await bot.add_cog(AntiSelfReact(bot))