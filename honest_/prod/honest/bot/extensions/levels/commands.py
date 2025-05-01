import asyncio
from typing import Optional, Union

import orjson
from discord import Client, Embed, Guild, Member, Role, TextChannel, User
from discord.ext.commands import (Author, Boolean, Cog, CommandError,
                                  Converter, EmbedConverter,
                                  GuildChannelConverter, TextChannelConverter,
                                  command, group, has_permissions,
                                  hybrid_command, hybrid_group)
from loguru import logger
from system.patch.context import Context
from tools import lock


async def convert(ctx: Context, argument: str):
    try:
        if m := await TextChannelConverter().convert(ctx, argument):
            return m
    except Exception:
        pass
    return await GuildChannelConverter().convert(ctx, argument)


DISABLED_ARGS = ["NONE", "FALSE", "RESET", "DISABLE", "D"]
DM_ARGS = ["PM", "DM"]


class MessageMode(Converter):
    async def convert(self, ctx: Context, argument: str):
        logger.info(f"{type(argument)} - {argument}")
        if argument.upper() in DISABLED_ARGS:
            return "DISABLED"
        elif argument.upper() in DM_ARGS:
            return "DM"
        else:
            raise CommandError(f"argument `{argument}` is not a valid mode")


def boolean_to_emoji(ctx: Context, boolean: bool):
    if boolean:
        return ctx.bot.config["emojis"]["success"]
    return ctx.bot.config["emojis"]["fail"]


