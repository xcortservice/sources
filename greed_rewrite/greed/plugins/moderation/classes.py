import psutil
import datetime
import discord
import humanize
import json

from typing import Union, Optional
from logging import getLogger
from typing import Dict, Union
from datetime import timedelta
from enum import Enum

from discord import Member, User, Embed
from discord.ext import commands

from greed.framework import Greed, Context
from greed.framework.script import Script
from greed.shared.config import ContextEmojis

log = getLogger("greed/moderation/classes")


def process_mod_action(
    action_data: Dict[str, Union[str, int, timedelta, None]],
) -> Dict[str, str]:
    """
    Process moderation action data in a separate process.
    """
    action = action_data["action"]
    duration = action_data.get("duration")

    action_title = (
        "hardunbanned"
        if action == "hardunban"
        else (
            "hardbanned"
            if action == "hardban"
            else (
                "banned"
                if action == "ban"
                else (
                    "unbanned"
                    if action == "unban"
                    else (
                        "kicked"
                        if action == "kick"
                        else (
                            "jailed"
                            if action == "jail"
                            else (
                                "unjailed"
                                if action == "unjail"
                                else (
                                    "muted"
                                    if action == "mute"
                                    else (
                                        "unmuted"
                                        if action == "unmute"
                                        else (
                                            "warned"
                                            if action == "warn"
                                            else (
                                                "punished"
                                                if action.startswith("antinuke")
                                                else (
                                                    "punished"
                                                    if action.startswith("antiraid")
                                                    else action + "ed"
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
    )

    result = {
        "title": action_title,
        "is_unaction": action.startswith("un"),
        "is_antinuke": action.startswith("antinuke"),
        "is_antiraid": action.startswith("antiraid"),
        "should_dm": action not in ("timeout", "untimeout"),
    }
    return result


def process_dm_script(dm_data: Dict):
    """
    Process DM notification in a separate process.
    """
    try:
        settings = dm_data["settings"]
        action = dm_data["action"]
        author_name = dm_data["author_name"]
        guild_name = dm_data["guild_name"]
        victim_id = dm_data["victim_id"]
        reason = dm_data["reason"]
        duration = dm_data["duration"]
        role_name = dm_data.get("role_name")
        processed_action = dm_data["processed_action"]

        script = settings.get(f"dm_{action.lower()}")

        if action in ["role_add", "role_remove"]:
            return {
                "success": True,
                "victim_id": victim_id,
                "embed_data": {
                    "title": f"Role {'Added' if action == 'role_add' else 'Removed'}",
                    "color": 0x00FF00 if action == "role_add" else 0xFF0000,
                    "fields": [
                        {
                            "name": "Server",
                            "value": guild_name,
                            "inline": True,
                        },
                        {
                            "name": "Role",
                            "value": role_name,
                            "inline": True,
                        },
                        {
                            "name": "Moderator",
                            "value": author_name,
                            "inline": True,
                        },
                        (
                            {
                                "name": "Reason",
                                "value": reason,
                                "inline": False,
                            }
                            if reason
                            else None
                        ),
                    ],
                },
            }
        else:
            duration_text = f"{duration}" if duration else ""
            return {
                "success": True,
                "victim_id": victim_id,
                "embed_data": {
                    "title": processed_action["title"].title(),
                    "description": duration_text,
                    "color": 0x00FF00 if processed_action["is_unaction"] else 0xFF0000,
                    "fields": [
                        {
                            "name": f"You have been {processed_action['title']} in",
                            "value": guild_name,
                            "inline": True,
                        },
                        {
                            "name": "Moderator",
                            "value": author_name,
                            "inline": True,
                        },
                        {
                            "name": "Reason",
                            "value": reason,
                            "inline": True,
                        },
                    ],
                },
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


class CaseType(Enum):
    bans = "bans"
    kicks = "kicks"
    unbans = "unbans"
    jails = "jails"
    unjails = "unjails"
    unmutes = "unmutes"
    mutes = "mutes"
    warns = "warns"


async def store_statistics_background(
    bot: Greed,
    guild_id: int,
    moderator_id: int,
    action: str,
) -> None:
    """
    Store moderation statistics in the background.
    """
    try:
        case_type = None
        if action == "ban":
            case_type = CaseType.bans
        elif action == "kick":
            case_type = CaseType.kicks
        elif action == "unban":
            case_type = CaseType.unbans
        elif action == "jail":
            case_type = CaseType.jails
        elif action == "unjail":
            case_type = CaseType.unjails
        elif action == "unmute":
            case_type = CaseType.unmutes
        elif action == "mute":
            case_type = CaseType.mutes
        elif action == "warn":
            case_type = CaseType.warns
        else:
            return

        existing_data = await bot.db.fetchval(
            """SELECT data FROM moderation_statistics WHERE guild_id = $1 AND user_id = $2""",
            guild_id,
            moderator_id,
        )
        try:
            data = json.loads(existing_data) if existing_data else {}
        except (json.JSONDecodeError, TypeError):
            data = {}

        name = str(case_type.name)
        if not data.get(name):
            data[name] = 1
        else:
            data[name] += 1

        try:
            json_data = json.dumps(data)
        except (TypeError, ValueError):
            json_data = "{}"

        await bot.db.execute(
            """INSERT INTO moderation_statistics (guild_id, user_id, data) 
            VALUES($1, $2, $3) ON CONFLICT(guild_id, user_id) 
            DO UPDATE SET data = $3""",
            guild_id,
            moderator_id,
            json_data,
        )
    except Exception as e:
        log.error(f"Error storing moderation statistics: {e}")


class Mod:
    def is_mod_configured():
        """
        Checks if the moderation system is configured in the guild.
        """

        async def predicate(ctx: Context):
            if not ctx.command:
                return False

            required_perms = []
            for check in ctx.command.checks:
                if hasattr(check, "perms"):
                    required_perms.extend(
                        perm for perm, value in check.perms.items() if value
                    )

            if required_perms:
                missing_perms = [
                    perm
                    for perm in required_perms
                    if not getattr(ctx.author.guild_permissions, perm)
                ]
                if missing_perms:
                    perm_name = missing_perms[0].replace("_", " ").title()
                    await ctx.embed(
                        f"You're missing the **{perm_name}** permission!",
                        message_type="warned",
                    )
                    return False

            check = await ctx.bot.pool.fetchrow(
                """
                SELECT * FROM mod 
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )

            if not check:
                await ctx.embed(
                    "Moderation isn't enabled in this server!\n"
                    f"-# Enable it using `{ctx.clean_prefix}setme` command",
                    message_type="warned",
                )
                return False

            return True

        return commands.check(predicate)


class ModConfig:
    """
    Contains methods for sending moderation logs and storing statistics.
    """

    @staticmethod
    async def get_statistics(
        bot: Greed,
        guild_id: int,
        moderator_id: int,
    ) -> Dict:
        """
        Get moderation statistics for a moderator.
        """
        data = await bot.db.fetchval(
            """SELECT data FROM moderation_statistics WHERE guild_id = $1 AND user_id = $2""",
            guild_id,
            moderator_id,
        )
        if data:
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    async def sendlogs(
        bot: Greed,
        action: str,
        author: Member,
        victim: Union[Member, User],
        reason: str,
        duration: Union[timedelta, int, None] = None,
        role: discord.Role = None,
    ):
        try:
            bot.loop.create_task(
                store_statistics_background(
                    bot,
                    author.guild.id,
                    author.id,
                    action,
                )
            )

            settings = await bot.db.fetchrow(
                """SELECT channel_id FROM moderation_channel WHERE guild_id = $1""",
                author.guild.id,
            )

            if not settings:
                return

            res = await bot.db.fetchrow(
                """SELECT count FROM cases WHERE guild_id = $1""",
                author.guild.id,
            )

            if not res:
                await bot.db.execute(
                    """INSERT INTO cases (guild_id, count) VALUES ($1, $2)""",
                    author.guild.id,
                    0,
                )
                case = 1
            else:
                case = int(res["count"]) + 1

            await bot.db.execute(
                """UPDATE cases SET count = $1 WHERE guild_id = $2""",
                case,
                author.guild.id,
            )

            duration_value = (
                int(duration.total_seconds())
                if isinstance(duration, timedelta)
                else duration
            )

            await bot.db.execute(
                """INSERT INTO moderation.history 
                (guild_id, case_id, user_id, moderator_id, action, reason, duration, role_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                author.guild.id,
                case,
                victim.id if victim else None,
                author.id,
                action,
                reason,
                duration_value,
                role.id if role else None,
            )

            mod_channel_id = settings.get("channel_id")
            if mod_channel_id:
                mod_channel = author.guild.get_channel(int(mod_channel_id))
                if mod_channel:
                    embed = Embed(
                        timestamp=datetime.datetime.now(),
                        color=(
                            discord.Color.green()
                            if action
                            in [
                                "role_add",
                                "unban",
                                "untimeout",
                                "unjail",
                            ]
                            else (
                                discord.Color.red()
                                if action
                                in [
                                    "ban",
                                    "kick",
                                    "timeout",
                                    "jail",
                                ]
                                else (
                                    discord.Color.green()
                                    if action == "role_add"
                                    else (
                                        discord.Color.red()
                                        if action == "role_remove"
                                        else discord.Color.blurple()
                                    )
                                )
                            )
                        ),
                    )
                    embed.set_author(
                        name="Modlog Entry",
                        icon_url=author.display_avatar,
                    )

                    if action in ["role_add", "role_remove"]:
                        embed.add_field(
                            name="Information",
                            value=f"**Case #{case}** | {action}\n**User**: {victim} (`{victim.id}`)\n**Moderator**: {author} (`{author.id}`)\n**Role**: {role.mention}\n**Reason**: {reason}",
                        )
                    else:
                        duration_text = (
                            f"\n**Duration**: {humanize.naturaldelta(duration)}"
                            if duration
                            else ""
                        )
                        embed.add_field(
                            name="Information",
                            value=f"**Case #{case}** | {action}\n**User**: {victim} (`{victim.id if victim else 'N/A'}`)\n**Moderator**: {author} (`{author.id}`)\n**Reason**: {reason}{duration_text}",
                        )

                    try:
                        await mod_channel.send(embed=embed)
                    except discord.HTTPException:
                        pass

            try:
                properties = {
                    "action": action,
                    "guild_id": str(author.guild.id),
                    "guild_name": author.guild.name,
                    "moderator_id": str(author.id),
                    "moderator_name": str(author),
                    "moderator_roles": [str(role.id) for role in author.roles[1:]],
                    "target_id": str(victim.id) if victim else None,
                    "target_name": str(victim) if victim else None,
                    "reason": reason,
                    "case_id": case,
                    "duration_seconds": (
                        int(duration.total_seconds())
                        if isinstance(duration, timedelta)
                        else duration if isinstance(duration, int) else None
                    ),
                    "role_id": str(role.id) if role else None,
                    "role_name": role.name if role else None,
                    "system_metrics": {
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_usage": psutil.Process().memory_info().rss
                        / 1024
                        / 1024,
                        "thread_count": psutil.Process().num_threads(),
                    },
                    "guild_metrics": {
                        "member_count": author.guild.member_count,
                        "case_count": case,
                        "verification_level": str(author.guild.verification_level),
                        "boost_level": author.guild.premium_tier,
                    },
                }

            except Exception as e:
                print(f"Error in modlog: {e}")
                import traceback

                traceback.print_exc()

        except Exception as e:
            print(f"Error in modlog: {e}")
            import traceback

            traceback.print_exc()


class ClearMod(discord.ui.View):
    def __init__(self, ctx: Context):
        super().__init__()
        self.ctx = ctx
        self.status = False

    @discord.ui.button(emoji=ContextEmojis().approved)
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.embed("You are not the author of this embed!")

        jail_data = await interaction.client.db.fetchrow(
            """SELECT role_id FROM jail_config WHERE guild_id = $1""",
            interaction.guild.id,
        )

        mod_data = await interaction.client.db.fetchrow(
            """SELECT channel_id FROM mod WHERE guild_id = $1""",
            interaction.guild.id,
        )

        if jail_data and (role := interaction.guild.get_role(jail_data["role_id"])):
            try:
                await role.delete()
            except discord.HTTPException:
                pass

        if mod_data and (
            channel := interaction.guild.get_channel(mod_data["channel_id"])
        ):
            try:
                await channel.delete()
            except discord.HTTPException:
                pass

        await interaction.client.db.execute(
            """DELETE FROM jail_config WHERE guild_id = $1""",
            interaction.guild.id,
        )
        await interaction.client.db.execute(
            """DELETE FROM mod WHERE guild_id = $1""",
            interaction.guild.id,
        )

        self.status = True
        return await interaction.response.edit_message(
            view=None,
            embed=Embed(
                description="I have disabled the moderation system.",
            ),
        )

    @discord.ui.button(emoji=ContextEmojis().denied)
    async def deny(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.embed("You are not the author of this embed!")

        await interaction.response.edit_message(
            embed=Embed(description="Aborting action"),
            view=None,
        )
        self.status = True

    async def on_timeout(self) -> None:
        if self.status == False:
            for item in self.children:
                item.disabled = True

            await self.message.edit(view=self)
