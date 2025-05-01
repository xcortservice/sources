from asyncio import Lock
from collections import defaultdict
from random import sample

from discord import (Client, Embed, Guild, RawReactionActionEvent, TextChannel,
                     utils)
from discord.ext import tasks
from discord.ext.commands import Cog
from loguru import logger
from system.classes.builtins import get_error
from system.classes.database import Record


class GiveawayEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.locks = defaultdict(Lock)

    async def cog_load(self):
        self.giveaway_check.start()

    async def cog_unload(self):
        self.giveaway_check.stop()

    @tasks.loop(seconds=10)
    async def giveaway_check(self):
        async with self.locks["giveaway"]:
            try:
                for giveaway in await self.bot.db.fetch(
                    """SELECT * FROM giveaways""", cached=False
                ):
                    if giveaway.win_message_id:
                        continue
                    if giveaway.expiration <= utils.utcnow():
                        channel = self.bot.get_channel(giveaway.channel_id)
                        if channel:
                            self.bot.dispatch(
                                "giveaway_end", channel.guild, channel, giveaway
                            )
                        else:
                            logger.info(
                                f"{giveaway.expiration.timestamp()} - {utils.utcnow().timestamp()}"
                            )
            except Exception as e:
                logger.error(f"Error in giveaway_check: {get_error(e)}")

    @Cog.listener("on_giveaway_end")
    async def giveaway_ended(
        self, guild: Guild, channel: TextChannel, giveaway: Record
    ):
        try:
            message = await channel.fetch_message(giveaway.message_id)
        except Exception:
            message = None
        valid_entries = []
        if len(giveaway.entries) == 0:
            await (
                message.reply("No entries for this giveaway.")
                if message
                else channel.send("No entries for this giveaway.")
            )

        for entry in giveaway.entries:
            if member := guild.get_member(entry):
                valid_entries.append(member)
        if len(valid_entries) < giveaway.winner_count:
            winners = valid_entries
        else:
            winners = sample(valid_entries, giveaway.winner_count)
        winners_string = ", ".join(m.mention for m in winners)
        hosts_string = ", ".join(f"<@!{u}>" for u in giveaway.hosts)
        embed = Embed(
            title="Giveaway Ended",
            description=f"The giveaway has ended.\n**Winners:** {winners_string}\n**Hosted By:** {hosts_string}",
        )
        win_message = await (
            message.reply(embed=embed) if message else channel.send(embed=embed)
        )
        await self.bot.db.execute(
            """UPDATE giveaways SET win_message_id = $1 WHERE message_id = $2""",
            win_message.id,
            giveaway.message_id,
        )

    @Cog.listener("on_raw_reaction_add")
    async def on_giveaway_enter(self, payload: RawReactionActionEvent):
        if str(payload.emoji) != "🎉":
            return
        if not (guild := self.bot.get_guild(payload.guild_id)):
            return
        if not (member := guild.get_member(payload.user_id)):
            return
        if member.bot:
            return
        if not (
            entries := await self.bot.db.fetchval(
                """SELECT entries FROM giveaways WHERE message_id = $1""",
                payload.message_id,
                cached=False,
            )
        ):
            entries = []
        if member.id in entries:
            return
        entries.append(member.id)
        await self.bot.db.execute(
            """UPDATE giveaways SET entries = $1 WHERE message_id = $2""",
            entries,
            payload.message_id,
        )

    @Cog.listener("on_raw_reaction_remove")
    async def on_giveaway_leave(self, payload: RawReactionActionEvent):
        if str(payload.emoji) != "🎉":
            return
        if not (guild := self.bot.get_guild(payload.guild_id)):
            return
        if not (member := guild.get_member(payload.user_id)):
            return
        if member.bot:
            return
        if not (
            entries := await self.bot.db.fetchval(
                """SELECT entries FROM giveaways WHERE message_id = $1""",
                payload.message_id,
            )
        ):
            return
        if member.id not in entries:
            return
        entries.remove(member.id)
        await self.bot.db.execute(
            """UPDATE giveaways SET entries = $1 WHERE message_id = $2""",
            entries,
            payload.message_id,
        )


async def setup(bot: Client):
    await bot.add_cog(GiveawayEvents(bot))
