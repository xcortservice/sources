from datetime import datetime, timedelta
from typing import Literal, Optional, Union

import humanize
from data.config import CONFIG
from data.variables import PERMISSION_LIST
from discord import (AutoModRuleAction, AutoModRuleEventType,
                     AutoModRuleTriggerType, AutoModTrigger, Client, File,
                     Guild, Member, Message, Role, TextChannel, Thread, User,
                     utils)
from discord.embeds import Embed, EmbedProxy
from discord.ext.commands import (Boolean, Cog, CommandConverter, CommandError,
                                  EmbedConverter, Expiration, FakePermission,
                                  RoleConverter, SafeRoleConverter, Timeframe,
                                  command, group, has_permissions,
                                  hybrid_group)
from system.classes.builtins import boolean_to_emoji
from system.classes.database import Record
from system.patch.context import Context


class SafeRole(RoleConverter):
    async def convert(self, ctx: Context, argument: str):
        try:
            role = await super().convert(ctx, argument)
        except Exception as e:
            raise e
        roles = [r for r in ctx.guild.roles][::-1]
        role_index = roles.index(role)
        author_index = roles.index(ctx.author.top_role)
        if role_index < author_index:
            raise CommandError(f"{role.mention} is higher than your top role")
        return role


class Configuration(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.link_regex = r"(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])"

    def transfer_boolean(self, boolean: bool):
        if boolean:
            return CONFIG["emojis"]["success"]
        else:
            return CONFIG["emojis"]["fail"]

    @group(
        name="prefix",
        description="change the prefix for the bot",
        invoke_without_command=True,
    )
    async def prefix(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @prefix.command(
        name="set",
        description="set the prefix that is used for bot commands",
        example=",prefix set ;",
    )
    @has_permissions(manage_messages=True)
    async def prefix_set(self, ctx: Context, setting: str):
        if len(setting) > 3:
            raise CommandError("prefix can't be more than 3 characters")
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, prefix) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix""",
            ctx.guild.id,
            setting,
        )
        return await ctx.success(f"set the **prefix** to `{setting}`")

    @prefix.command(
        name="self",
        description="set your prefix for bot commands",
        example=",prefix self ;",
    )
    async def prefix_self(self, ctx: Context, setting: str):
        if setting.lower() in ("none", "clear", "remove"):
            try:
                await self.bot.db.execute(
                    """UPDATE user_config SET prefix = NULL WHERE user_id = $1""",
                    ctx.author.id,
                )
            except Exception:
                raise CommandError("you haven't set your self prefix")
            return await ctx.success("successfully **removed** your **self prefix**")
        if len(setting) > 3:
            raise CommandError("prefix can't be more than 3 characters")
        await self.bot.db.execute(
            """INSERT INTO user_config (user_id, prefix) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET prefix = excluded.prefix""",
            ctx.author.id,
            setting,
        )
        return await ctx.success(f"set the **prefix** to `{setting}`")

    @group(
        name="alias",
        description="Add custom aliases to commands",
        example=",alias add hi avatar",
        aliases=["aliases"],
        invoke_without_command=True,
    )
    async def alias(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @alias.command(
        name="add",
        description="Create an alias for command",
        example=",alias add hi avatar",
    )
    @has_permissions(manage_messages=True)
    async def alias_add(
        self, ctx: Context, shortcut: str, *, _command: CommandConverter
    ):
        await self.bot.db.execute(
            """INSERT INTO aliases (guild_id, alias, command_name) VALUES($1, $2, $3) ON CONFLICT(guild_id, alias) DO UPDATE SET command_name = excluded.command_name""",
            ctx.guild.id,
            shortcut,
            _command.qualified_name,
        )
        return await ctx.success(
            f"Added alias `{shortcut}` for command `{_command.qualified_name}`"
        )

    @alias.command(
        name="remove",
        description="Remove an alias for command",
        example=",alias remove hi",
    )
    @has_permissions(manage_messages=True)
    async def alias_remove(self, ctx: Context, shortcut: str):
        check = await self.bot.db.execute(
            """DELETE FROM aliases WHERE guild_id = $1 AND alias = $2""",
            ctx.guild.id,
            shortcut,
        )
        if check == "DELETE 0":
            raise CommandError(f"There is no alias under `{shortcut}`")
        return await ctx.success(f"Removed alias `{shortcut}`")

    @alias.command(
        name="list",
        description="List every alias for all commands",
        aliases=["ls", "l", "show", "view"],
    )
    @has_permissions(manage_messages=True)
    async def alias_list(self, ctx: Context):
        aliases = await self.bot.db.fetch(
            """SELECT alias, command_name FROM aliases WHERE guild_id = $1""",
            ctx.guild.id,
        )
        if not aliases:
            raise CommandError("No aliases found")
        embed = Embed(title="Aliases", color=ctx.author.color)
        rows = [
            f"`{i}` {row.alias} - **{row.command_name}**"
            for i, row in enumerate(aliases, start=1)
        ]
        return await ctx.paginate(embed, rows)

    @group(
        name="antispam",
        description="filter spam and protect your chat",
        invoke_without_command=True,
    )
    async def antispam(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @antispam.group(
        name="flooding",
        aliases=["flood", "fl", "largetext"],
        description="configure filtering for large text bodies",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def antispam_flooding(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @antispam_flooding.command(
        name="toggle",
        description="toggle chat flood filtering",
        example=",antispam flooding toggle yes",
    )
    @has_permissions(manage_guild=True)
    async def antispam_flooding_toggle(self, ctx: Context, *, state: Boolean):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, flood_status) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET flood_status = excluded.flood_status""",
            ctx.guild.id,
            state,
        )
        return await ctx.success(
            f"chat flood filtering is now **{'ON' if state else 'OFF'}**"
        )

    @antispam_flooding.command(
        name="threshold",
        description="change the character threshold for flooding detection",
        example=",antispam flooding threshold 300",
    )
    @has_permissions(manage_guild=True)
    async def antispam_flooding_threshold(self, ctx: Context, *, setting: int):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, flood_threshold) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET flood_threshold = excluded.flood_threshold""",
            ctx.guild.id,
            setting,
        )
        return await ctx.success(f"the chat flooding threshold is now **{setting}**")

    @antispam.group(
        name="spam",
        description="configure repeated message filtering",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def antispam_spam(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @antispam_spam.command(
        name="toggle",
        description="toggle repeated message filtering",
        example=",antispam spam toggle yes",
    )
    @has_permissions(manage_guild=True)
    async def antispam_spam_toggle(self, ctx: Context, *, state: Boolean):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, status) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET status = excluded.status""",
            ctx.guild.id,
            state,
        )
        return await ctx.success(
            f"chat flood filtering is now **{'ON' if state else 'OFF'}**"
        )

    @antispam_spam.command(
        name="threshold",
        description="change the message threshold for spam detection",
        example=",antispam spam threshold 5",
    )
    @has_permissions(manage_guild=True)
    async def antispam_spam_threshold(self, ctx: Context, *, setting: int):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, threshold) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET threshold = excluded.threshold""",
            ctx.guild.id,
            setting,
        )
        return await ctx.success(f"the chat spamming threshold is now **{setting}**")

    @antispam.group(
        name="ladder",
        aliases=["laddertype", "lt", "laddering"],
        description="configure filtering for large text bodies",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def antispam_ladder(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @antispam_ladder.command(
        name="toggle",
        description="toggle ladder typing filtering",
        example=",antispam ladder toggle yes",
    )
    @has_permissions(manage_guild=True)
    async def antispam_ladder_toggle(self, ctx: Context, *, state: Boolean):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, ladder_status) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET ladder_status = excluded.ladder_status""",
            ctx.guild.id,
            state,
        )
        return await ctx.success(
            f"chat ladder typing filtering is now **{'ON' if state else 'OFF'}**"
        )

    @antispam_ladder.command(
        name="threshold",
        description="change the character threshold for flooding detection",
        example=",antispam ladder threshold 10",
    )
    @has_permissions(manage_guild=True)
    async def antispam_ladder_threshold(self, ctx: Context, *, setting: int):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, ladder_threshold) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET ladder_threshold = excluded.ladder_threshold""",
            ctx.guild.id,
            setting,
        )
        return await ctx.success(f"the ladder typing threshold is now **{setting}**")

    @antispam.command(
        name="timeout",
        description="set the timeout timeframe for spammers",
        example=",antispam timeout 10s",
    )
    @has_permissions(manage_guild=True)
    async def antispam_timeout(self, ctx: Context, timeframe: Timeframe):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, timeout) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET timeout = excluded.timeout""",
            ctx.guild.id,
            timeframe,
        )
        return await ctx.success(
            f"Successfully set the **timeout** for **antispam** to `{timeframe} seconds`"
        )

    @antispam.command(
        name="enable", aliases=["on", "true"], description="turn on anti spam"
    )
    @has_permissions(manage_guild=True)
    async def antispam_enable(self, ctx: Context):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, status, ladder_status, flood_status) VALUES($1, $2, $3, $4) ON CONFLICT(guild_id) DO UPDATE SET status = excluded.status, ladder_status = excluded.ladder_status, flood_status = excluded.flood_status""",
            ctx.guild.id,
            True,
            True,
            True,
        )
        return await ctx.success("successfully **ENABLED** anti spam")

    @antispam.command(
        name="disable", aliases=["off", "false"], description="turn off anti spam"
    )
    @has_permissions(manage_guild=True)
    async def antispam_disable(self, ctx: Context):
        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, status, ladder_status, flood_status) VALUES($1, $2, $3, $4) ON CONFLICT(guild_id) DO UPDATE SET status = excluded.status, ladder_status = excluded.ladder_status, flood_status = excluded.flood_status""",
            ctx.guild.id,
            False,
            False,
            False,
        )
        return await ctx.success("successfully **DISABLED** anti spam")

    @antispam.command(
        name="whitelist",
        description="whitelist or unwhitelist a user from antispam",
        example=",antispam whitelist @aiohttp",
    )
    @has_permissions(manage_guild=True)
    async def antispam_whitelist(
        self, ctx: Context, *, snowflake: Union[User, Member, TextChannel, Role]
    ):
        whitelisted = await self.bot.db.fetchval(
            """SELECT whitelisted FROM antispam WHERE guild_id = $1""", ctx.guild.id
        )

        if not whitelisted:
            whitelisted = []

        if snowflake.id not in whitelisted:
            whitelisted.append(snowflake.id)
            message = "whitelisted"

        else:
            whitelisted.remove(snowflake.id)
            message = "unwhitelisted"

        await self.bot.db.execute(
            """INSERT INTO antispam (guild_id, whitelisted) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET whitelisted = excluded.whitelisted""",
            ctx.guild.id,
            whitelisted,
        )
        return await ctx.success(f"successfully **{message}** {snowflake.mention}")

    @antispam.command(
        name="whitelisted", description="view members whitelisted from anti spam"
    )
    @has_permissions(manage_guild=True)
    async def antispam_whitelisted(self, ctx: Context):
        if not (
            whitelisted := await self.bot.db.fetchval(
                """SELECT whitelisted FROM antispam WHERE guild_id = $1""", ctx.guild.id
            )
        ):
            raise CommandError("there are no whitelisted users here")

        def get_user(user_id: int):
            if role := ctx.guild.get_role(user_id):
                return f"**{role.mention}** (`{user_id}`)"
            elif channel := ctx.guild.get_channel(user_id):
                return f"**{channel.mention}** (`{user_id}`)"
            elif member := ctx.guild.get_member(user_id):
                return f"**{member.mention}** (`{user_id}`"
            else:
                return f"**Unknown** (`{user_id}`)"

        rows = [get_user(u) for u in whitelisted]
        return await ctx.paginate(Embed(title="AntiSpam Whitelist"), rows, True)

    @antispam.command(
        name="settings",
        aliases=["view", "cfg", "config", "show"],
        description="view your configuration for anti spam",
    )
    @has_permissions(manage_guild=True)
    async def antispam_settings(self, ctx: Context):
        if not (
            settings := await self.bot.db.fetchrow(
                """SELECT * FROM antispam WHERE guild_id = $1""", ctx.guild.id
            )
        ):
            raise CommandError("there are no settings for this guild")
        embed = Embed(title="Anti Spam")
        configuration_value = f"""
**State:** {self.transfer_boolean(True if settings.status else False)}
**Threshold:** `{settings.threshold} messages / 10s`
**Timeout:** `{humanize.naturaldelta(timedelta(seconds=settings.timeout))}`
"""
        embed.add_field(name="Spam", value=configuration_value, inline=False)
        ladder_value = f"""
**State:** {self.transfer_boolean(True if settings.ladder_status else False)}
**Threshold:** `{settings.ladder_threshold} lines`
**Timeout:** `{humanize.naturaldelta(timedelta(seconds=settings.timeout))}`
"""
        embed.add_field(name="Ladder", value=ladder_value, inline=False)
        flood_value = f"""
**State:** {self.transfer_boolean(True if settings.flood_status else False)}
**Threshold:** `{settings.flood_threshold} characters`
**Timeout:** `{humanize.naturaldelta(timedelta(seconds=settings.timeout))}`
"""
        embed.add_field(name="Flood", value=flood_value, inline=False)
        return await ctx.send(embed=embed)

    @group(
        name="tracker",
        aliases=["trackers"],
        description="track username or vanity availability",
        invoke_without_command=True,
    )
    async def tracker(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @tracker.group(
        name="username",
        aliases=["names", "users", "usernames"],
        description="set the channel for tracking usernames",
        example=",tracker usernames add #names",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def tracker_username(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @tracker_username.command(
        name="add",
        aliases=["create", "set", "c", "a", "s"],
        description="add a channel for username notifications",
        example=",tracker username add #names",
    )
    @has_permissions(manage_guild=True)
    async def tracker_username_add(
        self, ctx: Context, *, channel: Union[TextChannel, Thread]
    ):
        channel_ids = (
            await self.bot.db.fetchval(
                """SELECT channel_ids FROM trackers WHERE tracker_type = $1 AND guild_id = $2""",
                "username",
                ctx.guild.id,
            )
            or []
        )
        if len(channel_ids) >= 2:
            raise CommandError("you can only have **2** tracker channels per type")
        if channel.id in channel_ids:
            raise CommandError("that channel is already a **username tracker**")
        channel_ids.append(channel.id)
        await self.bot.db.execute(
            """INSERT INTO trackers (guild_id, tracker_type, channel_ids) VALUES($1, $2, $3) ON CONFLICT(guild_id, tracker_type) DO UPDATE SET channel_ids = excluded.channel_ids""",
            ctx.guild.id,
            "username",
            channel_ids,
        )
        return await ctx.success(
            f"successfully **ADDED** {channel.mention} as a **username tracker**"
        )

    @tracker_username.command(
        name="remove",
        aliases=["delete", "del", "d", "r"],
        description="remove a channel for username notifications",
        example=",tracker username remove #names",
    )
    @has_permissions(manage_guild=True)
    async def tracker_username_remove(
        self, ctx: Context, *, channel: Union[TextChannel, Thread]
    ):
        if not (
            channel_ids := await self.bot.db.fetchval(
                """SELECT channel_ids FROM trackers WHERE tracker_type = $1 AND guild_id = $2""",
                "username",
                ctx.guild.id,
            )
        ):
            raise CommandError("No **username tracker** channels have been added")
        if channel.id not in channel_ids:
            raise CommandError(f"no **username tracker** found in {channel.mention}")
        channel_ids.remove(channel.id)
        if len(channel_ids) != 0:
            await self.bot.db.execute(
                """INSERT INTO trackers (guild_id, tracker_type, channel_ids) VALUES($1, $2, $3) ON CONFLICT(guild_id, tracker_type) DO UPDATE SET channel_ids = excluded.channel_ids""",
                ctx.guild.id,
                "username",
                channel_ids,
            )
        else:
            await self.bot.db.execute(
                """DELETE FROM trackers WHERE guild_id = $1 AND tracker_type = $2""",
                ctx.guild.id,
                "vanity",
            )
        return await ctx.success(
            f"successfully **REMOVED** {channel.mention} as a **username tracker**"
        )

    @tracker.group(
        name="vanity",
        aliases=["vanities"],
        description="set the channel for tracking vanitys",
        example=",tracker vanitys add #vanities",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def tracker_vanity(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @tracker_vanity.command(
        name="add",
        aliases=["create", "set", "c", "a", "s"],
        description="add a channel for vanity notifications",
        example=",tracker vanity add #vanities",
    )
    @has_permissions(manage_guild=True)
    async def tracker_vanity_add(
        self, ctx: Context, *, channel: Union[TextChannel, Thread]
    ):
        channel_ids = (
            await self.bot.db.fetchval(
                """SELECT channel_ids FROM trackers WHERE tracker_type = $1 AND guild_id = $2""",
                "vanity",
                ctx.guild.id,
            )
            or []
        )
        if len(channel_ids) >= 2:
            raise CommandError("you can only have **2** tracker channels per type")
        if channel.id in channel_ids:
            raise CommandError("that channel is already a **username tracker**")
        channel_ids.append(channel.id)
        await self.bot.db.execute(
            """INSERT INTO trackers (guild_id, tracker_type, channel_ids) VALUES($1, $2, $3) ON CONFLICT(guild_id, tracker_type) DO UPDATE SET channel_ids = excluded.channel_ids""",
            ctx.guild.id,
            "vanity",
            channel_ids,
        )
        return await ctx.success(
            f"successfully **ADDED** {channel.mention} as a **vanity tracker**"
        )

    @tracker_vanity.command(
        name="remove",
        aliases=["delete", "del", "d", "r"],
        description="remove a channel for vanity notifications",
        example=",tracker vanity remove #vanities",
    )
    @has_permissions(manage_guild=True)
    async def tracker_vanity_remove(
        self, ctx: Context, *, channel: Union[TextChannel, Thread]
    ):
        if not (
            channel_ids := await self.bot.db.fetchval(
                """SELECT channel_ids FROM trackers WHERE tracker_type = $1 AND guild_id = $2""",
                "vanity",
                ctx.guild.id,
            )
        ):
            raise CommandError("No **vanity tracker** channels have been added")
        if channel.id not in channel_ids:
            raise CommandError(f"no **vanity tracker** found in {channel.mention}")
        channel_ids.remove(channel.id)
        if len(channel_ids) != 0:
            await self.bot.db.execute(
                """INSERT INTO trackers (guild_id, tracker_type, channel_ids) VALUES($1, $2, $3) ON CONFLICT(guild_id, tracker_type) DO UPDATE SET channel_ids = excluded.channel_ids""",
                ctx.guild.id,
                "vanity",
                channel_ids,
            )
        else:
            await self.bot.db.execute(
                """DELETE FROM trackers WHERE guild_id = $1 AND tracker_type = $2""",
                ctx.guild.id,
                "vanity",
            )
        return await ctx.success(
            f"successfully **REMOVED** {channel.mention} as a **vanity tracker**"
        )

    @tracker.command(
        name="settings",
        aliases=["config", "show", "view", "ls"],
        description="show your tracker configuration",
    )
    @has_permissions(manage_guild=True)
    async def tracker_settings(self, ctx: Context):
        if not (
            trackers := await self.bot.db.fetch(
                """SELECT tracker_type, channel_ids FROM trackers WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("no **trackers** have been setup")
        fields = []
        username_field = None
        vanity_field = None
        embed = Embed(title="Tracker Settings")

        def get_channels(tracker: Record):
            def get_name(channel_id: int):
                if channel := ctx.guild.get_channel(channel_id):
                    return channel.mention
                else:
                    return f"Unknown (`{channel_id}`)"

            channels = [
                f"`{i}` {get_name(channel_id)}" for channel_id in tracker.channel_ids
            ]
            return "\n.".join(m for m in channels)

        for i, tracker in enumerate(trackers, start=1):
            if tracker.tracker_type == "username":
                username_field = get_channels(tracker)
            if tracker.tracker_type == "vanity":
                vanity_field = get_channels(tracker)

        if vanity_field:
            fields.append({"name": "Vanity", "value": vanity_field, "inline": False})
        else:
            fields.append({"name": "Vanity", "value": "N/A", "inline": False})
        if username_field:
            fields.insert(
                0, {"name": "Username", "value": username_field, "inline": False}
            )
        else:
            fields.insert(0, {"name": "Username", "value": "N/A", "inline": False})
        for field in fields:
            embed.add_field(**field)
        return await ctx.send(embed=embed)

    @hybrid_group(
        name="autorole",
        description="manage roles that will be assigned to members on join",
        invoke_without_command=True,
    )
    async def autorole(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @autorole.command(
        name="add",
        description="add a role for new member's to be given automatically",
        example=",autorole add members",
    )
    @has_permissions(manage_roles=True)
    async def autorole_add(self, ctx: Context, *, role: SafeRole):
        role_ids = (
            await self.bot.db.fetchval(
                """SELECT auto_roles FROM config WHERE guild_id = $1""", ctx.guild.id
            )
            or []
        )
        if role.id in role_ids:
            raise CommandError(f"{role.mention} is already an **auto role**")
        role_ids.append(role.id)
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, auto_roles) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET auto_roles = excluded.auto_roles""",
            ctx.guild.id,
            role_ids,
        )
        return await ctx.success(
            f"successfully **added** {role.mention} as an **auto role**"
        )

    @autorole.command(
        name="remove",
        description="remove an existing auto role",
        example=",autorole remove members",
    )
    @has_permissions(manage_roles=True)
    async def autorole_remove(self, ctx: Context, *, role: SafeRole):
        if not (
            role_ids := await self.bot.db.fetchval(
                """SELECT auto_roles FROM config WHERE guild_id = $1""", ctx.guild.id
            )
        ):
            raise CommandError(f"theres no **auto role** setup for {role.mention}")
        if role.id not in role_ids:
            raise CommandError(f"theres no **auto role** setup for {role.mention}")
        role_ids.remove(role.id)
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, auto_roles) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET auto_roles = excluded.auto_roles""",
            ctx.guild.id,
            role_ids,
        )
        return await ctx.success(
            f"successfully **removed** {role.mention} from the **auto roles**"
        )

    @autorole.command(
        name="list",
        aliases=["show", "ls", "view"],
        description="show existing auto roles",
    )
    @has_permissions(manage_roles=True)
    async def autorole_list(self, ctx: Context):
        if not (
            role_ids := await self.bot.db.fetchval(
                """SELECT auto_roles FROM config WHERE guild_id = $1""", ctx.guild.id
            )
        ):
            raise CommandError("theres no **auto roles** setup")
        roles = [r for role in role_ids if (r := ctx.guild.get_role(role))]
        rows = [f"`{i}` {r.mention}" for i, r in enumerate(roles, start=1)]
        embed = Embed(title="Auto Roles").set_author(
            name=str(ctx.author), icon_url=ctx.author.display_avatar.url
        )
        return await ctx.paginate(embed, rows)

    @autorole.command(
        name="clear", aliases=["reset", "cl"], description="clear all auto roles"
    )
    @has_permissions(manage_roles=True)
    async def autorole_clear(self, ctx: Context):
        await self.bot.db.execute(
            """UPDATE config SET auto_roles = NULL WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.success("successfully **cleared** all auto roles")

    @group(name="filter", invoke_without_command=True)
    async def automod_filter(self: "Configuration", ctx: Context) -> Message:
        """
        Protect your discord server using automod
        """

        return await ctx.send_help(ctx.command)

    @automod_filter.group(name="words", invoke_without_command=True)
    async def filter_words(self: "Configuration", ctx: Context):
        """
        Protect the server against unwanted words
        """

        return await ctx.send_help(ctx.command)

    @filter_words.command(name="remove", aliases=["rm"])
    @has_permissions(manage_guild=True)
    async def filter_words_remove(self: "Configuration", ctx: Context, *, word: str):
        """
        Unblacklist a word from the server
        """
        if len(word) > 60 or len(word) < 1:
            raise CommandError("word must be between 1 and 60 characters in length")
        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.creator_id == self.bot.user.id and not a.trigger.regex_patterns
            ),
            None,
        )

        if not automod:
            raise CommandError("There's no words automod rule found")

        keyword_filter = automod.trigger.keyword_filter
        keyword = f"*{word}*"

        if keyword not in keyword_filter:
            raise CommandError(f"**{word}** is not blacklisted from this server")

        keyword_filter.remove(keyword)
        await automod.edit(
            trigger=AutoModTrigger(
                type=AutoModRuleTriggerType.keyword,
                keyword_filter=keyword_filter,
            ),
            reason=f"Automod rule edited by {ctx.author}",
        )

        return await ctx.success(f"Removed **{word}** from the blacklisted words")

    @filter_words.command(name="add")
    @has_permissions(manage_guild=True)
    async def filter_words_add(self: "Configuration", ctx: Context, *, word: str):
        """
        Blacklist a word from the server's channels
        """
        if len(word) > 60 or len(word) < 1:
            raise CommandError("word must be between 1 and 60 characters in length")
        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.creator_id == self.bot.user.id and not a.trigger.regex_patterns
            ),
            None,
        )

        if not automod:
            actions = [
                AutoModRuleAction(
                    custom_message=f"Message blocked by {self.bot.user.name} for containing a blacklisted word"
                )
            ]

            automod = await ctx.guild.create_automod_rule(
                name=f"{self.bot.user.name} - words",
                event_type=AutoModRuleEventType.message_send,
                trigger=AutoModTrigger(
                    type=AutoModRuleTriggerType.keyword,
                    keyword_filter=[f"*{word}*"],
                ),
                enabled=True,
                actions=actions,
                reason=f"Automod rule enabled by {ctx.author}",
            )
        else:
            keyword_filter = automod.trigger.keyword_filter
            keyword_filter.append(f"*{word}*")
            await automod.edit(
                trigger=AutoModTrigger(
                    type=AutoModRuleTriggerType.keyword,
                    keyword_filter=keyword_filter,
                ),
                reason=f"Automod rule edited by {ctx.author}",
            )

        return await ctx.success(f"Added **{word}** as a blacklisted word")

    @filter_words.command(name="unwhitelist", aliases=["uwl"])
    @has_permissions(manage_guild=True)
    async def filter_words_uwl(
        self: "Configuration",
        ctx: Context,
        *,
        target: Union[SafeRoleConverter, TextChannel],
    ):
        """
        Unwhitelist a role or a channel against the blacklist word punishment
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.creator_id == self.bot.user.id and not a.trigger.regex_patterns
            ),
            None,
        )

        if not automod:
            raise CommandError("The word automod rule was not enabled")

        if isinstance(target, Role):
            roles = automod.exempt_roles
            if target not in roles:
                raise CommandError("This role is **not** whitelisted")
            else:
                roles.remove(target)

            await automod.edit(exempt_roles=roles)
        else:
            channels = automod.exempt_channels
            if target not in channels:
                raise CommandError("This channel is **not** whitelisted")
            else:
                channels.remove(target)

            await automod.edit(exempt_channels=channels)

        return await ctx.success(
            f"Unwhitelisted {target.mention} against blacklist words punishment"
        )

    @filter_words.command(name="whitelist", aliases=["wl"])
    @has_permissions(manage_guild=True)
    async def filter_words_wl(
        self: "Configuration",
        ctx: Context,
        *,
        target: Union[SafeRoleConverter, TextChannel],
    ):
        """
        Whitelist a role or a channel against the blacklisted words punishment
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.creator_id == self.bot.user.id and not a.trigger.regex_patterns
            ),
            None,
        )

        if not automod:
            raise CommandError("The words automod rule was not enabled")

        if isinstance(target, Role):
            roles = automod.exempt_roles
            if target in roles:
                raise CommandError("This role is **already** whitelisted")
            else:
                roles.append(target)

            await automod.edit(exempt_roles=roles)
        else:
            channels = automod.exempt_channels
            if target in channels:
                raise CommandError("This channel is **already** whitelisted")
            else:
                channels.append(target)

            await automod.edit(exempt_channels=channels)

        return await ctx.success(
            f"Whitelisted {target.mention} against blacklisted words punishment"
        )

    @filter_words.command(name="view", aliases=["list"])
    @has_permissions(manage_guild=True)
    async def filter_words_view(self: "Configuration", ctx: Context):
        """
        View the blacklisted words in this server
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.creator_id == self.bot.user.id and not a.trigger.regex_patterns
            ),
            None,
        )

        if not automod:
            raise CommandError("The blacklist words automod rule is not enabled")

        words = list(map(lambda m: m[1:-1], automod.trigger.keyword_filter))
        return await ctx.paginate(
            words, Embed(title=f"Blacklisted words ({len(words)})")
        )

    @automod_filter.group(name="links", invoke_without_command=True)
    async def filter_links(self: "Configuration", ctx: Context) -> Message:
        """
        Protect your server against regular links
        """

        return await ctx.send_help(ctx.command)

    @filter_links.command(
        name="remove", aliases=["rm", "delete", "del", "disable", "dis"]
    )
    @has_permissions(manage_guild=True)
    async def filter_links_disable(self: "Configuration", ctx: Context):
        """
        Disable the protection against regular links
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.trigger.regex_patterns == [self.link_regex]
            ),
            None,
        )

        if not automod:
            raise CommandError("The regular links automod rule was not enabled")

        await automod.delete(reason=f"Disabled by {ctx.author}")

        return await ctx.success("The regular links automod rule was deleted")

    @filter_links.command(name="enable", aliases=["e"])
    @has_permissions(manage_guild=True)
    async def filter_links_enable(
        self: "Configuration",
        ctx: Context,
        punishment: Literal["mute", "block"] = "block",
    ):
        """
        Enable the protection against regular links
        """

        automod = next(
            (
                e
                for e in await ctx.guild.fetch_automod_rules()
                if e.trigger.regex_patterns == [self.link_regex]
            ),
            None,
        )

        if automod:
            raise CommandError("There's such an automod rule **already** enabled")

        actions = [
            AutoModRuleAction(custom_message=f"Message blocked by {self.bot.user.name}")
        ]

        if punishment == "mute":
            actions.append(AutoModRuleAction(duration=datetime.timedelta(minutes=5)))

        await ctx.guild.create_automod_rule(
            name=f"{self.bot.user.name} - links",
            event_type=AutoModRuleEventType.message_send,
            trigger=AutoModTrigger(
                type=AutoModRuleTriggerType.keyword,
                regex_patterns=[self.link_regex],
            ),
            actions=actions,
            enabled=True,
            reason=f"Automod rule enabled by {ctx.author}",
        )

        return await ctx.success(
            f"Regular link automod rule enabled\npunishment: {'**block**' if punishment == 'block' else 'mute **5 minutes**'}"
        )

    @filter_links.command(name="unwhitelist", aliases=["uwl"])
    @has_permissions(manage_guild=True)
    async def filter_links_uwl(
        self: "Configuration",
        ctx: Context,
        *,
        target: Union[SafeRoleConverter, TextChannel],
    ):
        """
        Unwhitelist a role or a channel agains the regular link punishment
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.trigger.regex_patterns == [self.link_regex]
            ),
            None,
        )

        if not automod:
            raise CommandError("The regular link automod rule was not enabled")

        if isinstance(target, Role):
            roles = automod.exempt_roles
            if target not in roles:
                raise CommandError("This role is **not** whitelisted")
            else:
                roles.remove(target)

            await automod.edit(exempt_roles=roles)
        else:
            channels = automod.exempt_channels
            if target not in channels:
                raise CommandError("This channel is **not** whitelisted")
            else:
                channels.remove(target)

            await automod.edit(exempt_channels=channels)

        return await ctx.success(
            f"Unwhitelisted {target.mention} against regular link punishment"
        )

    @filter_links.command(name="whitelist", aliases=["wl"])
    @has_permissions(manage_guild=True)
    async def filter_links_wl(
        self: "Configuration",
        ctx: Context,
        *,
        target: Union[SafeRoleConverter, TextChannel],
    ):
        """
        Whitelist a role or a channel against the regular link punishment
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.trigger.regex_patterns == [self.link_regex]
            ),
            None,
        )

        if not automod:
            raise CommandError("The regular link automod rule was not enabled")

        if isinstance(target, Role):
            roles = automod.exempt_roles
            if target in roles:
                raise CommandError("This role is **already** whitelisted")
            else:
                roles.append(target)

            await automod.edit(exempt_roles=roles)
        else:
            channels = automod.exempt_channels
            if target in channels:
                raise CommandError("This channel is **already** whitelisted")
            else:
                channels.append(target)

            await automod.edit(exempt_channels=channels)

        return await ctx.success(
            f"Whitelisted {target.mention} against regular link punishment"
        )

    @automod_filter.group(name="invites", invoke_without_command=True)
    async def filter_invites(self: "Configuration", ctx: Context) -> Message:
        """
        Protect your discord server against discord invites
        """

        return await ctx.send_help(ctx.command)

    @filter_invites.command(name="unwhitelist", aliases=["uwl"])
    @has_permissions(manage_guild=True)
    async def filter_invites_uwl(
        self: "Configuration",
        ctx: Context,
        *,
        target: Union[SafeRoleConverter, TextChannel],
    ):
        """
        Unwhitelist a role or a channel agains the anti invite punishment
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.trigger.regex_patterns == [self.bot.invite_regex]
            ),
            None,
        )

        if not automod:
            raise CommandError("The anti invite automod rule was not enabled")

        if isinstance(target, Role):
            roles = automod.exempt_roles
            if target not in roles:
                raise CommandError("This role is **not** whitelisted")
            else:
                roles.remove(target)

            await automod.edit(exempt_roles=roles)
        else:
            channels = automod.exempt_channels
            if target not in channels:
                raise CommandError("This channel is **not** whitelisted")
            else:
                channels.remove(target)

            await automod.edit(exempt_channels=channels)

        return await ctx.success(
            f"Unwhitelisted {target.mention} against anti invite punishment"
        )

    @filter_invites.command(name="whitelist", aliases=["wl"])
    @has_permissions(manage_guild=True)
    async def fitler_invites_wl(
        self: "Configuration",
        ctx: Context,
        *,
        target: Union[SafeRoleConverter, TextChannel],
    ):
        """
        Whitelist a role or a channel against the anti invite punishment
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.trigger.regex_patterns == [self.bot.invite_regex]
            ),
            None,
        )

        if not automod:
            raise CommandError("The anti invite automod rule was not enabled")

        if isinstance(target, Role):
            roles = automod.exempt_roles
            if target in roles:
                raise CommandError("This role is **already** whitelisted")
            else:
                roles.append(target)

            await automod.edit(exempt_roles=roles)
        else:
            channels = automod.exempt_channels
            if target in channels:
                raise CommandError("This channel is **already** whitelisted")
            else:
                channels.append(target)

            await automod.edit(exempt_channels=channels)

        return await ctx.success(
            f"Whitelisted {target.mention} against anti invite punishment"
        )

    @filter_invites.command(
        name="remove", aliases=["rm", "delete", "del", "disable", "dis"]
    )
    @has_permissions(manage_guild=True)
    async def filter_invites_disable(self: "Configuration", ctx: Context):
        """
        Disable the protection against discord invites
        """

        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.trigger.regex_patterns == [self.bot.invite_regex]
            ),
            None,
        )

        if not automod:
            raise CommandError("The anti invite automod rule was not enabled")

        await automod.delete(reason=f"Disabled by {ctx.author}")

        return await ctx.success("The anti invite automod rule was deleted")

    @filter_invites.command(name="enable", aliases=["e"])
    @has_permissions(manage_guild=True)
    async def filter_invites_enable(
        self: "Configuration",
        ctx: Context,
        punishment: Literal["mute", "block"] = "block",
    ):
        """
        Block discord invites from getting sent in your discord server
        """
        automod = next(
            (
                a
                for a in await ctx.guild.fetch_automod_rules()
                if a.trigger.regex_patterns == [self.bot.invite_regex]
            ),
            None,
        )

        if automod:
            raise CommandError("Such a rule is **already** enabled")

        actions = [
            AutoModRuleAction(
                custom_message=f"This message has been blocked by {self.bot.user.name}"
            )
        ]

        if punishment == "mute":
            actions.append(AutoModRuleAction(duration=datetime.timedelta(minutes=5)))

        await ctx.guild.create_automod_rule(
            name=f"{self.bot.user.name} - invites",
            event_type=AutoModRuleEventType.message_send,
            trigger=AutoModTrigger(
                type=AutoModRuleTriggerType.keyword,
                regex_patterns=[self.bot.invite_regex],
            ),
            actions=actions,
            enabled=True,
            reason=f"Automod rule configured by {ctx.author}",
        )

        return await ctx.success(
            f"Configured anti invite automod rule\npunishment: {'block' if punishment == '**block**' else 'mute **5 minutes**'}"
        )

    @group(
        name="fakepermissions",
        aliases=["fakepermission", "fakeperms", "fakeperm", "fp"],
        description="give roles permissions only for use with bot commands",
        invoke_without_command=True,
    )
    async def fakepermissions(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @fakepermissions.command(
        name="add",
        aliases=["create", "set"],
        description="add permissions to a role for use in bot commands",
        example=",fakepermissions add @moderators moderate members, ban members",
    )
    @has_permissions(administrator=True, fake=False)
    async def fakepermissions_add(
        self, ctx: Context, role: Role, *, permissions: FakePermission
    ):
        perms = (
            await self.bot.db.fetchval(
                """SELECT permissions FROM fake_permissions WHERE guild_id = $1 AND role_id = $2""",
                ctx.guild.id,
                role.id,
            )
            or []
        )
        duplicate = next((p for p in permissions if p in perms), None)
        if duplicate:
            raise CommandError(
                f"There's already `{duplicate}` permission on {role.mention}"
            )
        perms.extend([i for i in permissions if i not in perms])
        await self.bot.db.execute(
            """INSERT INTO fake_permissions (guild_id, role_id, permissions) VALUES($1, $2, $3) ON CONFLICT(guild_id, role_id) DO UPDATE SET permissions = excluded.permissions""",
            ctx.guild.id,
            role.id,
            perms,
        )
        return await ctx.success(
            f"successfully **added** the following permissions to {role.mention}: {', '.join(f'`{p}`' for p in permissions)}"
        )

    @fakepermissions.command(
        name="remove",
        aliases=["delete", "del", "rem", "d", "r"],
        description="remove fake permission(s) from a role",
        example=",fakepermissions remove @moderators moderate members, ban members",
    )
    @has_permissions(administrator=True, fake=False)
    async def fakepermissions_remove(
        self, ctx: Context, role: Role, *, permissions: FakePermission
    ):
        perms = await self.bot.db.fetchval(
            """SELECT permissions FROM fake_permissions WHERE guild_id = $1 AND role_id = $2""",
            ctx.guild.id,
            role.id,
        )
        if not perms:
            raise CommandError(
                f"there are no **fake permissions** setup for {role.mention}"
            )
        perms = [i for i in perms if i not in permissions]
        await self.bot.db.execute(
            """INSERT INTO fake_permissions (guild_id, role_id, permissions) VALUES($1, $2, $3) ON CONFLICT(guild_id, role_id) DO UPDATE SET permissions = excluded.permissions""",
            ctx.guild.id,
            role.id,
            perms,
        )
        return await ctx.success(
            f"successfully **removed** the following permissions from {role.mention}: {', '.join(f'`{p}`' for p in permissions)}"
        )

    @fakepermissions.command(
        name="list", description="view all fake permissions that have been setup"
    )
    @has_permissions(administrator=True, fake=False)
    async def fakepermissions_list(self, ctx: Context, *, role: Optional[Role] = None):

        def format_permission(d: str) -> str:
            return d.replace("_", " ")

        if role:
            perms = await self.bot.db.fetchval(
                """SELECT permissions FROM fake_permissions WHERE guild_id = $1 AND role_id = $2""",
                ctx.guild.id,
                role.id,
            )
            rows = [
                f"`{i}` `{p.replace('_', ' ')}" for i, p in enumerate(perms, start=1)
            ]
            embed = Embed(title=f"Permissions for {role.name.title()}").set_author(
                name=str(ctx.author), icon_url=ctx.author.display_avatar.url
            )
        else:
            perms = await self.bot.db.fetch(
                """SELECT role_id, permissions FROM fake_permissions WHERE guild_id = $1""",
                ctx.guild.id,
            )
            rows = []
            perms = [i for i in perms if (role := ctx.guild.get_role(i.role_id))]
            rows = [
                f"`{i}` {ctx.guild.get_role(p.role_id).mention} - {', '.join(f'`{format_permission(d)}' for d in p.permissions)}"
                for i, p in enumerate(perms, start=1)
            ]
            embed = Embed(title="Fake Permissions").set_author(
                name=str(ctx.author), icon_url=ctx.author.display_avatar.url
            )

        if len(rows) == 0:
            raise CommandError("there are no **fake permissions** setup")

        return await ctx.paginate(embed, rows)

    @fakepermissions.command(
        name="valid", description="view the list of valid permissions"
    )
    @has_permissions(administrator=True, fake=False)
    async def fakepermissions_valid(self, ctx: Context):
        embed = Embed(title="Valid Permissions").set_author(
            name=str(ctx.author), icon_url=ctx.author.display_avatar.url
        )
        rows = [f"`{i.replace('_', ' ')}`" for i in PERMISSION_LIST]
        return await ctx.paginate(embed, rows)

    @group(
        name="settings",
        aliases=["configuration", "config", "cfg", "setting"],
        description="setup server based features for your server",
        invoke_without_command=True,
    )
    async def settings(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @settings.command(
        name="repost",
        aliases=["reposting", "autoembed"],
        description="automatically repost supported social media links",
        example=",settings repost on",
    )
    @has_permissions(manage_messages=True)
    async def settings_repost(self, ctx: Context, state: Boolean):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, reposting) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET reposting = excluded.reposting""",
            ctx.guild.id,
            state,
        )
        return await ctx.success(
            f"successfully **{'ENABLED' if state else 'DISABLED'}** auto reposting"
        )

    @settings.command(
        name="transcribe",
        aliases=["voicetotext", "autotranscribe", "transcriptions", "transcription"],
        descripition="automatically send voice messages as text",
        example=",settings transcribe on",
    )
    @has_permissions(manage_messages=True)
    async def settings_transcribe(self, ctx: Context, state: Boolean):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, transcription) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET transcription = excluded.transcription""",
            ctx.guild.id,
            state,
        )
        return await ctx.success(
            f"successfully **{'ENABLED' if state else 'DISABLED'}** auto voice message transcribing"
        )

    @settings.command(
        name="heximage",
        aliases=["colorhex", "autocolor", "autohex", "imghex"],
        description="Enable/Disable hex image displaying when hex code is sent",
        example=",settings heximage on",
    )
    @has_permissions(manage_messages=True)
    async def settings_heximage(self, ctx: Context, state: Boolean):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, auto_hex) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET auto_hex = excluded.auto_hex""",
            ctx.guild.id,
            state,
        )
        return await ctx.success(
            f"successfully **{'ENABLED' if state else 'DISABLED'}** auto color image hex posting"
        )

    @settings.group(
        name="welcome",
        aliases=["welc", "wlc", "join"],
        description="configure or alter your welcome message setup",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def settings_welcome(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @settings_welcome.command(
        name="message",
        aliases=["msg", "embed", "m"],
        description="set your welcome message",
        example=",settings welcome message {embed}{description: welcome {user.mention}}",
    )
    @has_permissions(manage_guild=True)
    async def settings_welcome_message(self, ctx: Context, *, code: EmbedConverter):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, welcome_message) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET welcome_message = excluded.welcome_message""",
            ctx.guild.id,
            code,
        )
        return await ctx.success(f"welcome message has been set to ```{code}```")

    @settings_welcome.command(
        name="channel",
        aliases=["ch", "destination", "dest"],
        description="set the welcome message channel",
        example=",settings welcome channel #welc",
    )
    @has_permissions(manage_guild=True)
    async def settings_welcome_channel(self, ctx: Context, *, channel: TextChannel):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, welcome_channel) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET welcome_channel = excluded.welcome_channel""",
            ctx.guild.id,
            channel.id,
        )
        return await ctx.success(
            f"successfully set the **welcome channel** to {channel.mention}"
        )

    @settings_welcome.command(
        name="reset", description="reset your welcome configuration"
    )
    @has_permissions(manage_guild=True)
    async def settings_welcome_reset(self, ctx: Context):
        try:
            await self.bot.db.execute(
                """UPDATE config SET welcome_message = NULL, welcome_channel = NULL WHERE guild_id = $1""",
                ctx.guild.id,
            )
        except Exception:
            raise CommandError("you have not setup your welcome configuration")
        return await ctx.success("successfully **RESET** your welcome configuration")

    @settings_welcome.command(
        name="test",
        aliases=["view", "show"],
        description="emit a fake member join event to see your welcome configuration",
    )
    @has_permissions(manage_guild=True)
    async def settings_welcome_test(self, ctx: Context):
        if not (
            config := await self.bot.db.fetchrow(
                """SELECT welcome_channel, welcome_message FROM config WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("you have not setup your welcome configuration")
        if not config.welcome_channel:
            raise CommandError("you have not set a welcome channel")
        if not config.welcome_message:
            raise CommandError("you have not set a welcome message")
        if not (channel := ctx.guild.get_channel(config.welcome_channel)):
            raise CommandError("welcome channel is not valid")
        self.bot.dispatch(
            "welcome", ctx.guild, ctx.author, channel, config.welcome_message
        )

    @settings.group(
        name="boost",
        aliases=["booster", "boostmessage"],
        description="configure or alter your boost message setup",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def settings_boost(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @settings_boost.command(
        name="message",
        aliases=["msg", "embed", "m"],
        description="set your boost message",
        example=",settings boost message {embed}{description: thanks {user.mention}}",
    )
    @has_permissions(manage_guild=True)
    async def settings_boost_message(self, ctx: Context, *, code: EmbedConverter):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, boost_message) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET boost_message = excluded.boost_message""",
            ctx.guild.id,
            code,
        )
        return await ctx.success(f"boost message has been set to ```{code}```")

    @settings_boost.command(
        name="channel",
        aliases=["ch", "destination", "dest"],
        description="set the boost message channel",
        example=",settings boost channel #welc",
    )
    @has_permissions(manage_guild=True)
    async def settings_boost_channel(self, ctx: Context, *, channel: TextChannel):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, boost_channel) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET boost_channel = excluded.boost_channel""",
            ctx.guild.id,
            channel.id,
        )
        return await ctx.success(
            f"successfully set the **boost channel** to {channel.mention}"
        )

    @settings_boost.command(name="reset", description="reset your boost configuration")
    @has_permissions(manage_guild=True)
    async def settings_boost_reset(self, ctx: Context):
        try:
            await self.bot.db.execute(
                """UPDATE config SET boost_message = NULL, boost_channel = NULL WHERE guild_id = $1""",
                ctx.guild.id,
            )
        except Exception:
            raise CommandError("you have not setup your boost configuration")
        return await ctx.success("successfully **RESET** your boost configuration")

    @settings_boost.command(
        name="test",
        aliases=["view", "show"],
        description="emit a fake member join event to see your boost configuration",
    )
    @has_permissions(manage_guild=True)
    async def settings_boost_test(self, ctx: Context):
        if not (
            config := await self.bot.db.fetchrow(
                """SELECT boost_channel, boost_message FROM config WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("you have not setup your boost configuration")
        if not config.boost_channel:
            raise CommandError("you have not set a boost channel")
        if not config.boost_message:
            raise CommandError("you have not set a boost message")
        if not (channel := ctx.guild.get_channel(config.boost_channel)):
            raise CommandError("boost channel is not valid")
        self.bot.dispatch("boost", ctx.guild, ctx.author, channel, config.boost_message)

    @settings.group(
        name="leave",
        aliases=["goodbye", "bye"],
        description="configure or alter your leave message setup",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def settings_leave(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @settings_leave.command(
        name="message",
        aliases=["msg", "embed", "m"],
        description="set your leave message",
        example=",settings leave message {embed}{description: leave {user.mention}}",
    )
    @has_permissions(manage_guild=True)
    async def settings_leave_message(self, ctx: Context, *, code: EmbedConverter):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, leave_message) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET leave_message = excluded.leave_message""",
            ctx.guild.id,
            code,
        )
        return await ctx.success(f"leave message has been set to ```{code}```")

    @settings_leave.command(
        name="channel",
        aliases=["ch", "destination", "dest"],
        description="set the leave message channel",
        example=",settings leave channel #welc",
    )
    @has_permissions(manage_guild=True)
    async def settings_leave_channel(self, ctx: Context, *, channel: TextChannel):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, leave_channel) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET leave_channel = excluded.leave_channel""",
            ctx.guild.id,
            channel.id,
        )
        return await ctx.success(
            f"successfully set the **leave channel** to {channel.mention}"
        )

    @settings_leave.command(name="reset", description="reset your leave configuration")
    @has_permissions(manage_guild=True)
    async def settings_leave_reset(self, ctx: Context):
        try:
            await self.bot.db.execute(
                """UPDATE config SET leave_message = NULL, leave_channel = NULL WHERE guild_id = $1""",
                ctx.guild.id,
            )
        except Exception:
            raise CommandError("you have not setup your leave configuration")
        return await ctx.success("successfully **RESET** your leave configuration")

    @settings_leave.command(
        name="test",
        aliases=["view", "show"],
        description="emit a fake member join event to see your leave configuration",
    )
    @has_permissions(manage_guild=True)
    async def settings_leave_test(self, ctx: Context):
        if not (
            config := await self.bot.db.fetchrow(
                """SELECT leave_channel, leave_message FROM config WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("you have not setup your leave configuration")
        if not config.leave_channel:
            raise CommandError("you have not set a leave channel")
        if not config.leave_message:
            raise CommandError("you have not set a leave message")
        if not (channel := ctx.guild.get_channel(config.leave_channel)):
            raise CommandError("leave channel is not valid")
        self.bot.dispatch("leave", ctx.guild, ctx.author, channel, config.leave_message)

    @settings.command(
        name="configuration",
        aliases=["settings", "cfg", "config", "view", "ls", "show"],
        description="view all of your settings",
    )
    @has_permissions(manage_guild=True)
    async def settings_configuration(self, ctx: Context):
        if not (
            config := await self.bot.db.fetchrow(
                """SELECT * FROM config WHERE guild_id = $1""", ctx.guild.id
            )
        ):
            raise CommandError("you have not setup anything")
        media_value = f"**Transcription:** {self.transfer_boolean(config.transcription)}\n**Color Hex:** {self.transfer_boolean(config.auto_hex)}\n**Reposting:** {self.transfer_boolean(config.reposting)}"
        welcome_value = f"**Channel:** {channel.mention if (channel := ctx.guild.get_channel(config.welcome_channel)) else self.transfer_boolean(False)}\n**Message:** {config.welcome_message.shorten(30) if config.welcome_message else self.transfer_boolean(False)}"
        boost_value = f"**Channel:** {channel.mention if (channel := ctx.guild.get_channel(config.boost_channel)) else self.transfer_boolean(False)}\n**Message:** {config.boost_message.shorten(30) if config.boost_message else self.transfer_boolean(False)}"
        leave_value = f"**Channel:** {channel.mention if (channel := ctx.guild.get_channel(config.leave_channel)) else self.transfer_boolean(False)}\n**Message:** {config.leave_message.shorten(30) if config.leave_message else self.transfer_boolean(False)}"
        embed = Embed(title="Configuration")
        description = (
            f">>> __**Media**__\n{media_value}\n\n"
            f"__**Welcome**__\n{welcome_value}\n\n"
            f"__**Boost**__\n{boost_value}\n\n"
            f"__**Leave**__\n{leave_value}"
        )
        embed.description = description
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        return await ctx.send(embed=embed)


async def setup(bot: Client):
    await bot.add_cog(Configuration(bot))
