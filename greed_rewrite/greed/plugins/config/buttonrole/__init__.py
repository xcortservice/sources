from __future__ import annotations

import typing
import asyncio
import re
from typing import Optional, TYPE_CHECKING
import discord
from discord.ext import commands
from discord import PartialEmoji
from discord.ext.commands import Context, Converter
from greed.shared.config import Colors

if TYPE_CHECKING:
    from greed.framework import Greed


def to_style(style: int) -> discord.ButtonStyle:
    styles = {
        1: discord.ButtonStyle.primary,
        2: discord.ButtonStyle.secondary,
        3: discord.ButtonStyle.success,
        4: discord.ButtonStyle.danger,
        5: discord.ButtonStyle.link,
    }
    return styles.get(style, discord.ButtonStyle.primary)


class Message(Converter[discord.Message]):
    async def convert(self, ctx: Context, argument: str) -> discord.Message:
        try:
            message = await commands.MessageConverter().convert(ctx, argument)
        except commands.BadArgument:
            raise commands.BadArgument("Message not found.")
        return message


class Role(Converter[discord.Role]):
    async def convert(self, ctx: Context, argument: str) -> discord.Role:
        try:
            role = await commands.RoleConverter().convert(ctx, argument)
        except commands.BadArgument:
            raise commands.BadArgument("Role not found.")
        return role


class StyleConverter(Converter[int]):
    async def convert(self, ctx: Context, argument: str) -> int:
        styles = {
            "primary": 1,
            "secondary": 2,
            "success": 3,
            "danger": 4,
            "link": 5,
        }
        if argument.lower() not in styles:
            raise commands.BadArgument(
                "Invalid style. Must be primary, secondary, success, danger, or link."
            )
        return styles[argument.lower()]


class PartialEmojiConverter(Converter[Optional[PartialEmoji]]):
    async def convert(self, ctx: Context, argument: str) -> Optional[PartialEmoji]:
        try:
            return await commands.PartialEmojiConverter().convert(ctx, argument)
        except commands.BadArgument:
            return None


class ButtonRole(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"button:role:(?P<guild_id>[0-9]+):(?P<role_id>[0-9]+):(?P<message_id>[0-9]+)",
):
    def __init__(
        self,
        guild_id: int,
        role_id: int,
        message_id: int,
        emoji: Optional[str] = None,
        label: Optional[str] = None,
        style: Optional[discord.ButtonStyle] = discord.ButtonStyle.primary,
    ):
        super().__init__(
            discord.ui.Button(
                label=label,
                style=style,
                emoji=emoji,
                custom_id=f"button:role:{guild_id}:{role_id}:{message_id}",
            )
        )
        self.guild_id = guild_id
        self.role_id = role_id
        self.message_id = message_id
        self.emoji = emoji
        self.label = label
        self.style = style

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):  # type: ignore
        kwargs = {
            "guild_id": int(match["guild_id"]),
            "role_id": int(match["role_id"]),
            "message_id": int(match["message_id"]),
        }
        return cls(**kwargs)

    async def assign_role(self, interaction: discord.Interaction, role: discord.Role):
        try:
            await interaction.user.add_roles(role, reason="Button Role")
        except Exception:
            return await interaction.fail(f"i couldn't assign {role.mention} to you")
        return await interaction.success(f"successfully gave you {role.mention}")

    async def remove_role(self, interaction: discord.Interaction, role: discord.Role):
        try:
            await interaction.user.remove_roles(role, reason="Button Role")
        except Exception:
            return await interaction.fail(f"i couldn't assign {role.mention} to you")
        return await interaction.success(f"successfully gave you {role.mention}")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        role = guild.get_role(self.role_id)
        if not role:
            return
        if not role.is_assignable():
            return
        if role.is_dangerous():
            return
        if role not in interaction.user.roles:
            return await self.assign_role(interaction, role)
        else:
            return await self.remove_role(interaction, role)


