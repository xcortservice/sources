from discord import Embed, Member, TextChannel, utils

from discord.ext.commands import Cog, command, group, has_permissions
from datetime import datetime, timedelta
import discord

from greed.framework import Context, Greed


class AntiRaid(Cog):
    def __init__(self, bot: Greed):
        self.bot = bot
        self.original_permissions = {}
        self.join_timestamps = {}

    async def get_server_settings(self, guild_id):
        """
        Fetch server settings for a specific guild.
        """
        settings = await self.bot.db.fetchrow(
            """
            SELECT antiraid_enabled, minimum_account_age, lockdown, default_pfp_check, log_channel_id, raid_punishment
            FROM server_settings
            WHERE guild_id = $1
            """,
            guild_id,
        )
        if not settings:
            await self.bot.db.execute(
                """
                INSERT INTO server_settings (guild_id) 
                VALUES ($1)
                """,
                guild_id,
            )
            return {
                "antiraid_enabled": False,
                "minimum_account_age": 7,
                "lockdown": False,
                "default_pfp_check": False,
                "log_channel_id": None,
                "raid_punishment": "ban",
            }

        return dict(settings)

    async def is_whitelisted(self, user_id):
        """
        Check if a user is whitelisted.
        """
        result = await self.bot.db.fetchrow(
            """
            SELECT 1 FROM whitelist 
            WHERE user_id = $1
            """,
            user_id,
        )
        return result is not None

    async def log_raid_activity(self, reason, member, guild):
        """
        Logs a failed raid activity to the logs.
        """
        embed = Embed(
            title="Raid Protection Alert",
            description=f"**Member:** {member.mention} ({member.id})\n"
            f"**Account Age:** {(datetime.utcnow() - member.created_at).days} days\n"
            f"**Reason:** {reason}",
            color=0xFF0000,
        )
        embed.set_thumbnail(
            url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        embed.timestamp = datetime.utcnow()

        settings = await self.get_server_settings(guild.id)
        log_channel_id = settings["log_channel_id"]

        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(embed=embed)
            else:
                await guild.system_channel.send(
                    f"Log channel with ID {log_channel_id} no longer exists."
                )
        else:
            log_channel = utils.get(guild.text_channels, name="raid-log")
            if log_channel:
                await log_channel.send(embed=embed)

    @group(name="antiraid", invoke_without_command=True)
    @has_permissions(administrator=True)
    async def antiraid(self, ctx: Context):
        """
        Anti-raid command group.
        """
        return await ctx.send_help(ctx.command)

    @antiraid.command(name="toggle")
    @has_permissions(administrator=True)
    async def toggle_antiraid(self, ctx: Context):
        """
        Toggle the anti-raid system on or off.
        """
        settings = await self.get_server_settings(ctx.guild.id)
        new_status = not settings["antiraid_enabled"]
        await self.bot.db.execute(
            """ 
            UPDATE server_settings
            SET antiraid_enabled = $1
            WHERE guild_id = $2 
            """,
            new_status,
            ctx.guild.id,
        )
        status_text = "enabled" if new_status else "disabled"
        await ctx.embed(
            message=f"Anti-raid system has been {status_text}", message_type="approved"
        )

    @antiraid.command(name="age", aliases=["minage"])
    @has_permissions(administrator=True)
    async def set_min_account_age(self, ctx: Context, days: int):
        """
        Set the minimum account age in days.
        """
        await self.bot.db.execute(
            """ 
            UPDATE server_settings
            SET minimum_account_age = $1
            WHERE guild_id = $2
            """,
            days,
            ctx.guild.id,
        )
        await ctx.embed(
            message=f"Minimum account age set to {days} days", message_type="approved"
        )

    # Conflicting command name, we edit later to antiraid lockdown -- adam
    # @command(name="lockdown")
    # @has_permissions(administrator=True)
    # async def toggle_lockdown(self, ctx: Context, status: str):
    #     """
    #     Enable or disable server lockdown (block all new joins).
    #     """
    #     if status.lower() not in ["on", "off"]:
    #         return await ctx.embed(
    #             message="Invalid status! Use `on` or `off`!", message_type="warned"
    #         )

    #     await self.bot.db.execute(
    #         """
    #         UPDATE server_settings
    #         SET lockdown = $1
    #         WHERE guild_id = $2
    #         """,
    #         status.lower() == "on",
    #         ctx.guild.id,
    #     )

    #     for channel in ctx.guild.text_channels:
    #         overwrites = channel.overwrites_for(ctx.guild.default_role)

    #         if status.lower() == "on":
    #             if channel.id not in self.original_permissions:
    #                 self.original_permissions[channel.id] = {
    #                     "send_messages": overwrites.send_messages,
    #                     "read_messages": overwrites.read_messages,
    #                     "add_reactions": overwrites.add_reactions,
    #                     "create_public_threads": overwrites.create_public_threads,
    #                     "create_private_threads": overwrites.create_private_threads,
    #                     "send_messages_in_threads": overwrites.send_messages_in_threads,
    #                 }
    #             await channel.set_permissions(
    #                 ctx.guild.default_role,
    #                 send_messages=False,
    #                 read_messages=True,
    #                 add_reactions=False,
    #                 create_public_threads=False,
    #                 create_private_threads=False,
    #                 send_messages_in_threads=False,
    #             )
    #         else:
    #             if channel.id in self.original_permissions:
    #                 original = self.original_permissions[channel.id]
    #                 await channel.set_permissions(
    #                     ctx.guild.default_role,
    #                     send_messages=original["send_messages"],
    #                     read_messages=original["read_messages"],
    #                     add_reactions=original["add_reactions"],
    #                     create_public_threads=original["create_public_threads"],
    #                     create_private_threads=original["create_private_threads"],
    #                     send_messages_in_threads=original["send_messages_in_threads"],
    #                 )
    #                 del self.original_permissions[channel.id]

    #     state = "locked down" if status.lower() == "on" else "lifted"
    #     await ctx.embed(
    #         message=f"Server is now {state}. New member joins are {'blocked' if status.lower() == 'on' else 'allowed'}",
    #         message_type="approved",
    #     )

    @antiraid.command(name="defaultpfp")
    @has_permissions(administrator=True)
    async def toggle_default_pfp(self, ctx: Context):
        """
        Toggle blocking users with default profile pictures.
        """
        settings = await self.get_server_settings(ctx.guild.id)
        new_status = not settings["default_pfp_check"]
        await self.bot.db.execute(
            """ 
            UPDATE server_settings
            SET default_pfp_check = $1
            WHERE guild_id = $2
            """,
            "on" if new_status else "off",
            ctx.guild.id,
        )
        status = "enabled" if new_status else "disabled"
        await ctx.embed(
            message=f"Default profile picture check has been {status}",
            message_type="approved",
        )

    @antiraid.command(name="punishment")
    @has_permissions(administrator=True)
    async def set_punishment(self, ctx: Context, punishment: str):
        """
        Set the punishment for raid attempts.
        """
        punishment = punishment.lower()
        valid_punishments = ["ban", "kick", "timeout", "jail"]

        if punishment not in valid_punishments:
            return await ctx.embed(
                message=f"Invalid punishment! Must be one of: {', '.join(valid_punishments)}",
                message_type="warned",
            )

        await self.bot.db.execute(
            """ 
            UPDATE server_settings
            SET raid_punishment = $1
            WHERE guild_id = $2
            """,
            punishment,
            ctx.guild.id,
        )

        await ctx.embed(
            message=f"Raid punishment has been set to **{punishment}**",
            message_type="approved",
        )

    @antiraid.command(name="status")
    async def status(self, ctx):
        """
        Check the current anti-raid system status.
        """
        settings = await self.get_server_settings(ctx.guild.id)

        embed = Embed(title="Anti-Raid Status")
        embed.add_field(
            name="Antiraid System",
            value=(
                "<:UB_Check_Icon:1306875712782864445>"
                if settings["antiraid_enabled"]
                else "<:UB_X_Icon:1306875714426900531>"
            ),
            inline=False,
        )

        embed.add_field(
            name="Lockdown",
            value=(
                "<:UB_Check_Icon:1306875712782864445>"
                if settings["lockdown"]
                else "<:UB_X_Icon:1306875714426900531>"
            ),
            inline=False,
        )

        embed.add_field(
            name="Minimum Account Age",
            value=f"{settings['minimum_account_age']} days",
            inline=False,
        )

        embed.add_field(
            name="Default PFP Check",
            value=(
                "<:UB_Check_Icon:1306875712782864445>"
                if settings["default_pfp_check"]
                else "<:UB_X_Icon:1306875714426900531>"
            ),
            inline=False,
        )

        embed.add_field(
            name="Log Channel",
            value=(
                f"<#{settings['log_channel_id']}>"
                if settings["log_channel_id"]
                else "<:UB_X_Icon:1306875714426900531>"
            ),
            inline=False,
        )

        embed.add_field(
            name="Raid Punishment",
            value=settings.get("raid_punishment", "ban").title(),
            inline=False,
        )

        embed.set_footer(text="Use the antiraid commands to adjust settings.")
        await ctx.send(embed=embed)

    @antiraid.command(name="setlogchannel")
    @has_permissions(administrator=True)
    async def set_log_channel(self, ctx: Context, channel: TextChannel = None):
        """
        Sets the channel for raid activity logs.
        """
        await self.bot.db.execute(
            """
            INSERT INTO server_settings (guild_id, log_channel_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET log_channel_id = $2
            """,
            ctx.guild.id,
            channel.id,
        )

        return await ctx.embed(
            message=f"Raid log channel has been set to {channel.mention}.",
            message_type="approved",
        )

    @Cog.listener()
    async def on_member_join(self, member):
        """
        Listen for new member joins and apply anti-raid checks.
        """
        settings = await self.get_server_settings(member.guild.id)
        if not settings["antiraid_enabled"]:
            return

        if await self.is_whitelisted(member.id):
            return

        if member.guild.id not in self.join_timestamps:
            self.join_timestamps[member.guild.id] = []

        current_time = datetime.utcnow()
        self.join_timestamps[member.guild.id].append(current_time)

        self.join_timestamps[member.guild.id] = [
            t
            for t in self.join_timestamps[member.guild.id]
            if (current_time - t).total_seconds() <= 60
        ]

        if len(self.join_timestamps[member.guild.id]) > 5:
            await self.toggle_lockdown(member.guild, "on")
            await self.log_raid_activity(
                "Mass join detected, enabled lockdown", member, member.guild
            )
            return

        if settings["lockdown"]:
            await self.handle_lockdown(member)
            return

        if settings["default_pfp_check"] and not member.avatar:
            await self.handle_default_pfp_check(member)
            return

        member_created_naive = member.created_at.replace(tzinfo=None)
        account_age = (datetime.utcnow() - member_created_naive).days
        if account_age < settings["minimum_account_age"]:
            await self.handle_account_age(
                member, account_age, settings["minimum_account_age"]
            )

    async def handle_lockdown(self, member: Member):
        """
        Handles the lockdown case.
        """
        await member.send(
            embed=Embed(
                title="Server Lockdown",
                description="The server is currently in lockdown. Please try again later.",
            )
        )
        await self.handle_raid_punishment(member, "Server lockdown in effect")
        await self.log_raid_activity("Lockdown", member, member.guild)

    async def handle_default_pfp_check(self, member: Member):
        """
        Handles default profile picture check.
        """
        await member.send(
            embed=Embed(
                title="Default Profile Picture Detected",
                description="Please change your profile picture to join this server.",
            )
        )
        await self.handle_raid_punishment(member, "Default profile picture detected")
        await self.log_raid_activity("Default PFP detected", member, member.guild)

    async def handle_account_age(self, member: Member, account_age: int, min_age: int):
        """
        Handles account age below the minimum required.
        """
        await member.send(
            embed=Embed(
                title="Account Age Check",
                description=(
                    f"Your account is too new to join this server. "
                    f"Minimum required age is {min_age} days, but yours is {account_age} days."
                ),
            )
        )
        await self.handle_raid_punishment(
            member, f"Account age ({account_age} days) below required {min_age}"
        )
        await self.log_raid_activity(
            f"Account age ({account_age} days) below required {min_age}",
            member,
            member.guild,
        )

    async def handle_raid_punishment(self, member: Member, reason: str):
        """
        Handle the punishment for a raid attempt.
        """
        settings = await self.get_server_settings(member.guild.id)
        punishment = settings.get("raid_punishment", "ban")

        try:
            if punishment == "ban":
                if not member.guild.me.guild_permissions.ban_members:
                    await self.log_raid_activity(
                        f"Failed to ban {member}: Missing permissions",
                        member,
                        member.guild,
                    )
                    return
                await member.guild.ban(member, reason=f"Anti-raid: {reason}")

            elif punishment == "kick":
                if not member.guild.me.guild_permissions.kick_members:
                    await self.log_raid_activity(
                        f"Failed to kick {member}: Missing permissions",
                        member,
                        member.guild,
                    )
                    return
                await member.guild.kick(member, reason=f"Anti-raid: {reason}")

            elif punishment == "timeout":
                if not member.guild.me.guild_permissions.moderate_members:
                    await self.log_raid_activity(
                        f"Failed to timeout {member}: Missing permissions",
                        member,
                        member.guild,
                    )
                    return
                await member.timeout(timedelta(hours=1), reason=f"Anti-raid: {reason}")

            else:
                await member.guild.ban(member, reason=f"Anti-raid: {reason}")

        except discord.Forbidden:
            await self.log_raid_activity(
                f"Failed to punish {member}: Forbidden", member, member.guild
            )
        except discord.HTTPException as e:
            await self.log_raid_activity(
                f"Failed to punish {member}: {str(e)}", member, member.guild
            )


async def setup(bot: Greed):
    await bot.add_cog(AntiRaid(bot))
