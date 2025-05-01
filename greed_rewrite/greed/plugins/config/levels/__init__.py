import json
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from discord import Role, TextChannel, Message, Embed, VoiceState, Member
from discord.ext import commands, tasks
from greed.framework.discord.context import Context
from greed.framework.discord.parser import EmbedConverter
from greed.shared.config import Colors
from greed.framework.pagination import Paginator

logger = logging.getLogger("greed/plugins/config/levels")


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._voice_sessions: Dict[int, Dict[int, Dict]] = {}
        self._level_cache: Dict[int, Dict[int, int]] = {}

        self.cleanup_voice_sessions.start()
        self.process_voice_xp.start()

    async def get_settings(self, guild_id: int) -> Dict:
        cache_key = f"levels:settings:{guild_id}"
        if cached := await self.bot.redis.get(cache_key):
            return cached

        data = await self.bot.db.fetchval(
            """SELECT award_message, roles FROM text_level_settings WHERE guild_id = $1""",
            guild_id,
        )
        settings = json.loads(data) if data else {}
        await self.bot.redis.set(cache_key, settings, ex=3600)
        return settings

    async def get_voice_settings(self, guild_id: int) -> Dict:
        cache_key = f"levels:voice_settings:{guild_id}"
        if cached := await self.bot.redis.get(cache_key):
            return cached

        data = await self.bot.db.fetchrow(
            """SELECT * FROM voice_level_settings WHERE guild_id = $1""",
            guild_id,
        )
        settings = (
            dict(data)
            if data
            else {
                "enabled": True,
                "xp_per_minute": 5,
                "max_xp_per_session": 100,
                "min_voice_time": 1,
                "excluded_channels": [],
                "excluded_roles": [],
            }
        )
        await self.bot.redis.set(cache_key, settings, ex=3600)
        return settings

    async def get_xp(self, guild_id: int, user_id: int) -> int:
        cache_key = f"levels:xp:{guild_id}:{user_id}"
        if cached := await self.bot.redis.get(cache_key):
            return int(cached)

        xp = await self.bot.db.fetchval(
            """SELECT xp FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
            guild_id,
            user_id,
        )
        xp = xp or 0
        await self.bot.redis.set(cache_key, xp, ex=300)
        return xp

    async def add_xp(self, guild_id: int, user_id: int, amount: int) -> None:
        current_xp = await self.get_xp(guild_id, user_id)
        new_xp = current_xp + amount

        await self.bot.db.execute(
            """INSERT INTO text_levels (guild_id, user_id, xp) VALUES($1, $2, $3)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp""",
            guild_id,
            user_id,
            new_xp,
        )

        cache_key = f"levels:xp:{guild_id}:{user_id}"
        await self.bot.redis.set(cache_key, new_xp, ex=300)

    async def assign_level_role(self, ctx: Context, role: Role, level: int) -> None:
        xp_task = self.bot.levels.get_xp(level)
        xp = await xp_task.compute()

        async for rows in self.bot.db.fetch_iter(
            """SELECT user_id FROM text_levels WHERE guild_id = $1 AND xp >= $2""",
            ctx.guild.id,
            xp,
            chunk_size=100,
        ):
            for row in rows:
                if member := ctx.guild.get_member(row.user_id):
                    try:
                        await member.add_roles(role, reason="Level Role")
                    except Exception as e:
                        logger.error(
                            f"Failed to assign role {role.id} to user {member.id}: {e}"
                        )

    @commands.Cog.listener("on_message")
    async def on_message(self, message: Message):
        if message.mention_everyone:
            data = await self.bot.db.fetchrow(
                """SELECT channels, message FROM notifications WHERE guild_id = $1""",
                message.guild.id,
            )
            if data:
                if data.channels:
                    channels = (
                        data.channels
                        if isinstance(data.channels, list)
                        else [data.channels]
                    )
                    if message.channel.id in channels:
                        return await self.bot.send_embed(
                            destination=message.channel,
                            code=data.message,
                            user=message.author,
                        )
                else:
                    logger.error("No channels found in the database.")

    @commands.group(
        name="levels",
        brief="setup level roles and autoboard",
        invoke_without_command=True,
        aliases=["lvls"],
    )
    async def levels(self, ctx: Context):
        return await ctx.send_help()

    @levels.command(
        name="channel",
        brief="set a channel for level award messages",
        example=",levels channel #txt",
        usage=",levels channel <channel>",
    )
    @commands.has_permissions(manage_guild=True)
    async def levels_channel(self, ctx: Context, *, channel: TextChannel):
        data = await self.get_settings(ctx.guild.id)
        data["channel_id"] = channel.id
        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id, award_message) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET award_message = excluded.award_message""",
            ctx.guild.id,
            json.dumps(data),
        )
        return await ctx.embed(
            f"**Messages for leveling** will now be sent to {channel.mention}",
            "approved",
        )

    @levels.command(name="enable", brief="enable leveling")
    @commands.has_permissions(manage_guild=True)
    async def levels_enable(self, ctx: Context):
        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id) VALUES($1) ON CONFLICT(guild_id) DO NOTHING""",
            ctx.guild.id,
        )
        return await ctx.embed("Successfully enabled leveling", "approved")

    @levels.command(name="disable", brief="disable leveling")
    @commands.has_permissions(manage_guild=True)
    async def levels_disable(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM text_level_settings WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.embed("Successfully disabled leveling", "approved")

    @levels.group(
        name="message",
        brief="set a message for leveling up",
        example=",levels message {embed}{description: congrats {user.mention} for hitting level {level}}",
        usage=",levels message <message>",
        invoke_without_command=True,
        aliases=["msg", "m"],
    )
    @commands.has_permissions(manage_guild=True)
    async def levels_message(self, ctx: Context, *, message: EmbedConverter):
        data = await self.get_settings(ctx.guild.id)
        data["message"] = message
        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id, award_message) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET award_message = excluded.award_message""",
            ctx.guild.id,
            json.dumps(data),
        )
        return await ctx.embed(
            "The **award message** for leveling has been **applied**", "approved"
        )

    @levels_message.command(
        name="test",
        brief="test your level up message",
        aliases=["debug", "t", "try", "view"],
    )
    @commands.has_permissions(manage_guild=True)
    async def levels_message_test(self, ctx: Context):
        data = await self.get_settings(ctx.guild.id)
        if not data.get("channel_id"):
            return await ctx.embed(
                "You **have not** created a **level channel**", "denied"
            )
        if not data.get("message"):
            return await ctx.embed(
                "You **have not** created a **level message**", "denied"
            )
        self.bot.dispatch("text_level_up", ctx.guild, ctx.author, 1)
        return await ctx.embed(
            "Your created **level message** has been sent", "approved"
        )

    @levels_message.command(
        name="reset", brief="reset your level message configuration", aliases=["clear"]
    )
    @commands.has_permissions(manage_guild=True)
    async def levels_message_reset(self, ctx: Context):
        try:
            await self.bot.db.execute(
                """UPDATE text_level_settings SET award_message = NULL WHERE guild_id = $1""",
                ctx.guild.id,
            )
        except Exception:
            pass
        return await ctx.embed(
            "Your **level message** has been **cleared**", "approved"
        )

    @levels.group(
        name="role",
        brief="add level roles to be awarded",
        usage=",levels role <level> <role>",
        example=",levels role 5 level-5",
        invoke_without_command=True,
    )
    @commands.has_permissions(manage_guild=True)
    async def levels_role(self, ctx: Context, level: int, *, role: Role):
        role = role[0]
        data = await self.get_settings(ctx.guild.id)
        if [level, role.id] not in data.get("roles", []):
            data["roles"] = data.get("roles", []) + [[level, role.id]]
            await self.bot.db.execute(
                """INSERT INTO text_level_settings (guild_id, roles) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET roles = excluded.roles""",
                ctx.guild.id,
                json.dumps(data),
            )
            await self.assign_level_role(ctx, role, level)
        return await ctx.embed(
            f"{role.mention} will now be **given to users** who reach **level {level}**",
            "approved",
        )

    @levels_role.command(
        name="remove",
        brief="remove a level role",
        usage=",levels role remove <level> <role>",
        example=",levels role remove 5 level-5",
        aliases=["r", "rem", "del", "delete"],
    )
    @commands.has_permissions(manage_guild=True)
    async def levels_role_remove(self, ctx: Context, level: int):
        data = await self.get_settings(ctx.guild.id)
        new = [d for d in data.get("roles", []) if d[0] != level]

        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id, roles) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET roles = excluded.roles""",
            ctx.guild.id,
            json.dumps(data),
        )
        return await ctx.embed(
            f"All **reward roles has been cleared** for **level {level}**", "approved"
        )

    @levels.command(
        name="list", brief="show all level rewards", aliases=["show", "l", "ls", "s"]
    )
    @commands.has_permissions(manage_guild=True)
    async def levels_list(self, ctx: Context):
        data = await self.get_settings(ctx.guild.id)
        roles = data.get("roles", [])
        rows = []
        skipped = 0
        for i, d in enumerate(roles, start=1):
            role = ctx.guild.get_role(d[1])
            if not role:
                skipped += 1
                continue
            level = d[0]
            rows.append(f"`{i - skipped}` {role.mention} - `{level}`")

        if not rows:
            return await ctx.embed("You have **not set any reward levels**", "denied")

        embed = Embed(color=Colors().information, title="Level Rewards")
        await Paginator(ctx, rows, embed=embed).start()

    @levels.command(name="setup", brief="setup leveling")
    @commands.has_permissions(manage_guild=True)
    async def levels_setup(self, ctx: Context):
        await self.bot.db.execute(
            """INSERT INTO text_level_settings (guild_id) VALUES($1) ON CONFLICT(guild_id) DO NOTHING""",
            ctx.guild.id,
        )
        return await ctx.embed("**Leveling** has been **enabled**", "approved")

    @tasks.loop(minutes=5)
    async def process_voice_xp(self):
        current_time = datetime.utcnow()
        for guild_id, sessions in self._voice_sessions.items():
            settings = await self.get_voice_settings(guild_id)
            if not settings["enabled"]:
                continue

            for user_id, session in sessions.items():
                if current_time - session["last_xp_gain"] < timedelta(minutes=1):
                    continue

                time_spent = (current_time - session["start_time"]).total_seconds() / 60
                if time_spent < settings["min_voice_time"]:
                    continue

                xp_to_add = min(
                    settings["xp_per_minute"],
                    settings["max_xp_per_session"] - session["xp_gained"],
                )

                if xp_to_add > 0:
                    await self.add_xp(guild_id, user_id, xp_to_add)
                    session["xp_gained"] += xp_to_add
                    session["last_xp_gain"] = current_time

    @tasks.loop(hours=1)
    async def cleanup_voice_sessions(self):
        current_time = datetime.utcnow()
        for guild_id, sessions in list(self._voice_sessions.items()):
            for user_id, session in list(sessions.items()):
                if current_time - session["start_time"] > timedelta(hours=24):
                    del sessions[user_id]
            if not sessions:
                del self._voice_sessions[guild_id]

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ):
        if member.bot:
            return

        guild_id = member.guild.id
        settings = await self.get_voice_settings(guild_id)

        if not settings["enabled"]:
            return

        if any(role.id in settings["excluded_roles"] for role in member.roles):
            return

        if not before.channel and after.channel:
            if after.channel.id in settings["excluded_channels"]:
                return

            if guild_id not in self._voice_sessions:
                self._voice_sessions[guild_id] = {}

            self._voice_sessions[guild_id][member.id] = {
                "channel_id": after.channel.id,
                "start_time": datetime.utcnow(),
                "last_xp_gain": datetime.utcnow(),
                "xp_gained": 0,
            }

        elif before.channel and not after.channel:
            if (
                guild_id in self._voice_sessions
                and member.id in self._voice_sessions[guild_id]
            ):
                del self._voice_sessions[guild_id][member.id]
                if not self._voice_sessions[guild_id]:
                    del self._voice_sessions[guild_id]

    @levels.group(name="voice", brief="configure voice leveling")
    async def levels_voice(self, ctx: Context):
        return await ctx.send_help()

    @levels_voice.command(name="enable", brief="enable voice leveling")
    @commands.has_permissions(manage_guild=True)
    async def voice_enable(self, ctx: Context):
        await self.bot.db.execute(
            """INSERT INTO voice_level_settings (guild_id, enabled) VALUES($1, true)
               ON CONFLICT(guild_id) DO UPDATE SET enabled = true""",
            ctx.guild.id,
        )
        return await ctx.embed("Voice leveling has been enabled", "approved")

    @levels_voice.command(name="disable", brief="disable voice leveling")
    @commands.has_permissions(manage_guild=True)
    async def voice_disable(self, ctx: Context):
        await self.bot.db.execute(
            """UPDATE voice_level_settings SET enabled = false WHERE guild_id = $1""",
            ctx.guild.id,
        )
        return await ctx.embed("Voice leveling has been disabled", "approved")

    @levels_voice.command(name="settings", brief="view voice leveling settings")
    @commands.has_permissions(manage_guild=True)
    async def voice_settings(self, ctx: Context):
        settings = await self.get_voice_settings(ctx.guild.id)
        embed = Embed(title="Voice Leveling Settings", color=Colors().information)
        embed.add_field(
            name="Status",
            value="Enabled" if settings["enabled"] else "Disabled",
            inline=False,
        )
        embed.add_field(
            name="XP per Minute", value=str(settings["xp_per_minute"]), inline=True
        )
        embed.add_field(
            name="Max XP per Session",
            value=str(settings["max_xp_per_session"]),
            inline=True,
        )
        embed.add_field(
            name="Minimum Voice Time (minutes)",
            value=str(settings["min_voice_time"]),
            inline=True,
        )
        return await ctx.send(embed=embed)

    async def get_leaderboard(self, guild_id: int, limit: int = 10, sort_by: str = "total") -> List[Tuple[int, int, int, int]]:
        cache_key = f"levels:leaderboard:{guild_id}:{sort_by}"
        if cached := await self.bot.redis.get(cache_key):
            return json.loads(cached)

        if sort_by == "total":
            text_rows = await self.bot.db.fetch(
                """SELECT user_id, xp FROM text_levels WHERE guild_id = $1 ORDER BY xp DESC LIMIT $2""",
                guild_id,
                limit,
            )
            voice_rows = await self.bot.db.fetch(
                """SELECT user_id, xp FROM voice_levels WHERE guild_id = $1 ORDER BY xp DESC LIMIT $2""",
                guild_id,
                limit,
            )
            xp_dict = {}
            for row in text_rows:
                xp_dict[row["user_id"]] = xp_dict.get(row["user_id"], 0) + row["xp"]
            for row in voice_rows:
                xp_dict[row["user_id"]] = xp_dict.get(row["user_id"], 0) + row["xp"]
            leaderboard = sorted(xp_dict.items(), key=lambda x: x[1], reverse=True)[:limit]
        elif sort_by == "text":
            rows = await self.bot.db.fetch(
                """SELECT user_id, xp FROM text_levels WHERE guild_id = $1 ORDER BY xp DESC LIMIT $2""",
                guild_id,
                limit,
            )
            leaderboard = [(row["user_id"], row["xp"]) for row in rows]
        elif sort_by == "voice":
            rows = await self.bot.db.fetch(
                """SELECT user_id, xp FROM voice_levels WHERE guild_id = $1 ORDER BY xp DESC LIMIT $2""",
                guild_id,
                limit,
            )
            leaderboard = [(row["user_id"], row["xp"]) for row in rows]
        else:
            return []

        await self.bot.redis.set(cache_key, json.dumps(leaderboard), ex=300)
        return leaderboard

    async def get_user_stats(self, guild_id: int, user_id: int) -> Dict[str, int]:
        cache_key = f"levels:stats:{guild_id}:{user_id}"
        if cached := await self.bot.redis.get(cache_key):
            return json.loads(cached)

        text_data = await self.bot.db.fetchrow(
            """SELECT xp, msgs FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
            guild_id,
            user_id,
        )
        voice_data = await self.bot.db.fetchrow(
            """SELECT xp, time_spent FROM voice_levels WHERE guild_id = $1 AND user_id = $2""",
            guild_id,
            user_id,
        )

        stats = {
            "text_xp": text_data["xp"] if text_data else 0,
            "text_messages": text_data["msgs"] if text_data else 0,
            "voice_xp": voice_data["xp"] if voice_data else 0,
            "voice_time": voice_data["time_spent"] if voice_data else 0,
            "total_xp": (text_data["xp"] if text_data else 0) + (voice_data["xp"] if voice_data else 0)
        }

        await self.bot.redis.set(cache_key, json.dumps(stats), ex=300)
        return stats

    @levels.command(
        name="leaderboard", 
        brief="show level leaderboard", 
        aliases=["lb", "top"],
        usage=",levels leaderboard [total|text|voice] [limit]"
    )
    async def levels_leaderboard(self, ctx: Context, sort_by: str = "total", limit: int = 10):
        if limit < 1 or limit > 25:
            return await ctx.embed("Limit must be between 1 and 25", "denied")
        
        if sort_by not in ["total", "text", "voice"]:
            return await ctx.embed("Sort type must be one of: total, text, voice", "denied")

        leaderboard = await self.get_leaderboard(ctx.guild.id, limit, sort_by)
        if not leaderboard:
            return await ctx.embed("No level data available", "denied")

        rows = []
        for i, (user_id, xp) in enumerate(leaderboard, 1):
            if member := ctx.guild.get_member(user_id):
                rows.append(f"`{i}` {member.mention} - `{xp:,} XP`")

        embed = Embed(color=Colors().information, title=f"Level Leaderboard ({sort_by.title()} XP)")
        await Paginator(ctx, rows, embed=embed).start()

    @levels.command(
        name="stats",
        brief="view user level stats",
        aliases=["stat", "profile", "rank"],
        usage=",levels stats [user]"
    )
    async def levels_stats(self, ctx: Context, member: Optional[Member] = None):
        member = member or ctx.author
        stats = await self.get_user_stats(ctx.guild.id, member.id)

        embed = Embed(
            color=Colors().information,
            title=f"{member.name}'s Level Stats",
            description=f"Total XP: `{stats['total_xp']:,}`"
        )
        
        embed.add_field(
            name="Text Stats",
            value=f"XP: `{stats['text_xp']:,}`\nMessages: `{stats['text_messages']:,}`",
            inline=True
        )
        
        embed.add_field(
            name="Voice Stats",
            value=f"XP: `{stats['voice_xp']:,}`\nTime Spent: `{stats['voice_time']:,} minutes`",
            inline=True
        )

        return await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Levels(bot))
