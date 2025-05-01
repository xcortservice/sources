from asyncio import Lock, sleep
from collections import defaultdict

from data.variables import (AUTO_REACTION_COOLDOWN, AUTO_RESPONDER_COOLDOWN,
                            STICKY_MESSAGE_COOLDOWN)
from discord import Client, Member, TextChannel
from discord.ext.commands import Cog
from system.classes.database import Record
from system.patch.context import Context


class NotificationsEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.locks = defaultdict(Lock)
        self.last_messages = {}

    @Cog.listener("on_valid_message")
    async def on_sticky_message(self, ctx: Context):
        async with self.locks[f"sticky_message:{ctx.channel.id}"]:
            check = await self.bot.object_cache.ratelimited(
                f"rl:sticky_message:{ctx.guild.id}", *STICKY_MESSAGE_COOLDOWN
            )
            if check != 0:
                await sleep(check)
            if not (
                config := await self.bot.db.fetchrow(
                    """SELECT code, last_message FROM sticky_message WHERE guild_id = $1 AND channel_id = $2""",
                    ctx.guild.id,
                    ctx.channel.id,
                )
            ):
                return
            if last_message_id := self.last_messages.get(ctx.channel.id):
                try:
                    await self.bot.http.delete_message(ctx.channel.id, last_message_id)
                except Exception:
                    pass
            elif config.last_message:
                try:
                    await self.bot.http.delete_message(
                        ctx.channel.id, config.last_message
                    )
                except Exception:
                    pass
            message = await self.bot.send_embed(
                ctx.channel, config.code, user=ctx.author
            )
            await self.bot.db.execute(
                """UPDATE sticky_message SET last_message = $1 WHERE guild_id = $2 AND channel_id = $3""",
                message.id,
                ctx.guild.id,
                ctx.channel.id,
            )
            self.last_messages[message.channel.id] = message.id

    async def send_response(self, ctx: Context, record: Record):
        if check := await self.bot.object_cache.ratelimited(
            f"auto_responder:{ctx.guild.id}", *AUTO_RESPONDER_COOLDOWN
        ):
            if check != 0:
                await sleep(check)
        # command checks
        if not record.ignore_command_checks:
            if ctx.valid:
                return

        role_ids = [r.id for r in ctx.author.roles]
        matches = list(set(role_ids) & set(record.denied_role_ids))

        # ignored role ID check
        if matches:
            return

        channel_matches = list(set([ctx.channel.id]) & set(record.denied_channel_ids))

        # ignored channel ID check
        if channel_matches:
            return

        if record.reply:
            kwargs = {"reference": ctx.message}
        else:
            kwargs = {}
        return await ctx.send(
            record.response, delete_after=record.self_destruct, **kwargs
        )

    @Cog.listener("on_context")
    async def on_auto_responder(self, ctx: Context):
        async with self.locks[f"auto_responder:{ctx.channel.id}"]:
            if not (
                data := await self.bot.db.fetch(
                    """SELECT * FROM auto_responders WHERE guild_id = $1""",
                    ctx.guild.id,
                )
            ):
                return
            for record in data:
                if (
                    not record.strict
                    and record.trigger.lower() in ctx.message.content.lower()
                ):
                    await self.send_response(ctx, record)
                elif (
                    record.strict
                    and record.trigger.lower() in ctx.message.content.lower().split(" ")
                ):
                    await self.send_response(ctx, record)

    @Cog.listener("on_valid_message")
    async def on_auto_reaction(self, ctx: Context):
        async with self.locks[f"auto_reaction:{ctx.channel.id}"]:
            words = [r.lower() for r in ctx.message.content.split(" ")]
            words.append(str(ctx.channel.id))
            records = await self.bot.db.fetch(
                """SELECT * FROM auto_reactions WHERE guild_id = $1 AND trigger = ANY($2)""",
                ctx.guild.id,
                words,
            )
            for record in records:
                for reaction in record.response:
                    check = await self.bot.object_cache.ratelimited(
                        f"rl:auto_reaction:{ctx.guild.id}", *AUTO_REACTION_COOLDOWN
                    )
                    if check != 0:
                        await sleep(check)
                    await ctx.message.add_reaction(str(reaction))


async def setup(bot: Client):
    await bot.add_cog(NotificationsEvents(bot))
