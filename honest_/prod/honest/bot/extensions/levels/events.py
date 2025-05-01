import json

from discord import Client, Guild, Member
from discord.ext.commands import Cog
from loguru import logger


class LevelEvents(Cog):
    def __init__(self: "LevelEvents", bot: Client):
        self.bot = bot

    @Cog.listener("on_text_level_up")
    async def on_level_up(self, guild: Guild, member: Member, level: int):
        settings = await self.bot.levels.get_settings(guild)

        async def do_roles():
            if not settings.roles:
                return
            new_roles = member.roles
            for entry in settings.roles:
                role_level, role_id = entry
                role = guild.get_role(role_id)
                if not role:
                    continue
                if level < role_level or level != role_level:
                    if not settings.roles_stack:
                        if role in member.roles:
                            new_roles.remove(role)
                if level >= role_level:
                    if role not in member.roles:
                        new_roles.append(role)
            return await member.edit(roles=new_roles, reason="level up")

        async def do_message():
            data = settings.award_message
            mode = settings.award_message_mode
            user_data = await self.bot.db.fetchval(
                """SELECT messages_enabled FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
                guild.id,
                member.id,
                cached=False,
            )
            if user_data is None:
                user_data = True
            if user_data is False:
                return
            if not data:
                return
            try:
                data = json.loads(data)
            except Exception:
                pass
            if mode == "CUSTOM":
                channel_id = settings.channel_id
                channel = guild.get_channel(channel_id)
                if not channel:
                    channel = member
            else:
                channel = member
            try:
                message = data.get("message")
            except Exception:
                message = data

            message = message.replace("{level}", str(level))
            if user_data is True:
                try:
                    return await self.bot.send_embed(channel, message, user=member)
                except Exception:
                    return False
            else:
                return

        await do_roles()
        await do_message()


async def setup(bot: Client):
    await bot.add_cog(LevelEvents(bot))
