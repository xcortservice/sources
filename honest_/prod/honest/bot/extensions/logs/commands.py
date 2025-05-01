from typing import Optional

from discord import (Client, Embed, File, Guild, Member, TextChannel, Thread,
                     User)
from discord.ext.commands import (Cog, CommandError, command, group,
                                  has_permissions, hybrid_group)
from system.patch.context import Context


class Logs(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @hybrid_group(invoke_without_command=True)
    async def logs(self, ctx: Context):
        """
        Track events happening in your server
        """

        return await ctx.send_help(ctx.command)

    @logs.command(name="settings")
    @has_permissions(manage_guild=True)
    async def logs_settings(self, ctx: Context):
        """
        Check the logs feature settings in this server
        """

        results = await self.bot.db.fetch(
            "SELECT * FROM logs WHERE guild_id = $1", ctx.guild.id
        )

        if not results:
            raise CommandError("There are no logs configured in this server")

        embed = Embed(
            title="Logs settings",
            description="\n".join(
                [f"{result.log_type}: <#{result.channel_id}>" for result in results]
            ),
        ).set_author(name=ctx.guild.name, icon_url=ctx.guild.icon)
        return await ctx.reply(embed=embed)

    @logs.command(name="members")
    @has_permissions(manage_guild=True)
    async def logs_members(
        self, ctx: Context, *, channel: Optional[TextChannel] = None
    ):
        """
        Track member related events happening in the server
        """

        if not channel:
            r = await self.bot.db.execute(
                """
                DELETE FROM logs WHERE
                guild_id = $1 AND
                log_type = $2 
                """,
                ctx.guild.id,
                "members",
            )

            if r == "DELETE 0":
                raise CommandError("Member logs weren't enabled")

            return await ctx.success("Disabled member logging")

        await self.bot.db.execute(
            """
            INSERT INTO logs VALUES ($1,$2,$3)
            ON CONFLICT (guild_id, log_type)
            DO UPDATE SET channel_id = $3   
            """,
            ctx.guild.id,
            "members",
            channel.id,
        )

        return await ctx.success(f"Sending member related logs to {channel.mention}")

    @logs.command(name="channel")
    @has_permissions(manage_guild=True)
    async def logs_channel(
        self, ctx: Context, *, channel: Optional[TextChannel] = None
    ):
        """
        Track channel related events happening in the server
        """

        if not channel:
            r = await self.bot.db.execute(
                """
                DELETE FROM logs WHERE
                guild_id = $1 AND
                log_type = $2 
                """,
                ctx.guild.id,
                "channels",
            )

            if r == "DELETE 0":
                raise CommandError("Channel logs weren't enabled")

            return await ctx.success("Disabled channel logging")

        await self.bot.db.execute(
            """
            INSERT INTO logs VALUES ($1,$2,$3)
            ON CONFLICT (guild_id, log_type)
            DO UPDATE SET channel_id = $3   
            """,
            ctx.guild.id,
            "channels",
            channel.id,
        )

        return await ctx.success(f"Sending channel related logs to {channel.mention}")

    @logs.command(name="role")
    @has_permissions(manage_guild=True)
    async def logs_role(self, ctx: Context, *, channel: Optional[TextChannel] = None):
        """
        Track role related events happening in the server
        """

        if not channel:
            r = await self.bot.db.execute(
                """
                DELETE FROM logs WHERE
                guild_id = $1 AND
                log_type = $2 
                """,
                ctx.guild.id,
                "roles",
            )

            if r == "DELETE 0":
                raise CommandError("Role logs weren't enabled")

            return await ctx.success("Disabled role logging")

        await self.bot.db.execute(
            """
            INSERT INTO logs VALUES ($1,$2,$3)
            ON CONFLICT (guild_id, log_type)
            DO UPDATE SET channel_id = $3   
            """,
            ctx.guild.id,
            "roles",
            channel.id,
        )

        return await ctx.success(f"Sending role related logs to {channel.mention}")

    @logs.command(name="automod")
    @has_permissions(manage_guild=True)
    async def logs_automod(
        self, ctx: Context, *, channel: Optional[TextChannel] = None
    ):
        """
        Track automod related events happening in the server
        """

        if not channel:
            r = await self.bot.db.execute(
                """
                DELETE FROM logs WHERE
                guild_id = $1 AND
                log_type = $2 
                """,
                ctx.guild.id,
                "automod",
            )

            if r == "DELETE 0":
                raise CommandError("Automod logs weren't enabled")

            return await ctx.success("Disabled automod logging")

        await self.bot.db.execute(
            """
            INSERT INTO logs VALUES ($1,$2,$3)
            ON CONFLICT (guild_id, log_type)
            DO UPDATE SET channel_id = $3   
            """,
            ctx.guild.id,
            "automod",
            channel.id,
        )

        return await ctx.success(f"Sending automod related logs to {channel.mention}")

    @logs.command(name="message")
    @has_permissions(manage_guild=True)
    async def logs_message(
        self, ctx: Context, *, channel: Optional[TextChannel] = None
    ):
        """
        Track message related events happening in the server
        """

        if not channel:
            r = await self.bot.db.execute(
                """
                DELETE FROM logs WHERE
                guild_id = $1 AND
                log_type = $2 
                """,
                ctx.guild.id,
                "messages",
            )

            if r == "DELETE 0":
                raise CommandError("Message logs weren't enabled")

            return await ctx.success("Disabled message logging")

        await self.bot.db.execute(
            """
            INSERT INTO logs VALUES ($1,$2,$3)
            ON CONFLICT (guild_id, log_type)
            DO UPDATE SET channel_id = $3   
            """,
            ctx.guild.id,
            "messages",
            channel.id,
        )

        return await ctx.success(f"Sending message related logs to {channel.mention}")


async def setup(bot: Client):
    await bot.add_cog(Logs(bot))
