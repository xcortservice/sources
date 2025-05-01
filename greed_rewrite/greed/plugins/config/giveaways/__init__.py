from discord import Message, Guild, Object, Role, Embed
from discord.ext.commands import Cog, has_permissions, hybrid_group
from discord.ext import tasks
from datetime import datetime, timedelta
import humanfriendly
import random
import discord
import logging
from typing import Optional, Union, List, Dict, Any
from .views import GiveawayView
from asyncio import Lock
from greed.framework.script import Script
import traceback
from collections import defaultdict

from greed.framework import Context, Greed

logger = logging.getLogger("greed/giveaways")


def get_tb(error: Exception) -> str:
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


class Giveaway(Cog):
    def __init__(self, bot: Greed):
        self.bot = bot
        self.entry_updating = False
        self._locks = {}
        self._init_locks()

    def _init_locks(self) -> None:
        self._locks["gw"] = Lock()
        self._locks["entries"] = Lock()

    @property
    def locks(self) -> Dict[str, Lock]:
        if not self._locks:
            self._init_locks()
        return self._locks

    async def setup_hook(self) -> None:
        self._init_locks()
        self.giveaway_loop.start()
        self.cleanup_loop.start()

    def cog_unload(self) -> None:
        self.giveaway_loop.cancel()
        self.cleanup_loop.cancel()
        self._locks.clear()

    @hybrid_group(name="giveaway", aliases=["gw"], invoke_without_command=True)
    async def giveaway(self, ctx: Context) -> None:
        return await ctx.send_help(ctx.command)

    @giveaway.command(
        name="blacklist",
        brief="Blacklist a role from entering giveaways",
        example=",giveaway blacklist @members",
    )
    @has_permissions(manage_guild=True)
    async def giveaway_blacklist(self, ctx: Context, *, role: Role) -> None:
        role = role[0]
        if await self.bot.db.fetchrow(
            """SELECT * FROM giveaway_blacklist WHERE guild_id = $1 AND role_id = $2""",
            ctx.guild.id,
            role.id,
        ):
            await self.bot.db.execute(
                """DELETE FROM giveaway_blacklist WHERE guild_id = $1 AND role_id = $2""",
                ctx.guild.id,
                role.id,
            )
            m = f"**Unblacklisted** users with {role.mention} and can now **enter giveaways**"
        else:
            await self.bot.db.execute(
                """INSERT INTO giveaway_blacklist (guild_id, role_id) VALUES($1, $2) ON CONFLICT(guild_id, role_id) DO NOTHING""",
                ctx.guild.id,
                role.id,
            )
            m = f"**Blacklisted** users with {role.mention} role from **entering giveaways**"
        return await ctx.embed(m, "approved")

    async def get_int(self, string: str) -> str:
        return "".join(s for s in string if s.isdigit())

    async def get_timeframe(self, timeframe: str) -> datetime:
        try:
            converted = humanfriendly.parse_timespan(timeframe)
        except Exception:
            converted = humanfriendly.parse_timespan(
                f"{await self.get_int(timeframe)} hours"
            )
        return datetime.now() + timedelta(seconds=converted)

    async def get_winners(
        self, entries: List[Dict[str, Any]], amount: int
    ) -> List[int]:
        if not entries:
            logger.warning("No entries found for giveaway")
            return []

        weighted_entries = []
        for entry in entries:
            weighted_entries.extend([entry["user_id"]] * entry["entry_count"])

        if not weighted_entries:
            logger.warning("No weighted entries after processing")
            return []

        if amount >= len(weighted_entries):
            return list(set(weighted_entries))

        winners = random.sample(weighted_entries, amount)
        return winners

    async def get_config(
        self,
        guild: Guild,
        prize: str,
        message_id: int,
        winners: str,
        winners_str: str,
        winner_objects: List[discord.Member],
        creator: int,
        ends: datetime,
    ) -> Dict[str, Any]:
        _creator = self.bot.get_user(creator)
        embed = Embed(
            title="Giveaway Ended", description=f"**Prize**: {prize}\n**Winners**:\n"
        )
        desc = (
            "\n".join(
                f"`{i}` {winner.mention}"
                for i, winner in enumerate(winner_objects, start=1)
            )
            or "**No one entered**"
        )
        embed.description += desc
        content = winners
        self.bot.gwdesc = embed.description

        config = await self.bot.db.fetchrow(
            """SELECT * FROM giveaway_config WHERE guild_id = $1""", guild.id
        ) or {"guild_id": guild.id, "dm_creator": False, "dm_winners": False}

        if winners is not None:
            if config["dm_creator"]:
                try:
                    await _creator.send(content=content, embed=embed)
                except Exception:
                    pass
            if config["dm_winners"]:
                for w in winner_objects:
                    try:
                        await w.send(content=content, embed=embed)
                    except Exception:
                        pass
        return {"embed": embed, "content": content}

    async def get_message(
        self,
        guild: Guild,
        prize: str,
        end_time: datetime,
        winners: int,
        creator: discord.Member,
        message: discord.Message,
        required_role: Optional[Role] = None,
    ) -> Dict[str, Any]:
        if template := await self.bot.db.fetchrow(
            """SELECT * FROM giveaway_templates WHERE guild_id = $1""", guild.id
        ):
            code = template["code"]
            code = code.replace("{prize}", prize)
            code = code.replace("{ends}", discord.utils.format_dt(end_time, style="R"))
            if required_role:
                code = code.replace("{role}", required_role.mention)
            script = Script(code, creator)
            await script.compile()
            return script.data
        else:
            ends_timestamps = f"{self.bot.get_timestamp(end_time)} ({self.bot.get_timestamp(end_time, 'f')})"
            embed = Embed(
                title=prize,
                description=f"**Winners:** {winners}\n**Ends:** {ends_timestamps}",
                color=0x2F3136,
            )
            if required_role:
                embed.description += f"\n**Required Role:** {required_role.mention}"
            embed.set_footer(text=f"hosted by {str(creator)}")
            return {"embed": embed, "content": None}

    async def fetch_message(
        self, guild: Union[int, discord.Guild], channel_id: int, message_id: int
    ) -> Optional[discord.Message]:
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
            if not guild:
                return None
        channel = guild.get_channel(channel_id)
        if not channel:
            return None
        try:
            return await channel.fetch_message(message_id)
        except Exception:
            return None

    async def end_giveaway(self, message: Message, winners: int, prize: str) -> None:
        await self.bot.db.execute(
            """INSERT INTO ended_giveaways 
            (guild_id, message_id, channel_id, prize, winner_count, creator_id, ended_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            message.guild.id,
            message.id,
            message.channel.id,
            prize,
            winners,
            await self.get_creator_id(message.id),
            datetime.now(),
        )

        embed = Embed(
            title="<:giveaway:1356908120273588265> Giveaway Ended",
            description=f"**Prize:** {prize}\n**Winners:** {winners}",
            color=0x2F3136,
        )
        await message.edit(embed=embed, view=None)

    async def get_creator_id(self, message_id: int) -> Optional[int]:
        return await self.bot.db.fetchval(
            "SELECT creator FROM gw WHERE message_id = $1", message_id
        )

    @tasks.loop(minutes=1)
    async def giveaway_loop(self) -> None:
        try:
            await self.do_gw()
        except Exception as e:
            logger.error(f"Uncaught exception in giveaway loop: {get_tb(e)}")

    @giveaway_loop.before_loop
    async def before_giveaway_loop(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def cleanup_loop(self) -> None:
        try:
            five_days_ago = datetime.now() - timedelta(days=5)
            old_giveaways = await self.bot.db.fetch(
                """SELECT guild_id, message_id FROM ended_giveaways 
                WHERE ended_at < $1""",
                five_days_ago,
            )

            for gw in old_giveaways:
                await self.bot.db.execute(
                    """DELETE FROM giveaway_entries 
                    WHERE guild_id = $1 AND message_id = $2""",
                    gw["guild_id"],
                    gw["message_id"],
                )
                await self.bot.db.execute(
                    """DELETE FROM ended_giveaways 
                    WHERE guild_id = $1 AND message_id = $2""",
                    gw["guild_id"],
                    gw["message_id"],
                )
        except Exception as e:
            logger.error(f"Error in cleanup loop: {get_tb(e)}")

    async def do_gw(self) -> None:
        async with self.locks["gw"]:
            active_giveaways = await self.bot.db.fetch(
                """SELECT * FROM gw WHERE ex <= NOW()"""
            )

            if not active_giveaways:
                return

            for gw in active_giveaways:
                guild = self.bot.get_guild(gw["guild_id"])
                if not guild:
                    logger.warning(f"Guild {gw['guild_id']} not found")
                    continue

                channel = guild.get_channel(gw["channel_id"])
                if not channel:
                    logger.warning(
                        f"Channel {gw['channel_id']} not found in guild {guild.id}"
                    )
                    continue

                try:
                    message = await channel.fetch_message(gw["message_id"])
                    prize = gw["prize"]
                except Exception as e:
                    logger.error(f"Failed to fetch giveaway message: {e}")
                    continue

                entries = await self.bot.db.fetch(
                    """SELECT user_id, entry_count FROM giveaway_entries 
                    WHERE guild_id = $1 AND message_id = $2""",
                    guild.id,
                    message.id,
                )

                winners = await self.get_winners(entries, gw["winner_count"])
                winner_objects = [
                    guild.get_member(w) for w in winners if guild.get_member(w)
                ]

                config = await self.bot.db.fetchrow(
                    """SELECT * FROM giveaway_config WHERE guild_id = $1""", guild.id
                ) or {"guild_id": guild.id, "dm_creator": False, "dm_winners": False}

                embed = Embed(
                    title=f"<:giveaway:1356908120273588265> Giveaway Ended: {prize}",
                    description="**Winners**\n"
                    + "\n".join(
                        [f"{i+1}. {w.mention}" for i, w in enumerate(winner_objects)]
                        or ["No valid winners"]
                    ),
                    color=0x2F3136,
                )

                try:
                    await channel.send(
                        content=(
                            f"Congratulations {' '.join([w.mention for w in winner_objects])}!"
                            if winner_objects
                            else ""
                        ),
                        embed=embed,
                    )

                    if config["dm_creator"]:
                        if creator := self.bot.get_user(gw["creator"]):
                            try:
                                await creator.send(
                                    content=f"Your giveaway for **{prize}** has ended!",
                                    embed=embed,
                                )
                            except Exception as e:
                                logger.error(f"Failed to DM creator: {e}")

                    if config["dm_winners"]:
                        for w in winner_objects:
                            try:
                                await w.send(
                                    content=f"You won the giveaway for **{prize}**!",
                                    embed=embed,
                                )
                            except Exception as e:
                                logger.error(f"Failed to DM winner {w.id}: {e}")

                except discord.HTTPException as e:
                    logger.error(f"Failed to send giveaway end message: {e}")

                await self.end_giveaway(message, gw["winner_count"], prize)
                await self.bot.db.execute(
                    """DELETE FROM gw WHERE message_id = $1""", message.id
                )

    @giveaway.command(
        name="start",
        aliases=["create"],
        brief="Create a giveaway",
        example=",giveaway start 1h 1 $10 @role",
    )
    @has_permissions(manage_guild=True)
    async def giveaway_start(
        self,
        ctx: Context,
        duration: str,
        winners: int = 1,
        role: Optional[Role] = None,
        *,
        prize: str,
    ) -> None:
        end_time = await self.get_timeframe(duration)
        message = await ctx.send("Starting giveaway...", view=GiveawayView())

        await self.bot.db.execute(
            """INSERT INTO gw 
            (guild_id, channel_id, message_id, ex, creator, winner_count, prize, required_role) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            ctx.guild.id,
            ctx.channel.id,
            message.id,
            end_time,
            ctx.author.id,
            winners,
            prize,
            role.id if role else None,
        )

        embed = await self.get_message(
            ctx.guild, prize, end_time, winners, ctx.author, message, role
        )
        await message.edit(**embed)
        await ctx.embed("Giveaway started successfully!", "approved")

    @giveaway.command(
        name="reroll",
        brief="Reroll giveaway winners",
        example=",giveaway reroll 1234567890",
    )
    @has_permissions(manage_guild=True)
    async def reroll(self, ctx: Context, message_id: int) -> None:
        ended_gw = await self.bot.db.fetchrow(
            """SELECT * FROM ended_giveaways 
            WHERE guild_id = $1 AND message_id = $2""",
            ctx.guild.id,
            message_id,
        )

        if not ended_gw:
            return await ctx.embed(
                "No ended giveaway found with that message ID.", "denied"
            )

        entries = await self.bot.db.fetch(
            """SELECT user_id, entry_count FROM giveaway_entries 
            WHERE guild_id = $1 AND message_id = $2""",
            ctx.guild.id,
            message_id,
        )

        if not entries:
            return await ctx.embed("No entries found for this giveaway.", "denied")

        winners = await self.get_winners(entries, ended_gw["winner_count"])
        winners = [winners] if not isinstance(winners, list) else winners

        winner_objects = []
        for w in winners:
            if member := ctx.guild.get_member(w):
                winner_objects.append(member)

        if not winner_objects:
            return await ctx.embed("No valid winners found.", "denied")

        embed = Embed(
            title=f"<:giveaway:1356908120273588265> Reroll: {ended_gw['prize']}",
            description="**New Winners**\n"
            + "\n".join([f"{i+1}. {w.mention}" for i, w in enumerate(winner_objects)]),
            color=0x2F3136,
        )

        channel = ctx.guild.get_channel(ended_gw["channel_id"])
        if channel:
            try:
                await channel.send(
                    content=f"New winners: {' '.join([w.mention for w in winner_objects])}",
                    embed=embed,
                )
                await ctx.embed("Successfully rerolled winners!", "approved")
            except discord.HTTPException as e:
                await ctx.embed(f"Failed to send reroll message: {e}", "denied")
        else:
            await ctx.embed("Original channel not found.", "denied")

    @giveaway.command(
        name="end",
        brief="End a specific giveaway from that giveaway message",
        aliases=["stop"],
        example=",giveaway end 1234567890",
    )
    @has_permissions(manage_guild=True)
    async def giveaway_end(
        self, ctx: Context, message_id: Optional[int] = None
    ) -> None:
        data = await self.bot.db.fetch(
            """SELECT * FROM gw WHERE guild_id = $1""", ctx.guild.id
        )
        if not data:
            return await ctx.embed("**no giveaway found**", "denied")
        if len(data) == 1:
            message_id = data[0].message_id
        if message_id is None:
            if ctx.message.reference:
                message_id = ctx.message.reference.message_id
        if message_id is None:
            return await ctx.embed(
                "please include the message id of the giveaway", "denied"
            )

        try:
            await self.bot.db.execute(
                """UPDATE gw SET ex = $1 WHERE guild_id = $2 AND message_id = $3""",
                datetime.now(),
                ctx.guild.id,
                message_id,
            )
        except Exception:
            return await ctx.embed(
                f"**No giveaway found** under `{message_id}`", "denied"
            )
        return await ctx.embed("**Giveaway will end in a few moments!**", "approved")

    @giveaway.command(
        name="dmcreator",
        brief="Dm the creator when the giveaway has ended of the winner(s)",
        example=",giveaway dmcreator true",
    )
    @has_permissions(manage_guild=True)
    async def giveaway_dmcreator(self, ctx: Context, state: bool) -> None:
        await self.bot.db.execute(
            """INSERT INTO giveaway_config (guild_id, dm_creator, dm_winners) 
            VALUES($1, $2, $3) 
            ON CONFLICT(guild_id) DO UPDATE SET dm_creator = excluded.dm_creator""",
            ctx.guild.id,
            state,
            False,
        )
        return await ctx.embed(f"**Dmcreator** is now set to `{state}`", "approved")

    @giveaway.command(
        name="dmwinners",
        aliases=["dmwinner"],
        brief="dm the winners when the giveaway has ended",
        example=",giveaway dmwinners true",
    )
    @has_permissions(manage_guild=True)
    async def giveaway_dmwinner(self, ctx: Context, state: bool) -> None:
        await self.bot.db.execute(
            """INSERT INTO giveaway_config (guild_id, dm_creator, dm_winners) 
            VALUES($1, $2, $3) 
            ON CONFLICT(guild_id) DO UPDATE SET dm_winners = excluded.dm_winners""",
            ctx.guild.id,
            False,
            state,
        )
        return await ctx.embed(f"**DmWinners** is now set to `{state}`", "approved")

    @giveaway.command(
        name="template",
        brief="set your default embed template for giveaways",
        example=",giveaway template [embed_code]",
    )
    @has_permissions(manage_guild=True)
    async def giveaway_template(
        self, ctx: Context, *, template: Optional[str] = None
    ) -> None:
        if template is None:
            await self.bot.db.execute(
                """DELETE FROM giveaway_templates WHERE guild_id = $1""", ctx.guild.id
            )
            m = "**Giveaway template** has been cleared"
        else:
            await self.bot.db.execute(
                """INSERT INTO giveaway_templates (guild_id, code) 
                VALUES($1, $2) 
                ON CONFLICT(guild_id) DO UPDATE SET code = excluded.code""",
                ctx.guild.id,
                template,
            )
            m = "Giveaway template** is now set to the **embed code provided**"
        return await ctx.embed(m, "approved")

    @giveaway.command(
        name="setmax",
        brief="Set a max entrie count users with a specific role",
        aliases=["max"],
        example=",giveaway setmax 100",
    )
    @has_permissions(manage_roles=True)
    async def giveaway_setmax(self, ctx: Context, max: int, *, role: Role) -> None:
        role = role[0]
        await self.bot.db.execute(
            """INSERT INTO giveaway_settings (guild_id, role_id, entries) 
            VALUES($1, $2, $3) 
            ON CONFLICT(guild_id, role_id) DO UPDATE SET entries = excluded.entries""",
            ctx.guild.id,
            role.id,
            max,
        )
        return await ctx.embed(
            f"{role.mention}'s **max entries** set to `{max}` for **entering giveaways**",
            "approved",
        )


async def setup(bot: Greed) -> None:
    cog = Giveaway(bot)
    await bot.add_cog(cog)
