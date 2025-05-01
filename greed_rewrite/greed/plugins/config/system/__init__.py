from __future__ import annotations

from discord import Message, TextChannel
from discord.ext.commands import group, Cog, has_permissions

from greed.framework import Context, Greed
from greed.framework.script import Script


class System(Cog):
    """
    Customize welcome, boost, and leave messages for the server.
    """

    def __init__(self, bot: Greed):
        self.bot = bot

    @group(
        name="welcome",
        aliases=["welc"],
        invoke_without_command=True,
        with_app_command=True,
        brief="Welcome configurations for the server",
        example=",welcome",
    )
    @has_permissions(manage_channels=True)
    async def welcome(self, ctx: Context) -> Message:
        if ctx.subcommand_passed is not None:
            return
        return await ctx.send_help(ctx.command.qualified_name)

    @welcome.command(
        name="setup",
        aliases=["make", "create"],
        brief="setup welcome settings",
        example=",welcome setup",
    )
    @has_permissions(manage_channels=True)
    async def welcome_create(self, ctx: Context) -> Message:
        if await self.bot.db.fetchrow(
            "SELECT * FROM welcome WHERE guild_id = $1", ctx.guild.id
        ):
            return await ctx.embed(
                "**Welcome settings** have **already been configured** for this server",
                "approved",
            )

        await self.bot.db.execute(
            "INSERT INTO welcome (guild_id, channel_id, message) VALUES ($1, $2, $3)",
            ctx.guild.id,
            ctx.channel.id,
            "welcome {user}",
        )
        self.bot.cache.welcome[ctx.guild.id] = {
            "channel": ctx.channel.id,
            "message": "welcome {user}",
        }
        await ctx.embed("**Configured the welcome** for this server", "approved")

    @welcome.command(
        name="channel",
        aliases=["chan"],
        brief="Set the welcome channel",
        example=",welcome channel #welcomechannel",
    )
    @has_permissions(manage_channels=True)
    async def welcome_channel(self, ctx: Context, channel: TextChannel) -> Message:
        if not (
            await self.bot.db.fetchrow(
                "SELECT * FROM welcome WHERE guild_id = $1", ctx.guild.id
            )
        ):
            return await ctx.embed(
                f"Welcome settings have **not** been configured yet. Use `{ctx.prefix}welcome setup` first",
                "warned",
            )
        if self.bot.cache.welcome.get(ctx.guild.id):
            self.bot.cache.welcome[ctx.guild.id]["channel"] = channel.id
        else:
            self.bot.cache.welcome[ctx.guild.id] = {"channel": channel.id}
        await self.bot.db.execute(
            "UPDATE welcome SET channel_id = $1 WHERE guild_id = $2",
            channel.id,
            ctx.guild.id,
        )
        await ctx.embed(
            f"**Welcome channel** has been **set** to {channel.mention}", "approved"
        )

    @welcome.command(
        name="reset",
        aliases=["remove", "delete", "off"],
        brief="Clear welcome settings",
        example=",welcome reset",
    )
    @has_permissions(manage_channels=True)
    async def welcome_delete(self, ctx: Context) -> Message:
        if not (
            await self.bot.db.fetchrow(
                "SELECT * FROM welcome WHERE guild_id = $1", ctx.guild.id
            )
        ):
            return await ctx.embed(
                f"Welcome settings have **not** been configured yet. Use `{ctx.prefix}welcome setup` first",
                "warned",
            )
        self.bot.cache.welcome.pop(ctx.guild.id)
        await self.bot.db.execute(
            "DELETE FROM welcome WHERE guild_id = $1", ctx.guild.id
        )
        await ctx.embed("**Deleted the welcome** for this server", "approved")

    @welcome.command(
        name="view",
        brief="View your current welcome embed code",
        example=",welcome view",
    )
    @has_permissions(manage_channels=True)
    async def welcome_view(self, ctx: Context):
        if not (
            data := await self.bot.db.fetchrow(
                "SELECT * FROM welcome WHERE guild_id = $1", ctx.guild.id
            )
        ):
            return await ctx.embed(
                f"Welcome settings have **not** been configured yet. Use `{ctx.prefix}welcome setup` first",
                "warned",
            )
        return await ctx.send(f"```{data['message']}```")

    @welcome.command(
        name="message",
        aliases=["msg"],
        brief="Set the welcome message",
        example=",welcome message wsp {user}",
    )
    @has_permissions(manage_channels=True)
    async def welcome_message(self, ctx: Context, *, message: str) -> Message:
        if not (
            await self.bot.db.fetchrow(
                "SELECT * FROM welcome WHERE guild_id = $1", ctx.guild.id
            )
        ):
            return await ctx.embed(
                f"Welcome settings have **not** been configured yet. Use `{ctx.prefix}welcome setup` first",
                "warned",
            )
        script = Script(message, [ctx.guild, ctx.channel, ctx.author])
        await script.send(ctx.channel)
        self.bot.cache.welcome[ctx.guild.id]["message"] = message
        await self.bot.db.execute(
            "UPDATE welcome SET message = $1 WHERE guild_id = $2",
            message,
            ctx.guild.id,
        )
        await ctx.embed(f"Welcome message has been **set** to `{message}`", "approved")

    @welcome.command(
        name="test",
        aliases=["trial"],
        brief="Test the welcome message",
        example=",welcome test",
    )
    @has_permissions(manage_channels=True)
    async def welcome_test(self, ctx: Context) -> Message:
        self.bot.dispatch("member_join", ctx.author)
        await ctx.embed("**Welcome message** was sent", "approved")

    @group(
        name="leave",
        aliases=["goodbye"],
        invoke_without_command=True,
        brief="Manage leave messages for when a user leaves the guild",
        example=",leave",
    )
    @has_permissions(manage_channels=True)
    async def leave(self, ctx: Context) -> Message:
        if ctx.subcommand_passed is not None:
            return
        return await ctx.send_help(ctx.command.qualified_name)

    @leave.command(
        name="channel",
        aliases=["chan"],
        brief="Set the leave channel",
        example=",leave channel #goodbye",
    )
    @has_permissions(manage_channels=True)
    async def leave_channel(self, ctx: Context, channel: TextChannel) -> Message:
        if not (
            await self.bot.db.fetchrow(
                "SELECT * FROM leave WHERE guild_id = $1", ctx.guild.id
            )
        ):
            return await ctx.embed(
                f"**Leave settings** have **not** been configured yet. Use `{ctx.prefix}leave setup` first",
                "approved",
            )

        await self.bot.db.execute(
            "UPDATE leave SET channel_id = $1 WHERE guild_id = $2",
            channel.id,
            ctx.guild.id,
        )
        self.bot.cache.leave[ctx.guild.id]["channel"] = channel.id
        await ctx.embed(
            f"Leave channel has been **set** to {channel.mention}", "approved"
        )

    @leave.command(name="view", brief="view your current leave embed code")
    @has_permissions(manage_channels=True)
    async def leave_view(self, ctx: Context):
        if not (
            data := await self.bot.db.fetchrow(
                "SELECT * FROM leave WHERE guild_id = $1", ctx.guild.id
            )
        ):
            return await ctx.embed(
                f"**Leave settings** have **not** been configured yet. Use `{ctx.prefix}leave setup` first",
                "approved",
            )
        return await ctx.send(f"```{data['message']}```")

    @leave.command(
        name="setup",
        aliases=["enable", "on"],
        brief="Configure leave settings",
        example=",leave setup",
    )
    @has_permissions(manage_channels=True)
    async def leave_create(self, ctx: Context) -> Message:
        if await self.bot.db.fetchrow(
            "SELECT * FROM leave WHERE guild_id = $1", ctx.guild.id
        ):
            return await ctx.embed(
                "**Leave settings** have **already** been configured for this server",
                "approved",
            )

        await self.bot.db.execute(
            "INSERT INTO leave (guild_id, channel_id, message) VALUES ($1, $2, $3)",
            ctx.guild.id,
            ctx.channel.id,
            "leave {user}",
        )
        self.bot.cache.leave[ctx.guild.id] = {
            "channel": ctx.channel.id,
            "message": "leave {user}",
        }
        await ctx.embed(
            "**Leave settings** have **been configured** for this server", "approved"
        )

    @leave.command(
        name="reset",
        aliases=["remove", "delete"],
        brief="Clear leave settings",
        example=",leave reset",
    )
    @has_permissions(manage_channels=True)
    async def leave_delete(self, ctx: Context) -> Message:
        if not (
            await self.bot.db.fetchrow(
                "SELECT * FROM leave WHERE guild_id = $1", ctx.guild.id
            )
        ):
            return await ctx.embed(
                f"**Leave settings** have **not** been configured yet. Use `{ctx.prefix}leave setup` first",
                "approved",
            )

        await self.bot.db.execute("DELETE FROM leave WHERE guild_id = $1", ctx.guild.id)
        self.bot.cache.leave.pop(ctx.guild.id)
        await ctx.embed("**Deleted** the leave settings", "approved")

    @leave.command(
        name="message",
        aliases=["msg"],
        brief="Set the leave message",
        example=",leave message {embed_code}",
    )
    @has_permissions(manage_channels=True)
    async def leave_message(self, ctx: Context, *, message: str) -> Message:
        if not (
            await self.bot.db.fetchrow(
                "SELECT * FROM leave WHERE guild_id = $1", ctx.guild.id
            )
        ):
            return await ctx.embed(
                f"**Leave settings** have **not** been configured yet. Use `{ctx.prefix}leave setup` first",
                "approved",
            )
        script = Script(message, [ctx.guild, ctx.channel, ctx.author])
        await script.send(ctx.channel)
        self.bot.cache.leave[ctx.guild.id]["message"] = message
        await self.bot.db.execute(
            "UPDATE leave SET message = $1 WHERE guild_id = $2",
            message,
            ctx.guild.id,
        )
        await ctx.embed(
            f"**Leave message** has been **set** to `{message}`", "approved"
        )

    @leave.command(
        name="test",
        aliases=["trial"],
        brief="Test the leave message",
        example=",leave test",
    )
    @has_permissions(manage_channels=True)
    async def leave_test(self, ctx: Context) -> Message:
        self.bot.dispatch("member_remove", ctx.author)
        await ctx.embed("**Leave message** has been sent", "approved")

    @group(
        name="boost",
        aliases=["bm", "boostmessage", "boostmsg"],
    )
    @has_permissions(manage_guild=True)
    async def boost(self, ctx: Context):
        """
        Configure boost messages.
        """
        return await ctx.send_help(ctx.command)

    @boost.command(
        name="setup",
        aliases=(
            "on",
            "enable",
        ),
    )
    @has_permissions(manage_guild=True)
    async def boost_enable(self, ctx: Context) -> Message:
        """
        Enable boost messages for the guild.
        """
        if await self.bot.db.fetchrow(
            """
            SELECT * FROM guild.boost 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        ):
            return await ctx.embed(
                message="Boost messages are already enabled!", message_type="warned"
            )

        await self.bot.db.execute(
            """
            INSERT INTO guild.boost (guild_id, channel_id, message) 
            VALUES ($1, $2, $3)
            """,
            ctx.guild.id,
            ctx.channel.id,
            "Thank you for boosting the server, {user.mention}!",
        )
        return await ctx.embed(
            message="Enabled boost messages", message_type="approved"
        )

    @boost.command(
        name="reset",
        aliases=(
            "off",
            "disable",
        ),
    )
    @has_permissions(manage_guild=True)
    async def boostmsg_disable(self, ctx: Context) -> Message:
        """
        Disable boost messages for the guild.
        """
        if not await self.bot.db.fetchrow(
            """
            SELECT * FROM guild.boost 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        ):
            return await ctx.embed(
                message="Boost messages are already disabled!", message_type="warned"
            )

        await self.bot.db.execute(
            """
            DELETE FROM guild.boost 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )
        return await ctx.embed(
            message="Disabled boost messages", message_type="approved"
        )

    @boost.command(
        name="channel",
        aliases=("chan",),
    )
    @has_permissions(manage_guild=True)
    async def boostmsg_channel(self, ctx: Context, channel: TextChannel) -> Message:
        """
        Assign a channel for boost messages to be sent in.
        """
        if not await self.bot.db.fetchrow(
            """
            SELECT * FROM guild.boost 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        ):
            return await ctx.embed(
                message="Boost messages are not enabled!", message_type="warned"
            )

        await self.bot.db.execute(
            """
            UPDATE guild.boost SET channel_id = $1 
            WHERE guild_id = $2
            """,
            channel.id,
            ctx.guild.id,
        )
        return await ctx.embed(
            message=f"**Boost message channel** set to {channel.mention}",
            message_type="approved",
        )

    @boost.command(
        name="message",
        aliases=("msg",),
    )
    @has_permissions(manage_guild=True)
    async def boostmsg_message(self, ctx: Context, *, message: str) -> Message:
        """
        Set the message to be sent when someone boosts the guild.
        """
        if not await self.bot.db.fetchrow(
            """
            SELECT * FROM guild.boost 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        ):
            return await ctx.embed(
                message="Boost messages are not enabled!", message_type="warned"
            )

        await self.bot.send_embed(ctx.channel, message, user=ctx.author)
        await self.bot.db.execute(
            """
            UPDATE guild.boost SET message = $1 
            WHERE guild_id = $2
            """,
            message,
            ctx.guild.id,
        )
        return await ctx.embed(
            message=f"Boost message set to ``{message}``", message_type="approved"
        )

    @boost.command(name="view")
    @has_permissions(manage_guild=True)
    async def boost_view(self, ctx: Context):
        """
        View the current boost message.
        """
        if not (
            message := await self.bot.db.fetchrow(
                """
                SELECT message 
                FROM guild.boost 
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
        ):
            return await ctx.embed(
                message="Boost messages are not enabled!", message_type="warned"
            )

        return await ctx.embed(message=f"```{message}```", message_type="neutral")

    @boost.command(name="test")
    @has_permissions(manage_guild=True)
    async def boostmsg_test(self, ctx: Context):
        """
        Test the boost message.
        """
        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT * FROM guild.boost 
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
        ):
            return await ctx.embed(
                message="Boost messages are not enabled!", message_type="warned"
            )

        channel = self.bot.get_channel(data["channel_id"])
        if not channel:
            return await ctx.embed(
                message="Boost message channel not found!", message_type="warned"
            )

        await self.bot.send_embed(channel, data["message"], user=ctx.author)
        return await ctx.embed(
            message=f"Boost message was sent to {channel.mention}",
            message_type="approved",
        )


async def setup(bot: Greed):
    await bot.add_cog(System(bot))
