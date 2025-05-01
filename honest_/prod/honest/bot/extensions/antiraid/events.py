from asyncio import Lock
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from discord import Client, Embed, File, Guild, Member, User, utils
from discord.ext.commands import (Cog, CommandError, Context, command, group,
                                  has_permissions)
from system.classes.database import Record


class AntiRaidEvents(Cog):
    def __init__(self: "AntiRaidEvents", bot: Client):
        self.bot = bot
        self.locks = defaultdict(Lock)

    async def check_member(
        self,
        member: Member,
        guild: Guild,
        config: Record,
        dispatch: Optional[bool] = True,
    ) -> tuple:
        whitelist = config.whitelist or []
        if config.raid_status is True and member.id not in whitelist:
            if datetime.now() > config.raid_expires_at:
                await self.bot.db.execute(
                    """UPDATE antiraid SET raid_triggered_at = NULL, raid_expires_at = NULL WHERE guild_id = $1""",
                    guild.id,
                )
            else:
                return True, config.join_punishment, "Raid is active"
        if member.id in whitelist:
            return False, None, None
        if (
            config.new_accounts is True
            and member.created_at
            < datetime.now() - timedelta(days=config.new_account_threshold)
        ):
            return True, config.new_account_punishment, "New Account"
        if config.no_avatar and not member.avatar:
            return True, config.no_avatar_punishment, "No Avatar"
        if (
            await self.bot.object_cache.ratelimited(
                f"raid:{guild.id}", config.join_threshold, 60
            )
            != 0
        ):
            expiration = datetime.now() + timedelta(minutes=10)
            await self.bot.db.execute(
                """INSERT INTO antiraid (guild_id, raid_status, raid_triggered_at, raid_expires_at) VALUES($1, $2, $3, $4) ON CONFLICT(guild_id) DO UPDATE SET raid_status = excluded.raid_status, raid_triggered_at = excluded.raid_triggered_at, raid_expires_at = excluded.raid_expires_at""",
                guild.id,
                True,
                datetime.now(),
                expiration,
            )
            self.bot.dispatch("raid", member, guild, expiration)
            return True, config.join_punishment, "Mass Join"

        return False, None, None

    # @Cog.listener("on_member_join")
    # async def on_new_member(self, member: Member):
    #     guild = member.guild
    #     async def execute():
    #         if not (config := await self.bot.db.fetchrow("""SELECT * FROM antiraid WHERE guild_id = $1""", guild.id)):
    #             return False
    #         value = False
    #         async with self.locks[f"antiraid:{guild.id}"]:
    #             punish, punishment_value, reason = await self.check_member(member, guild, config)
    #             if punish:
    #                 if punishment_value == 1:
    #                     await member.kick(reason = reason)
    #                     value = True
    #                 else:
    #                     await member.ban(reason = reason)
    #                     value = True
    #         return value
    #     _ = await execute()
    #     if not _:
    #         if not member.pending:
    #             self.bot.dispatch(
    #                 "member_agree",
    #                 member,
    #             )

    @Cog.listener("on_member_update")
    async def on_accepted(self, before: Member, after: Member):
        if before.pending and not after.pending:
            self.bot.dispatch("member_agree", after)

    @Cog.listener("on_raid")
    async def new_raid(self, member: Member, guild: Guild, expiration: datetime):
        try:
            await guild.owner.send(
                embed=Embed(
                    title="RAID",
                    description=f"your server {guild.name} (`{guild.id}`) is being raided, the raid will expire at {utils.format_dt(expiration, style='R')}",
                )
            )
        except Exception:
            pass


async def setup(bot: Client):
    await bot.add_cog(AntiRaidEvents(bot))
