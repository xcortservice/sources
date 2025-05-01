import discord

from typing import Union

from .context import Context


class Hierarchy:
    """
    Custom hierarchy check for Greed.
    """
    async def hierarchy(
        self,
        ctx: Context,
        member: Union[discord.Member, discord.User],
        allow_self: bool = False,
    ) -> bool:

        bot_member = ctx.guild.me
        author = ctx.author

        if isinstance(member, discord.User):
            return True

        if (
            isinstance(member, discord.Member)
            and bot_member.top_role <= member.top_role
        ):
            await ctx.embed(
                f"I don't have high enough roles to perform this action on {member.mention}",
                "warned",
            )
            return False

        if author.id == member.id:
            if not allow_self:
                await ctx.embed("You cannot use this command on yourself", "warned")
                return False
            return True

        if author.id == ctx.guild.owner_id:
            return True

        if member.id == ctx.guild.owner_id:
            await ctx.embed("You cannot use this command on the server owner", "warned")
            return False

        if isinstance(author, discord.ClientUser) or not hasattr(author, "top_role"):
            return True

        if author.top_role.is_default():
            await ctx.embed("You need roles with permissions to use this command", "warned")
            return False

        if author.top_role <= member.top_role:
            if author.top_role == member.top_role:
                await ctx.embed(
                    "You cannot target users with the same top role as you",
                    "warned",
                )
            else:
                await ctx.embed("You cannot target users with higher roles than you", "warned")
            return False

        return True
