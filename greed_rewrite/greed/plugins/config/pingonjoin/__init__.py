from discord import TextChannel
from discord.ext import commands
from discord.ext.commands import Cog, group, has_permissions

from greed.framework import Greed, Context
from greed.framework.discord.parser import EmbedConverter

class PingOnJoin(Cog):
    """
    Punishes users for reacting to their own messages.
    """
    def __init__(self, bot: Greed):
        self.bot = bot

    @group(
        name="pingonjoin",
        aliases=["poj"],
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def pingonjoin(self, ctx: Context):
        """
        Ping new members when they join the server.
        """
        return await ctx.send_help(ctx.command.qualified_name)

    @pingonjoin.command(
        name="enable", 
        aliases=["on"]
    )
    @has_permissions(manage_guild=True)
    async def pingonjoin_enable(
        self, 
        ctx: Context, 
        channel: TextChannel, 
        threshold: int = None
    ):
        """
        Enable ping on join in the specified channel.
        """
        threshold = threshold or 1
        await self.bot.db.execute(
            """
            INSERT INTO pingonjoin (guild_id, channel_id, threshold) 
            VALUES ($1, $2, $3)
              ON CONFLICT (guild_id) 
              DO UPDATE SET channel_id = excluded.channel_id, threshold = excluded.threshold
            """,
            ctx.guild.id,
            channel.id,
            threshold,
        )
        return await ctx.embed(
            message=f"Ping on join enabled in {channel.mention} with a threshold of {threshold}",
            message_type="approved",
        )

    @pingonjoin.command(
        name="message",
        aliases=["msg"],
    )
    @commands.has_permissions(manage_guild=True)
    async def pingonjoin_message(self, ctx: Context, *, message: EmbedConverter):
        """
        Customize the message sent when a user joins the server.
        """
        await self.bot.db.execute(
            """
            UPDATE pingonjoin SET message = $1 
            WHERE guild_id = $2
            """,
            message,
            ctx.guild.id,
        )
        return await ctx.embed(
            message=f"Ping on join message set to {message}", 
            message_type="approved"
        )

    @pingonjoin.command(
        name="disable", 
        aliases=["off", "reset"], 
    )
    @has_permissions(manage_guild=True)
    async def pingonjoin_disable(self, ctx: Context):
        """
        Reset the ping on join settings in the guild.
        """
        await self.bot.db.execute(
            """
            DELETE FROM pingonjoin 
            WHERE guild_id = $1
            """, 
            ctx.guild.id
        )
        return await ctx.embed(
            message="Ping on join has been disabled", 
            message_type="approved"
        )

    
async def setup(bot: Greed):
    await bot.add_cog(PingOnJoin(bot))