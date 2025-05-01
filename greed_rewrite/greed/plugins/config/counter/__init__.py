from discord import TextChannel
from discord.ext import commands
from discord.ext.commands import Cog, group, has_permissions

from greed.framework import Greed, Context

class Counter(Cog):
    """
    Count up to a certain number in a channel.
    """
    def __init__(self, bot: Greed):
        self.bot = bot

    @group(
        name="counter",
        invoke_without_command=True,
    )
    async def counter(self, ctx: Context):
        """
        Base command for the counter.
        """
        return await ctx.send_help(ctx.command.qualified_name)

    @counter.command(name="enable")
    @has_permissions(manage_channels=True)
    async def counter_enable(
        self, 
        ctx: Context, 
        channel: TextChannel
    ):
        """
        Enable the counter in a specific channel.
        """
        row = await self.bot.db.fetchrow(
            """
            SELECT current_count FROM counter_channels 
            WHERE channel_id = $1
            """,
            channel.id,
        )

        if row:
            return await ctx.embed(
                message=f"{channel.mention} is already enabled for the counter!",
                message_type="warned")

        await self.bot.db.execute(
            """
            INSERT INTO counter_channels (channel_id, current_count) 
            VALUES ($1, $2)
            """,
            channel.id,
            1,
        )
        await ctx.embed(
            message=f"Counter enabled in {channel.mention}",
            message_type="approved",
        )

        message = await channel.send("1")
        await message.add_reaction("✅")

    @counter.command(name="disable")
    @has_permissions(manage_channels=True)
    async def counter_disable(
        self, 
        ctx: Context, 
        channel: TextChannel
    ):
        """
        Disable the counter in a specific channel.
        """
        row = await self.bot.db.fetchrow(
            """
            SELECT current_count FROM counter_channels 
            WHERE channel_id = $1
            """,
            channel.id,
        )
        if not row:
            return await ctx.embed(
                f"{channel.mention} is not an active counter channel!",
                message_type="warned"
            )
        
        await self.bot.db.execute(
            """
            DELETE FROM counter_channels 
            WHERE channel_id = $1
            """, 
            channel.id
        )
        await ctx.embed(
            message=f"Counter has been disabled in {channel.mention}",
            message_type="approved"
        )

async def setup(bot: Greed):
    await bot.add_cog(Counter(bot))