class ButtonRoleView(discord.ui.View):
    def __init__(self, bot: discord.Client, guild_id: int, message_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.message_id = message_id

    async def prepare(self):
        data = await self.bot.db.fetch(
            """SELECT * FROM button_roles WHERE guild_id = $1 AND message_id = $2 ORDER BY index DESC""",
            self.guild_id,
            self.message_id,
        )
        for entry in data:
            kwargs = {
                "guild_id": self.guild_id,
                "role_id": entry.role_id,
                "message_id": entry.message_id,
                "emoji": entry.emoji,
                "label": entry.label,
                "style": to_style(entry.style),
            }
            self.add_item(ButtonRole(**kwargs))
        self.bot.add_view(self, message_id=self.message_id)


class buttonrole(commands.Cog, name="ButtonRole"):
    def __init__(self, bot: "Greed"):
        self.bot = bot

    @commands.group(
        name="buttonrole",
        aliases=["buttonroles"],
        brief="No Description Provided",
        invoke_without_command=True,
    )
    @commands.has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @buttonrole.command(
        name="remove",
        brief="Remove a button role from a message",
        example=",buttonrole remove discord.channels/... 3",
    )
    @commands.has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_remove(self, ctx: Context, message: Message, index: int):
        entries = await self.bot.db.fetch(
            """SELECT index FROM button_roles WHERE message_id = $1 ORDER BY index ASC""",
            message.id,
        )
        if index > len(entries):
            index = len(entries)
        await self.bot.db.execute(
            """DELETE FROM button_roles WHERE message_id = $1 AND index = $2""",
            message.id,
            entries[index - 1].index,
        )
        view = ButtonRoleView(self.bot, ctx.guild.id, message.id)
        await view.prepare()
        await message.edit(view=view)
        return await ctx.embed(
            f"successfully removed that button from the button roles on [this message]({message.jump_url})",
            "approved",
        )

    @buttonrole.command(name="reset", brief="Clears every button role from guild")
    @commands.has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_reset(self, ctx: Context):
        for row in await self.bot.db.fetch(
            """SELECT message_id, channel_id FROM button_roles WHERE guild_id = $1""",
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
            """DELETE FROM button_roles WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.embed("successfully cleared all button roles", "approved")

    @buttonrole.command(
        name="removeall",
        brief="Removes all button roles from a message",
        example=",buttonrole removeall discord.com/channels/...",
    )
    @commands.has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_removeall(self, ctx: Context, message: Message):
        await message.edit(view=None)
        await self.bot.db.execute(
            """DELETE FROM button_roles WHERE message_id = $1""", message.id
        )
        return await ctx.embed(
            f"successfully removed all button roles from [this message]({message.jump_url})",
            "approved",
        )

    @buttonrole.command(name="list", brief="View a list of every button role")
    @commands.has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_list(self, ctx: Context):
        rows = []
        embed = discord.Embed(color=Colors().information, title="Button roles").set_author(
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

    @buttonrole.command(name="add", brief="add a button role", example="")
    @commands.has_permissions(manage_guild=True, manage_roles=True)
    async def buttonrole_add(
        self,
        ctx: Context,
        message: Message,
        role: Role,
        style: StyleConverter,
        emoji: Optional[PartialEmojiConverter] = None,
        label: Optional[str] = None,
    ):
        if not message.author.id == self.bot.user.id:
            raise commands.CommandError("That is not a message that I created")
        if not emoji and not label:
            raise commands.CommandError("either an emoji or label must be provided")
        indexes = await self.bot.db.fetch(
            """SELECT index FROM button_roles WHERE message_id = $1 ORDER BY index ASC""",
            message.id,
        )
        try:
            index = indexes[-1].index + 1
        except Exception:
            index = 1
        if label is not None and len(label) > 100:
            raise commands.CommandError("label must be 100 characters or less")
        await self.bot.db.execute(
            """INSERT INTO button_roles (guild_id, message_id, channel_id, role_id, style, emoji, label, index) VALUES($1, $2, $3, $4, $5, $6, $7, $8)""",
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
            f"Successfully added button role for {role.mention} to [this message]({message.jump_url})",
            "approved",
        )


async def setup(bot):
    await bot.add_cog(buttonrole(bot))
