from __future__ import annotations

import asyncio

from typing import Optional

from discord import (
    Message,
    Role,
    Embed,
)
from discord.ext.commands import (
    CommandError,
    has_permissions,
    group,
    PartialEmojiConverter,
    Cog
)

from greed.framework import Greed, Context
from .views import ButtonRoleView, StyleConverter
from greed.shared.config import Colors

class ButtonRoles(Cog):
    """
    A class to manage button roles in Discord.
    """
    def __init__(self, bot: Greed):
        self.bot = bot

    @group(
        name="buttonrole",
        aliases=["buttonroles"],
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole(self, ctx: Context):
        """
        Create a button role.
        """
        return await ctx.send_help(ctx.command)

    @buttonrole.command(name="remove")
    @has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_remove(self, ctx: Context, message: Message, index: int):
        """
        Remove a button role from a message.
        """
        record = await self.bot.db.fetch(
            """
            SELECT index 
            FROM button_roles 
            WHERE message_id = $1 ORDER BY index ASC
            """
        )
        if index > len(record):
            index = len(index)
        
        await self.bot.db.execute(
            """
            DELETE FROM button_roles 
            WHERE message_id = $1 
            AND index = $2
            """,
            message.id,
            record[index - 1].index,
        )
        view = ButtonRoleView(self.bot, ctx.guild.id, message.id)
        await view.prepare()
        await message.edit(view=view)
        return await ctx.embed(
            message-f"successfully removed that button from the button roles on [this message]({message.jump_url})",
            message_type="warned"
        )

    @buttonrole.command(name="reset")
    @has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_reset(self, ctx: Context):
        """
        Reset all button roles in the guild.
        """
        for row in await self.bot.db.fetch(
            """
            SELECT message_id, channel_id 
            FROM button_roles 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        ):
            channel = ctx.guild.get_channel(row.channel_id)
            if not channel:
                continue
            try:
                message = await channel.fetch_message(row.message_id)
            except Exception:
                continue
            await message.edit(view=None)
        
        await self.bot.db.execute(
            """
            DELETE FROM button_roles 
            WHERE guild_id = $1
            """, 
            ctx.guild.id
        )
        return await ctx.embed(
            message="Successfully cleared all button roles",
            message_type="approved")

    @buttonrole.command(name="removeall")
    @has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_removeall(self, ctx: Context, message: Message):
        """
        Remove all button roles from a message.
        """
        await message.edit(view=None)
        await self.bot.db.execute(
            """
            DELETE FROM button_roles 
            WHERE message_id = $1
            """, 
            message.id
        )
        return await ctx.embed(
            message=f"Successfully removed all button roles from [this message]({message.jump_url})",
            message_type="approved"
        )

    @buttonrole.command(name="list", brief="View a list of every button role")
    @has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_list(self, ctx: Context):
        rows = []
        embed = Embed(color=Colors().information, title="Button roles").set_author(
            name=str(ctx.author), icon_url=ctx.author.display_avatar.url
        )
        i = 0
        for row in await self.bot.db.fetch(
            """SELECT message_id, channel_id, role_id FROM button_roles WHERE guild_id = $1 ORDER BY index ASC""",
            ctx.guild.id,
        ):
            if not (channel := ctx.guild.get_channel(row.channel_id)):
                asyncio.ensure_future(
                    self.bot.db.execute(
                        """DELETE FROM button_roles WHERE channel_id = $1 AND guild_id = $2""",
                        row.channel_id,
                        ctx.guild.id,
                    )
                )
                continue
            try:
                message = await channel.fetch_message(row.message_id)
            except Exception:
                asyncio.ensure_future(
                    self.bot.db.execute(
                        """DELETE FROM button_roles WHERE message_id = $1 AND guild_id = $2""",
                        row.message_id,
                        ctx.guild.id,
                    )
                )
                continue
            if not (role := ctx.guild.get_role(row.role_id)):
                asyncio.ensure_future(
                    self.bot.db.execute(
                        """DELETE FROM button_roles WHERE role_id = $1 AND guild_id = $2""",
                        row.role_id,
                        ctx.guild.id,
                    )
                )
                continue
            i += 1
            rows.append(f"`{i}` {role.mention} - [message]({message.jump_url})")
        return await ctx.paginate(embed, rows, 10, "button role", "button roles")

    @buttonrole.command(name="add")
    @has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_add(
        self,
        ctx: Context,
        message: Message,
        role: Role,
        style: StyleConverter,
        emoji: Optional[PartialEmojiConverter] = None,
        label: Optional[str] = None,
    ):
        """
        Add a button role to a message.
        """
        if not message.author.id == self.bot.user.id:
            raise CommandError("That is not a message that I created!")
        
        if not emoji and not label:
            raise CommandError("either an emoji or label must be provided!")
        
        record = await self.bot.db.fetch(
            """
            SELECT index 
            FROM button_roles 
            WHERE message_id = $1 ORDER BY index ASC
            """,
            message.id,
        )
        try:
            index = record[-1].index + 1
        
        except Exception:
            index = 1
        
        if label is not None and len(label) > 100:
            raise CommandError("Label must be 100 characters or less!")
        
        await self.bot.db.execute(
            """
            INSERT INTO button_roles (guild_id, message_id, channel_id, role_id, style, emoji, label, index) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            ctx.guild.id,
            message.id,
            message.channel.id,
            role.id,
            style,
            emoji,
            label,
            index,
        )
        view = ButtonRoleView(self.bot, ctx.guild.id, message.id)
        await view.prepare()
        await message.edit(view=view)
        return await ctx.embed(
            message=f"Successfully added button role for {role.mention} to [this message]({message.jump_url})",
            message_type="warned"
        )
    
async def setup(bot: Greed):
    await bot.add_cog(ButtonRoles(bot))