class Levels(Cog, name="Levels"):
    def __init__(self, bot: Client):
        self.bot = bot

    @group(
        name="levels",
        description="setup the leveling system or view a user's level",
        invoke_without_command=True,
        aliases=["lvls", "level", "rank", "rnk"],
    )
    async def levels(self, ctx: Context, *, member: Optional[Member] = Author):
        if not await self.bot.levels.check_guild(ctx.guild):
            return await ctx.fail(
                f"**leveling system** is disabled in this server - use `{ctx.prefix}levels unlock` to enable"
            )
        return await self.bot.levels.get_member_xp(ctx, member)

    @lock("assign_level_role:{ctx.guild.id}")
    async def assign_level_role(self, ctx: Context, role: Role, level: int):
        settings = await self.bot.levels.get_settings(ctx.guild)
        user_statistics = {
            member: await self.bot.levels.get_statistics(member)
            for member in ctx.guild.members
        }
        try:
            roles = sorted(
                orjson.loads(
                    await self.bot.db.fetchval(
                        """SELECT roles FROM text_level_settings WHERE guild_id = $1""",
                        ctx.guild.id,
                    )
                ),
                key=lambda x: x[0],
                reverse=True,
            )
            role_ids = [r[1] for r in roles]
        except Exception:
            pass
        required = self.bot.levels.get_xp(level, settings)
        for member, stats in user_statistics.items():
            level = self.bot.levels.get_level(stats[0], settings)
            if not settings.roles_stack:
                if stats[0] > required:
                    await member.add_roles(role, reason="Level Role")
            else:
                try:
                    for level, role_id in roles:
                        if level >= level:
                            roles = [r for r in member.roles if r.id not in role_ids]
                            roles.append(ctx.guild.get_role(role_id))
                            await member.edit(roles=roles, reason="Level Role")
                except Exception:
                    pass

    async def get_level(self, member: Member) -> int:
        settings = await self.bot.levels.get_settings(member.guild)
        stats = await self.bot.levels.get_statistics(member)
        return self.bot.levels.get_level(stats[0], settings)

    @levels.group(
        name="message",
        description="set a message for leveling up",
        example=",levels message {embed}{description: congrats {user.mention} for hitting level {level}}",
        usage=",levels message <message>",
        invoke_without_command=True,
        aliases=["msg", "m"],
    )
    @has_permissions(manage_guild=True)
    async def levels_message(self, ctx: Context, *, message: EmbedConverter):
        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id, award_message) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET award_message = excluded.award_message""",
            ctx.guild.id,
            message,
        )
        return await ctx.success(
            "The **award message** for leveling has been **applied**"
        )

    @levels_message.command(
        name="view",
        description="View the level up message for the server",
        aliases=["debug", "t", "try", "test", "show"],
    )
    @has_permissions(manage_guild=True)
    async def levels_message_view(self, ctx: Context):
        data = await self.bot.levels.get_settings(
            ctx.guild
        )  # await self.bot.db.fetchval("""SELECT award_message FROM text_level_settings WHERE guild_id = $1""", ctx.guild.id)
        if not data:
            return await ctx.fail("You **have not** created a **level message**")
        if not data.channel_id:
            return await ctx.fail("You **have not** created a **level channel**")
        if not data.award_message:
            return await ctx.fail("You **have not** created a **level message**")
        self.bot.dispatch("text_level_up", ctx.guild, ctx.author, 1)
        return await ctx.success("Your created **level message** has been sent")

    @levels.command(
        name="messagemode",
        description="Set up where level up messages will be sent",
        example=",levels messagemode CUSTOM",
    )
    @has_permissions(manage_guild=True)
    async def levels_messagemode(
        self, ctx: Context, *, mode: Union[TextChannel, MessageMode]
    ):
        if not isinstance(mode, str):
            await self.bot.db.execute(
                """INSERT INTO text_level_settings (guild_id, award_message_mode, channel_id) VALUES($1, $2, $3) ON CONFLICT(guild_id) DO UPDATE SET award_message_mode = excluded.award_message_mode, channel_id = excluded.channel_id""",
                ctx.guild.id,
                "CUSTOM",
                mode.id,
            )
            return await ctx.success(
                f"successfully set your message mode to **CUSTOM** with the channel {mode.mention}"
            )
        else:
            await self.bot.db.execute(
                """INSERT INTO text_level_settings (guild_id, award_message_mode) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET award_message_mode = excluded.award_message_mode""",
                ctx.guild.id,
                mode.upper(),
            )
        return await ctx.success(
            f"successfully set your message mode to `{mode.upper()}`"
        )

    @levels.command(
        name="messages",
        description="Toggle level up messages for yourself",
        example=",levels messages True",
    )
    async def levels_messages(self, ctx: Context, setting: Optional[Boolean] = None):
        if setting is None:
            setting = await self.bot.db.fetchval(
                """SELECT messages_enabled FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
                ctx.guild.id,
                ctx.author.id,
                cached=False,
            )
            if setting is None:
                setting = True
            if setting:
                setting = False
            else:
                setting = True
        try:
            await self.bot.db.execute(
                """UPDATE text_levels SET messages_enabled = $1 WHERE guild_id = $2 AND user_id = $3""",
                setting,
                ctx.guild.id,
                ctx.author.id,
            )
        except Exception:
            await self.bot.db.execute(
                """INSERT INTO text_levels (guild_id, user_id, messages_enabled, xp) VALUES($1, $2, $3, $4)""",
                ctx.guild.id,
                ctx.author.id,
                setting,
                0,
            )
        return await ctx.success(
            f"successfully {'**ENABLED**' if setting else '**DISABLED**'} your level up messages"
        )

    @levels.command(
        name="ignore",
        description="Ignore a channel or role for XP",
        example=",levels ignore @blacklisted",
    )
    @has_permissions(manage_guild=True)
    async def levels_ignore(
        self, ctx: Context, *, target: Union[Role, GuildChannelConverter]
    ):
        settings = orjson.loads(
            await self.bot.db.fetchval(
                """SELECT ignored FROM text_level_settings WHERE guild_id = $1""",
                ctx.guild.id,
            )
            or b"[]"
        )
        if target.id in settings:
            ignored = False
            settings.remove(target.id)
        else:
            ignored = True
            settings.append(target.id)
        await self.bot.db.execute(
            """UPDATE text_level_settings SET ignored = $1 WHERE guild_id = $2""",
            orjson.dumps(settings),
            ctx.guild.id,
        )
        return await ctx.success(
            f"successfully **{f'REMOVED** {target.mention} from the ignored list' if not ignored else f'ADDED** {target.mention} to the ignored list'}"
        )

    @levels.command(name="lock", description="Disable leveling system")
    @has_permissions(manage_guild=True)
    async def levels_lock(self, ctx: Context):
        locked = await self.bot.db.fetchval(
            """SELECT locked FROM text_level_settings WHERE guild_id = $1""",
            ctx.guild.id,
        )
        if locked:
            return await ctx.fail("**leveling system** is already disabled.")
        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id, locked) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET locked = excluded.locked""",
            ctx.guild.id,
            True,
        )
        return await ctx.success(
            f"Disabled the **leveling system** - use `{ctx.prefix}levels unlock` to revert."
        )

    @levels.command(name="unlock", description="Enable leveling system")
    @has_permissions(manage_guild=True)
    async def levels_unlock(self, ctx: Context):
        locked = await self.bot.db.fetchval(
            """SELECT locked FROM text_level_settings WHERE guild_id = $1""",
            ctx.guild.id,
        )
        if locked is False:
            return await ctx.fail("The **leveling system** is already enabled.")

        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id, locked) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET locked = excluded.locked""",
            ctx.guild.id,
            False,
        )
        return await ctx.success(
            f"Enabled **leveling system** - use `{ctx.prefix}levels lock` to revert."
        )

    @levels.command(
        name="reset",
        description="Reset all levels and configurations",
    )
    @has_permissions(manage_guild=True)
    async def levels_reset(self, ctx: Context):
        tasks = [
            self.bot.db.execute(
                """DELETE FROM text_level_settings WHERE guild_id = $1""", ctx.guild.id
            ),
            self.bot.db.execute(
                """DELETE FROM text_levels WHERE guild_id = $1""", ctx.guild.id
            ),
        ]
        await ctx.confirm("are you sure you want to reset **all** level data?")
        await asyncio.gather(*tasks)

    @levels.command(name="sync", description="sync your level roles for your members")
    @has_permissions(manage_guild=True)
    async def levels_sync(self, ctx: Context):
        data = orjson.loads(
            await self.bot.db.fetchval(
                """SELECT roles FROM text_level_settings WHERE guild_id = $1""",
                ctx.guild.id,
            )
            or "[]"
        )
        if len(data) == 0:
            raise CommandError("you have no level roles setup")
        user_statistics = {
            member: await self.bot.levels.get_statistics(member)
            for member in ctx.guild.members
        }
        settings = await self.bot.levels.get_settings(ctx.guild)
        message = await ctx.normal("Syncing level roles this may take a while...")
        for level, role in data:
            required_xp = self.bot.levels.get_xp(level, settings)
            tasks = [
                u.add_roles(ctx.guild.get_role(role))
                for u, stats in user_statistics.items()
                if stats[0] >= required_xp and ctx.guild.get_role(role) not in u.roles
            ]
            for task in tasks:
                await task
        return await message.edit(
            embed=await ctx.success(
                "successfully synced all level roles", return_embed=True
            )
        )

    @levels.command(
        name="stackroles", description="Enable or disable stacking of roles"
    )
    @has_permissions(manage_guild=True)
    async def levels_stackroles(self, ctx: Context, *, option: Boolean):
        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id, roles_stack) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET roles_stack = excluded.roles_stack""",
            ctx.guild.id,
            option,
        )
        return await ctx.success(
            f"successfully **{'DISABLED' if not option else 'ENABLED'}** level role stacking"
        )

    @command(
        name="setxp",
        description="Set a user's experience",
        example=",setxp @aiohttp 154",
    )
    @has_permissions(manage_guild=True)
    async def setxp(self, ctx: Context, member: Member, xp: int):
        await self.bot.db.execute(
            """INSERT INTO text_levels (guild_id, user_id, xp) VALUES($1, $2, $3) ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp""",
            ctx.guild.id,
            member.id,
            xp,
        )
        return await ctx.success(
            f"successfully set {member.mention}'s **XP** to `{xp}`"
        )

    @command(
        name="removexp",
        description="Remove experience from a user",
        example=",removexp @aiohttp 13",
    )
    @has_permissions(manage_guild=True)
    async def removexp(self, ctx: Context, member: Member, xp: int):
        old_xp = (
            await self.bot.db.fetchval(
                """SELECT xp FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
                ctx.guild.id,
                member.id,
            )
            or xp
        )
        new_xp = old_xp - xp
        await self.bot.db.execute(
            """UPDATE text_levels SET xp = $1 WHERE guild_id = $2 AND user_id = $3""",
            new_xp,
            ctx.guild.id,
            member.id,
        )
        return await ctx.success(f"{member.mention}'s XP is now `{new_xp}`")

    @command(
        name="setlevel",
        description="Set a user's level",
        example=",setlevel @aiohttp 3",
    )
    @has_permissions(manage_guild=True)
    async def setlevel(self, ctx: Context, member: Member, level: int):
        settings = await self.bot.levels.get_settings(ctx.guild)
        needed_xp = self.bot.levels.get_xp(level, settings)
        await self.bot.db.execute(
            """INSERT INTO text_levels (guild_id, user_id, xp) VALUES($1, $2, $3) ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp""",
            ctx.guild.id,
            member.id,
            needed_xp,
        )
        return await ctx.success(
            f"successfully set {member.mention}'s level to {level}"
        )

    @levels.command(
        name="leaderboard",
        aliases=["lb"],
        description="View the highest ranking members",
    )
    async def levels_leaderboard(self, ctx: Context):
        settings = await self.bot.levels.get_settings(ctx.guild)
        users = await self.bot.levels.get_rank(ctx.guild, ctx.author)
        rows_ = [
            f"**{ctx.guild.get_member(k).name}** is **Level {self.bot.levels.get_level(v[0], settings)}** (`{int(v[0])} XP`)"
            for k, v in users.items()
            if ctx.guild.get_member(k) and int(v[0]) > 0
        ]
        rows = [f"`{i}` {r}" for i, r in enumerate(rows_, start=1)]
        if not rows:
            raise CommandError("There are no level entries for this server")
        embed = Embed(title="Highest ranking members").set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
        )
        return await ctx.paginate(embed, rows)

    @levels.command(
        name="add",
        description="Create level role",
        usage=",levels role <level> <role>",
        example=",levels add level-5 5",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def levels_add(self, ctx: Context, role: Role, rank: int):
        data = orjson.loads(
            await self.bot.db.fetchval(
                """SELECT roles FROM text_level_settings WHERE guild_id = $1""",
                ctx.guild.id,
            )
            or "[]"
        )
        if [rank, role.id] not in data:
            data.append([rank, role.id])
            await self.bot.db.execute(
                """INSERT INTO text_level_settings (guild_id, roles) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET roles = excluded.roles""",
                ctx.guild.id,
                orjson.dumps(data),
            )
            await self.assign_level_role(ctx, role, rank)
        return await ctx.success(
            f"{role.mention} will now be **given to users** who reach **level {rank}**"
        )

    @levels.command(
        name="remove",
        description="remove a level role",
        usage=",levels remove <level> <role>",
        example=",levels role remove 5 level-5",
        aliases=["r", "rem", "del", "delete"],
    )
    @has_permissions(manage_guild=True)
    async def levels_role_remove(self, ctx: Context, level: int):
        data = orjson.loads(
            await self.bot.db.fetchval(
                """SELECT roles FROM text_level_settings WHERE guild_id = $1""",
                ctx.guild.id,
            )
            or "[]"
        )
        new = []
        for d in data:
            if d[0] != level:
                new.append(d)
            await self.bot.db.execute(
                """INSERT INTO text_level_settings (guild_id, roles) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET roles = excluded.roles""",
                ctx.guild.id,
                orjson.dumps(new),
            )
        return await ctx.success(
            f"All **reward roles has been cleared** for **level {level}**"
        )

    @levels.command(
        name="roles",
        description="show all level rewards",
        aliases=["rls", "rl", "show", "l", "ls", "s"],
    )
    @has_permissions(manage_guild=True)
    async def levels_roles(self, ctx: Context):
        rows = []
        data = orjson.loads(
            await self.bot.db.fetchval(
                """SELECT roles FROM text_level_settings WHERE guild_id = $1""",
                ctx.guild.id,
            )
            or "[]"
        )
        ii = 0
        for i, d in enumerate(data, start=1):
            role = ctx.guild.get_role(d[1])
            if not role:
                ii += 1
                continue
            level = d[0]
            rows.append(f"`{i - ii}` {role.mention} - `{level}`")
        if len(rows) == 0:
            return await ctx.fail("You have **not set any reward levels**")
        embed = Embed(color=self.bot.color, title="Level Rewards")
        return await ctx.paginate(embed, rows)

    @levels.command(
        name="setrate",
        description="Set multiplier for XP gain",
        example=",levels setrate 0.5",
    )
    @has_permissions(manage_guild=True)
    async def levels_setrate(self, ctx: Context, multiplier: Union[int, float]):
        multiplier = float(multiplier)
        if multiplier < 0.0:
            raise CommandError("You can't have a **multiplier** lower than 0")
        if multiplier > 3.0:
            raise CommandError("You can't have a **multiplier** higher than `3`")
        multiplier = 0.05 * multiplier
        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id, multiplier) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET multiplier = excluded.multiplier""",
            ctx.guild.id,
            multiplier,
        )
        return await ctx.success(
            f"successfully set the multiplier to `{int(multiplier / 0.05)}`"
        )

    @levels.command(name="cleanup", description="Reset level & XP for absent members")
    @has_permissions(manage_guild=True)
    async def levels_cleanup(self, ctx: Context):
        users = (
            await self.bot.db.fetch(
                """SELECT user_id FROM text_levels WHERE guild_id = $1""", ctx.guild.id
            )
            or []
        )
        tasks = []
        for user in users:
            if not ctx.guild.get_member(user.user_id):
                tasks.append(
                    self.bot.db.execute(
                        """DELETE FROM text_levels WHERE user_id = $1 AND guild_id = $2""",
                        user.user_id,
                        ctx.guild.id,
                    )
                )
        await asyncio.gather(*tasks)
        return await ctx.success(
            f"successfully cleaned up **{len(tasks)}** non guild member level entries"
        )

    @levels.command(name="list", description="View all ignored channels and roles")
    @has_permissions(manage_guild=True)
    async def levels_list(self, ctx: Context):
        data = await self.bot.db.fetchval(
            """SELECT ignored FROM text_level_settings WHERE guild_id = $1""",
            ctx.guild.id,
        )
        if not data:
            raise CommandError("there are no ignored targets")

        def get_row(target: int):
            if role := ctx.guild.get_role(target):
                return f"{role.mention} (role)"
            elif channel := ctx.guild.get_channel(target):
                return f"{channel.mention} (channel)"
            else:
                return None

        rows = [get_row(t) for t in orjson.loads(data) if get_row(t)]
        rows = [f"`{i}` {row}" for i, row in enumerate(rows, start=1)]
        embed = Embed(title="Blocked channels and roles").set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
        )
        return await ctx.paginate(embed, rows)

    @levels.command(
        name="config",
        aliases=["settings", "cfg"],
        description="View server configuration for Leveling system",
    )
    @has_permissions(manage_guild=True)
    async def levels_config(self, ctx: Context):
        try:
            settings = await self.bot.levels.get_settings(ctx.guild)
        except Exception:
            if not settings:
                return await ctx.fail("No settings found")
        embed = Embed(
            title="Settings",
            description=(
                "Level system is **enabled** in this server"
                if not settings.locked
                else "Level system is **disabled** in this server"
            ),
        ).set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
        )
        no_xp_roles = 0
        no_xp_channels = 0
        lrc = 0
        if settings.ignored:
            for target in settings.ignored:
                if ctx.guild.get_role(target):
                    no_xp_roles += 1
                elif ctx.guild.get_channel(target):
                    no_xp_channels += 1
                else:
                    continue
        if settings.roles:
            for role in settings.roles:
                lrc += 1
        general_value = f"**No-XP Roles:** {no_xp_roles}\n**Ignored Channels:** {no_xp_channels}\n**Level Role Count:** {lrc}\n**Level Multiplier:** {int(settings.multiplier / 0.05)}\n**Message Mode:** {(settings.award_message_mode or 'DM').upper()}\n**Level Up Channel:** {settings.get_channel(ctx.guild, True)}\n**Stack Roles:** {boolean_to_emoji(ctx, settings.roles_stack)}"
        embed.add_field(name="General", value=general_value, inline=False)
        return await ctx.send(embed=embed)


async def setup(bot: Client):
    await bot.add_cog(Levels(bot))
