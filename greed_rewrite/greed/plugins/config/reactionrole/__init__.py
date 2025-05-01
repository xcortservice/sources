from __future__ import annotations

import re
from typing import Union, TYPE_CHECKING
import discord
from discord.ext import commands
from discord.ext.commands import (
    Context,
    Converter,
    RoleConverter,
    PartialEmojiConverter,
)
from discord.ext.commands.errors import CommandError
from greed.shared.config import Colors
from greed.framework.pagination import Paginator

if TYPE_CHECKING:
    from greed.framework import Greed

DEFAULT_EMOJIS = re.compile(
    r"[\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001f926-\U0001f937\U0001F1E0-\U0001F1FF]+"
)


class ReactionRoleConverter(Converter):
    async def convert(self, ctx: Context, argument: str):
        argument = argument.replace("  ", " ")
        message = None
        emoji = None
        role = None
        splitting_char = ""
        if "," in argument:
            splitting_char += ","
        else:
            splitting_char += " "
        if argument.count(splitting_char) == 1:
            emoji, role = argument.split(splitting_char, 1)
        elif argument.count(splitting_char) == 2:
            message, emoji, role = argument.split(splitting_char, 2)
        else:
            raise CommandError("Please include a message, emoji, and role")
        if not message:
            if ctx.message.reference:
                message = ctx.message.reference.jump_url
        if message:
            message = await commands.MessageConverter().convert(ctx, message.strip())
        if not DEFAULT_EMOJIS.findall(emoji):
            emoji = await PartialEmojiConverter().convert(ctx, emoji.strip())
        else:
            emoji = emoji.replace(" ", "")
        role = await RoleConverter().convert(ctx, role)
        role = role[0]
        if not role:
            raise CommandError("Missing required argument **Role**")
        if not emoji:
            raise CommandError("Missing required argument **Emoji**")
        if not message:
            raise CommandError("Missing required argument **Message**")
        return {"message": message, "emoji": emoji, "role": role}


class reactionrole(commands.Cog, name="ReactionRole"):
    def __init__(self, bot: "Greed"):
        self.bot = bot

    @commands.group(
        name="reactionrole",
        aliases=["reactionroles", "rr", "reactrole"],
        example=",reactionrole",
        brief="Configure reaction role settings",
    )
    @commands.has_permissions(manage_roles=True)
    async def reactionrole(self, ctx: Context):
        if ctx.subcommand_passed is not None:
            return
        return await ctx.send_help(ctx.command.qualified_name)

    @reactionrole.command(
        name="add",
        aliases=["a", "create", "c"],
        brief="Add a reaction role to a message",
        example=",autoreaction add [message] [emoji] [roles]",
    )
    async def reactionrole_add(
        self, ctx: Context, *, message_emoji_role: ReactionRoleConverter
    ):
        emoji = str(message_emoji_role["emoji"])
        message = message_emoji_role["message"]
        role = message_emoji_role["role"]

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException as e:
            if e.code == 10014:
                return await ctx.embed(
                    "Invalid emoji provided. Please use a valid emoji.", "warned"
                )
            raise

        if await self.bot.db.fetch(
            """SELECT * FROM reactionrole WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3 AND emoji = $4 AND role_id = $5""",
            ctx.guild.id,
            message.channel.id,
            message.id,
            emoji,
            role.id,
        ):
            await self.bot.db.execute(
                """DELETE FROM reactionrole WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3 AND emoji = $4 AND role_id = $5""",
                ctx.guild.id,
                message.channel.id,
                message.id,
                emoji,
                role.id,
            )
        await self.bot.db.execute(
            """INSERT INTO reactionrole (guild_id,channel_id,message_id,emoji,role_id,message_url) VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(guild_id,channel_id,message_id,emoji,role_id) DO UPDATE SET role_id = excluded.role_id""",
            ctx.guild.id,
            message.channel.id,
            message.id,
            emoji,
            role.id,
            message.jump_url,
        )

        return await ctx.embed("**Reaction role** has been **added to that message**", "approved")

    def get_emoji(self, emoji: str):
        try:
            emoji = emoji
            return emoji
        except Exception:
            return emoji

    @reactionrole.command(
        name="remove",
        aliases=["delete", "del", "rem", "r", "d"],
        brief="Remove a reaction role from a message",
        example=",reactionrole remove [message_id] [emoji]",
    )
    async def reactionrole_remove(
        self,
        ctx: Context,
        message: discord.Message,
        emoji: Union[discord.Emoji, discord.PartialEmoji, str],
    ):
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji = str(emoji)
        else:
            emoji = emoji
        await self.bot.db.execute(
            """DELETE FROM reactionrole WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3 AND emoji = $4""",
            ctx.guild.id,
            message.channel.id,
            message.id,
            emoji,
        )
        return await ctx.embed("**Removed** the **reaction role**", "approved")

    @reactionrole.command(
        name="clear",
        brief="Clear all reaction roles from a message",
        example=",reactionrole clear",
    )
    async def reactionrole_clear(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM reactionrole WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.embed("**Cleared** all **reaction roles** if any exist", "approved")

    @reactionrole.command(
        name="list",
        brief="View a list of all reaction roles set to messages",
        example=",reactionrole list",
    )
    async def reactionrole_list(self, ctx: Context):
        rows = []
        i = 0
        for (
            channel_id,
            message_id,
            emoji,
            role_id,
            message_url,
        ) in await self.bot.db.fetch(
            """SELECT channel_id,message_id,emoji,role_id,message_url FROM reactionrole WHERE guild_id = $1""",
            ctx.guild.id,
        ):
            if ctx.guild.get_channel(channel_id):
                emoji = self.get_emoji(str(emoji))
                if role := ctx.guild.get_role(role_id):
                    i += 1
                    rows.append(
                        f"`{i}.` [Message]({message_url}) - {emoji} - {role.mention}"
                    )
        embed = discord.Embed(
            title=f"{ctx.guild.name}'s reaction roles",
            url=self.bot.domain,
            color=Colors().information,
        )
        if len(rows) == 0:
            return await ctx.embed("**No reaction roles found**", "warned")
        return await Paginator(ctx, rows, embed=embed, per_page=10).start()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        if data := await self.bot.db.fetchrow(
            """SELECT role_id FROM reactionrole WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3 AND emoji = $4""",
            payload.guild_id,
            payload.channel_id,
            payload.message_id,
            str(payload.emoji),
        ):
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member:
                return

            role = guild.get_role(data["role_id"])
            if not role:
                return

            try:
                await member.add_roles(role)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        if data := await self.bot.db.fetchrow(
            """SELECT role_id FROM reactionrole WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3 AND emoji = $4""",
            payload.guild_id,
            payload.channel_id,
            payload.message_id,
            str(payload.emoji),
        ):
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member:
                return

            role = guild.get_role(data["role_id"])
            if not role:
                return

            try:
                await member.remove_roles(role)
            except discord.HTTPException:
                pass


async def setup(bot: "Greed"):
    await bot.add_cog(reactionrole(bot))
