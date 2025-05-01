#
from typing import Any, Dict, List, Literal, Optional, Union

from data.config import CONFIG
from data.variables import dangerous_permissions
from discord import (Client, Embed, File, Guild, Member, Message, TextChannel,
                     Thread, User)
from discord.ext.commands import (Boolean, Cog, CommandConverter, CommandError,
                                  check, command, group, has_permissions)
from loguru import logger
from system.managers.flags.antinuke import Parameters, get_parameters
from system.patch.context import Context

from .model import Configuration


def guild_owner():
    async def predicate(ctx: Context) -> bool:
        if ctx.author.id == ctx.guild.owner_id or ctx.author.id in ctx.bot.owner_ids:
            return True
        raise CommandError("You aren't the server owner.")

    return check(predicate)


def trusted():
    async def predicate(ctx: Context):
        if ctx.author.id in ctx.bot.owner_ids:
            return True
        admins = set(
            await ctx.bot.db.fetchval(
                """
                SELECT admins FROM antinuke
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
            or []
        )
        admins.add(ctx.guild.owner_id)

        if ctx.author.id not in admins:
            raise CommandError("You aren't the server owner or an antinuke admin.")
        return True

    return check(predicate)


class AntiNuke(Cog):
    def __init__(self, bot: Client) -> None:
        self.bot: Client = bot

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.command.name == "admin":
            if (
                not ctx.author.id == ctx.guild.owner_id
                and ctx.author.id not in self.bot.owner_ids
            ):
                raise CommandError(
                    "You must be the **server owner** to run this command."
                )

            return True

        admins = set(
            await self.bot.db.fetchval(
                """
                SELECT admins FROM antinuke
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
            or []
        )
        admins.add(ctx.guild.owner_id)

        if ctx.author.id not in admins:
            if ctx.author.id not in self.bot.owner_ids:
                raise CommandError(
                    "You must be an **antinuke admin** to run this command."
                )

        return True

    @group(
        name="antinuke",
        usage="(subcommand) <args>",
        aliases=["an"],
        invoke_without_command=True,
    )
    @trusted()
    async def antinuke(self, ctx: Context) -> Message:
        """
        Antinuke to protect your server
        """
        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command.qualified_name)

    @antinuke.command(
        name="config",
        aliases=[
            "configuration",
            "settings",
        ],
    )
    @trusted()
    async def antinuke_config(self, ctx: Context) -> Message:
        """
        View server configuration for Antinuke
        """
        try:
            configuration: Configuration = Configuration(
                **await self.bot.db.fetchrow(
                    """
                SELECT * FROM antinuke
                WHERE guild_id = $1
                """,
                    ctx.guild.id,
                )
            )
        except Exception:
            raise CommandError("you have not setup the antinuke")

        enabled: int = 0
        for module, value in configuration:
            if not (getattr(value, "status", False)):
                continue

            enabled += 1

        embed = Embed(
            title="Settings",
            description=f"Antinuke is **{'enabled' if enabled else 'disabled'}** in this server",
        )

        embed.add_field(
            name="Modules",
            value=(
                "**Role Deletion:** "
                + (
                    CONFIG["emojis"]["success"]
                    if configuration.role.status
                    else CONFIG["emojis"]["fail"]
                )
                + "\n**Emoji Deletion:** "
                + (
                    CONFIG["emojis"]["success"]
                    if configuration.emoji.status
                    else CONFIG["emojis"]["fail"]
                )
                + "\n**Mass Member Ban:** "
                + (
                    CONFIG["emojis"]["success"]
                    if configuration.ban.status
                    else CONFIG["emojis"]["fail"]
                )
                + "\n**Mass Member Kick:** "
                + (
                    CONFIG["emojis"]["success"]
                    if configuration.kick.status
                    else CONFIG["emojis"]["fail"]
                )
                + "\n**Webhook Creation:** "
                + (
                    CONFIG["emojis"]["success"]
                    if configuration.webhook.status
                    else CONFIG["emojis"]["fail"]
                )
                + "\n**Channel Creation/Deletion:** "
                + (
                    CONFIG["emojis"]["success"]
                    if configuration.channel.status
                    else CONFIG["emojis"]["fail"]
                )
            ),
            inline=True,
        )
        embed.add_field(
            name="General",
            value=(
                f"**Super Admins:** {len(configuration.admins)}"
                + "\n**Whitelisted Bots:** "
                + str(
                    len(
                        [
                            member_id
                            for member_id in configuration.whitelist
                            if (member := self.bot.get_user(member_id)) and member.bot
                        ]
                    )
                )
                + "\n**Whitelisted Members:** "
                + str(
                    len(
                        [
                            member_id
                            for member_id in configuration.whitelist
                            if (member := self.bot.get_user(member_id))
                            and not member.bot
                        ]
                    )
                )
                + "\n**Protection Modules:** "
                + f"{enabled} enabled"
                + "\n**Watch Permission Grant:** "
                + (
                    str(
                        len(
                            [
                                permission
                                for permission in configuration.permissions
                                if permission.type == "grant"
                            ]
                        )
                    )
                    + "/"
                    + str(len(dangerous_permissions))
                    + " perms"
                )
                + "\n**Watch Permission Remove:** "
                + (
                    str(
                        len(
                            [
                                permission
                                for permission in configuration.permissions
                                if permission.type == "remove"
                            ]
                        )
                    )
                    + "/"
                    + str(len(dangerous_permissions))
                    + " perms"
                )
                + "\n**Deny Bot Joins (bot add):** "
                + (
                    CONFIG["emojis"]["success"]
                    if configuration.botadd.status
                    else CONFIG["emojis"]["fail"]
                )
            ),
            inline=True,
        )

        return await ctx.send(embed=embed)

    @antinuke.command(
        name="whitelist",
        example=",antinuke whitelist 593921296224747521",
    )
    @trusted()
    async def antinuke_whitelist(
        self, ctx: Context, *, member: Union[Member, User]
    ) -> Message:
        """
        Whitelist a member from triggering antinuke or a bot to join
        """

        whitelist: List[int] = await self.bot.db.fetchval(
            """
            INSERT INTO antinuke (guild_id, whitelist)
            VALUES ($1, ARRAY[$2]::bigint[])
            ON CONFLICT (guild_id) DO UPDATE
            SET whitelist = CASE
                WHEN $2 = ANY(antinuke.whitelist) THEN array_remove(antinuke.whitelist, $2)
                ELSE antinuke.whitelist || ARRAY[$2]::bigint[]
                END
            RETURNING whitelist;
            """,
            ctx.guild.id,
            member.id,
        )

        if member.id in whitelist:
            return await ctx.success(
                f"**{member}** is now whitelisted and "
                + (
                    "can join"
                    if member.bot and not isinstance(member, Member)
                    else "will not trigger **antinuke**"
                )
            )
        else:
            return await ctx.success(f"**{member}** is no longer whitelisted")

    @antinuke.command(
        name="admin",
        example=",antinuke admin jonathan",
    )
    @guild_owner()
    async def antinuke_admin(
        self, ctx: Context, *, member: Union[Member, User]
    ) -> Message:
        """
        Give a member permissions to edit antinuke settings
        """

        if member.bot:
            return await ctx.fail("You cannot make a bot an **antinuke admin**")

        admins: List[int] = await self.bot.db.fetchval(
            """
            INSERT INTO antinuke (guild_id, admins)
            VALUES ($1, ARRAY[$2]::bigint[])
            ON CONFLICT (guild_id) DO UPDATE
            SET admins = CASE
                WHEN $2 = ANY(antinuke.admins) THEN array_remove(antinuke.admins, $2)
                ELSE antinuke.admins || ARRAY[$2]::bigint[]
                END
            RETURNING admins;
            """,
            ctx.guild.id,
            member.id,
        )

        if member.id in admins:
            return await ctx.success(
                f"**{member}** is now an **antinuke admin** and can edit **antinuke settings**"
            )
        else:
            return await ctx.success(
                f"**{member}** is no longer an **antinuke admin** and can no longer edit **antinuke settings**"
            )

    @antinuke.command(name="admins")
    @guild_owner()
    async def antinuke_admins(self, ctx: Context) -> Message:
        """
        View all antinuke admins
        """

        admins: List[int] = (
            await self.bot.db.fetchval(
                """
            SELECT admins FROM antinuke
            WHERE guild_id = $1;
            """,
                ctx.guild.id,
            )
            or []
        )

        if not admins:
            return await ctx.fail("There are no **antinuke admins**")

        return await ctx.paginate(
            Embed(title="Antinuke Admins"), [f"<@{user_id}>" for user_id in admins]
        )

    @antinuke.command(name="list")
    @trusted()
    async def antinuke_list(self, ctx: Context) -> Message:
        """
        View all enabled modules along with whitelisted members & bots
        """

        configuration: Configuration = Configuration(
            **await self.bot.db.fetchrow(
                """
            SELECT * FROM antinuke
            WHERE guild_id = $1
            """,
                ctx.guild.id,
            )
        )

        entries: List = []

        if (ban := configuration.ban) and ban.status:
            entries.append(
                f"**ban** (do: {ban.punishment}, threshold: {ban.threshold}, cmd: {'on' if ban.command else 'off'})"
            )

        if (kick := configuration.kick) and kick.status:
            entries.append(
                f"**kick** (do: {kick.punishment}, threshold: {kick.threshold}, cmd: {'on' if kick.command else 'off'})"
            )

        if (role := configuration.role) and role.status:
            entries.append(
                f"**role** (do: {role.punishment}, threshold: {role.threshold}, cmd: {'on' if role.command else 'off'})"
            )

        if (channel := configuration.channel) and channel.status:
            entries.append(
                f"**channel** (do: {channel.punishment}, threshold: {channel.threshold})"
            )

        if (emoji := configuration.emoji) and emoji.status:
            entries.append(
                f"**emoji** (do: {emoji.punishment}, threshold: {emoji.threshold})"
            )

        if (webhook := configuration.webhook) and webhook.status:
            entries.append(
                f"**webhook** (do: {webhook.punishment}, threshold: {webhook.threshold})"
            )

        if (botadd := configuration.botadd) and botadd.status:
            entries.append(f"**botadd** (do: {botadd.punishment})")

        for user_id in configuration.whitelist:
            user: Member = self.bot.get_user(user_id)

            entries.append(
                f"**{user or 'Unknown User'}** whitelisted (`{user_id}`) [`{'MEMBER' if not user.bot else 'BOT'}`]"
            )

        if not entries:
            return await ctx.fail("There are no **antinuke modules** enabled")

        return await ctx.paginate(
            Embed(
                title="Antinuke modules & whitelist",
            ),
            entries,
        )

    @antinuke.command(
        name="botadd",
        example=",antinuke botadd on --do ban",
        parameters=Parameters,
    )
    @trusted()
    async def antinuke_botadd(
        self, ctx: Context, status: Boolean, flags=None
    ) -> Message:
        """
        Prevent new bot additions
        """
        ctx.parameters = await get_parameters(ctx)
        await self.bot.db.execute(
            """
            INSERT INTO antinuke (
                guild_id,
                botadd
            ) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET
                botadd = EXCLUDED.botadd;
            """,
            ctx.guild.id,
            {
                "status": status,
                "punishment": ctx.parameters.get("punishment"),
            },
        )

        if status:
            return await ctx.success(
                "Updated **bot add** antinuke module."
                + (f"\nPunishment is set to **{ctx.parameters.get('punishment')}** ")
            )
        else:
            return await ctx.success("Disabled **bot add** antinuke module")

    @antinuke.command(
        name="webhook",
        example=",antinuke webhook on --do ban --threshold 3",
        parameters=Parameters,
    )
    @trusted()
    async def antinuke_webhook(
        self, ctx: Context, status: Boolean, flags=None
    ) -> Message:
        """
        Prevent mass webhook creation
        """
        ctx.parameters = await get_parameters(ctx)
        await self.bot.db.execute(
            """
            INSERT INTO antinuke (
                guild_id,
                webhook
            ) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET
                webhook = EXCLUDED.webhook;
            """,
            ctx.guild.id,
            {
                "status": status,
                "punishment": ctx.parameters.get("punishment"),
                "threshold": ctx.parameters.get("threshold"),
            },
        )

        if status:
            return await ctx.success(
                "Updated **webhook** antinuke module."
                + (
                    f"\nPunishment is set to **{ctx.parameters.get('punishment')}** "
                    f"and threshold is set to **{ctx.parameters.get('threshold')}**"
                )
            )
        else:
            return await ctx.success("Disabled **webhook** antinuke module")

    @antinuke.command(
        name="emoji",
        example=",antinuke emoji on --do kick --threshold 3",
        parameters=Parameters,
    )
    @trusted()
    async def antinuke_emoji(
        self, ctx: Context, status: Boolean, flags=None
    ) -> Message:
        """
        Prevent mass emoji delete
        Warning: This module may be unstable due to Discord's rate limit
        """
        ctx.parameters = await get_parameters(ctx)
        await self.bot.db.execute(
            """
            INSERT INTO antinuke (
                guild_id,
                emoji
            ) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET
                emoji = EXCLUDED.emoji;
            """,
            ctx.guild.id,
            {
                "status": status,
                "punishment": ctx.parameters.get("punishment"),
                "threshold": ctx.parameters.get("threshold"),
            },
        )

        if status:
            return await ctx.success(
                "Updated **emoji** antinuke module."
                + (
                    f"\nPunishment is set to **{ctx.parameters.get('punishment')}** "
                    f"and threshold is set to **{ctx.parameters.get('threshold')}**"
                )
            )
        else:
            return await ctx.success("Disabled **emoji** antinuke module")

    @antinuke.command(
        name="permissions",
        example=",antinuke permissions grant administrator",
        aliases=["perms"],
        parameters=Parameters,
    )
    @trusted()
    async def antinuke_permissions(
        self,
        ctx: Context,
        option: Literal["grant", "remove"],
        permission: str,
        flags: str = None,
    ) -> Message:
        """
        Watch for dangerous permissions being granted or removed
        """

        permission = permission.lower()
        if permission not in dangerous_permissions:
            return await ctx.fail(
                "You passed an **invalid permission name**, please visit the documentation [here](https://docs.bleed.bot/help/commands/antinuke/antinuke-permissions)"
            )

        permission: Dict = {
            "type": option,
            "permission": permission,
            "punishment": ctx.parameters.get("punishment"),
        }
        permissions: List[Dict] = (
            await self.bot.db.fetchval(
                """
            SELECT permissions FROM antinuke
            WHERE guild_id = $1;
            """,
                ctx.guild.id,
            )
            or []
        )

        for _permission in list(permissions):
            if _permission == permission:
                permissions.remove(permission)
                await self.bot.db.execute(
                    """
                    INSERT INTO antinuke (guild_id, permissions)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id) DO UPDATE
                    SET permissions = EXCLUDED.permissions;
                    """,
                    ctx.guild.id,
                    permissions,
                )

                return await ctx.success(
                    f"No longer monitoring **{'granting' if option == 'grant' else 'removal'} of** permission `{permission['permission']}`"
                )

            elif (_permission["type"] == option) and (
                _permission["permission"] == permission["permission"]
            ):
                permissions.remove(_permission)

        permissions.append(permission)

        await self.bot.db.execute(
            """
            INSERT INTO antinuke (guild_id, permissions)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
            SET permissions = EXCLUDED.permissions;
            """,
            ctx.guild.id,
            permissions,
        )
        ctx.parameters = await get_parameters(ctx)
        return await ctx.success(
            f"Now monitoring **{'granting' if option == 'grant' else 'removal'} of** permission `{permission['permission']}`. Members **manually** giving out roles to others will be punished with `{permission['punishment']}`"
        )

    @antinuke.command(
        name="ban",
        example=",antinuke ban on --do ban --command on",
        parameters=Parameters,
    )
    @trusted()
    async def antinuke_ban(self, ctx: Context, status: Boolean, flags=None) -> Message:
        """
        Prevent mass member ban
        """
        ctx.parameters = await get_parameters(ctx)
        await self.bot.db.execute(
            """
            INSERT INTO antinuke (
                guild_id,
                ban
            ) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET
                ban = EXCLUDED.ban;
            """,
            ctx.guild.id,
            {
                "status": status,
                "punishment": ctx.parameters.get("punishment"),
                "threshold": ctx.parameters.get("threshold"),
                "command": ctx.parameters.get("command"),
            },
        )

        if status:
            return await ctx.success(
                "Updated **ban** antinuke module."
                + (
                    f"\nPunishment is set to **{ctx.parameters.get('punishment')}**, "
                    f"threshold is set to **{ctx.parameters.get('threshold')}** "
                    f"and command detection is **{'on' if ctx.parameters.get('command') else 'off'}**"
                )
            )
        else:
            return await ctx.success("Disabled **ban** antinuke module")

    @antinuke.command(
        name="kick",
        example=",antinuke kick on --do stripstaff --threshold 3",
        parameters=Parameters,
    )
    @trusted()
    async def antinuke_kick(self, ctx: Context, status: Boolean, flags=None) -> Message:
        """
        Prevent mass member kick
        """
        ctx.parameters = await get_parameters(ctx)
        await self.bot.db.execute(
            """
            INSERT INTO antinuke (
                guild_id,
                kick
            ) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET
                kick = EXCLUDED.kick;
            """,
            ctx.guild.id,
            {
                "status": status,
                "punishment": ctx.parameters.get("punishment"),
                "threshold": ctx.parameters.get("threshold"),
                "command": ctx.parameters.get("command"),
            },
        )

        if status:
            return await ctx.success(
                "Updated **kick** antinuke module."
                + (
                    f"\nPunishment is set to **{ctx.parameters.get('punishment')}**, "
                    f"threshold is set to **{ctx.parameters.get('threshold')}** "
                    f"and command detection is **{'on' if ctx.parameters.get('command') else 'off'}**"
                )
            )
        else:
            return await ctx.success("Disabled **kick** antinuke module")

    @antinuke.command(
        name="channel",
        example=",antinuke channel on --do ban --threshold 3",
        parameters=Parameters,
    )
    @trusted()
    async def antinuke_channel(
        self, ctx: Context, status: Boolean, flags=None
    ) -> Message:
        """
        Prevent mass channel create and delete
        """

        await self.bot.db.execute(
            """
            INSERT INTO antinuke (
                guild_id,
                channel
            ) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET
                channel = EXCLUDED.channel;
            """,
            ctx.guild.id,
            {
                "status": status,
                "punishment": ctx.parameters.get("punishment"),
                "threshold": ctx.parameters.get("threshold"),
            },
        )

        if status:
            return await ctx.success(
                "Updated **channel** antinuke module."
                + (
                    f"\nPunishment is set to **{ctx.parameters.get('punishment')}** "
                    f"and threshold is set to **{ctx.parameters.get('threshold')}**"
                )
            )
        else:
            return await ctx.success("Disabled **channel** antinuke module")

    @antinuke.command(
        name="role",
        example=",antinuke role on --do ban --threshold 3",
        parameters=Parameters,
    )
    @trusted()
    async def antinuke_role(self, ctx: Context, status: Boolean, flags=None) -> Message:
        """
        Prevent mass role delete
        """
        ctx.parameters = await get_parameters(ctx)
        await self.bot.db.execute(
            """
            INSERT INTO antinuke (
                guild_id,
                role
            ) VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET
                role = EXCLUDED.role;
            """,
            ctx.guild.id,
            {
                "status": status,
                "punishment": ctx.parameters.get("punishment"),
                "threshold": ctx.parameters.get("threshold"),
                "command": ctx.parameters.get("command"),
            },
        )

        if status:
            return await ctx.success(
                "Updated **role** antinuke module."
                + (
                    f"\nPunishment is set to **{ctx.parameters.get('punishment')}**, "
                    f"threshold is set to **{ctx.parameters.get('threshold')}** "
                    f"and command detection is **{'on' if ctx.parameters.get('command') else 'off'}**"
                )
            )
        else:
            return await ctx.success("Disabled **role** antinuke module")


async def setup(bot: Client):
    await bot.add_cog(AntiNuke(bot))
