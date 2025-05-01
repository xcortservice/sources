from datetime import datetime, timedelta
from random import sample
from typing import Optional

from discord import Client, Embed, Message, TextChannel, utils
from discord.ext.commands import (Cog, CommandError, Expiration, command,
                                  group, has_permissions, hybrid_command,
                                  hybrid_group)
from system.classes.builtins import shorten
from system.classes.database import Record
from system.patch.context import Context


class Giveaway(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @group(
        name="giveaway",
        description="Start a giveaway quickly and easily",
        invoke_without_command=True,
        aliases=["gw"],
    )
    @has_permissions(manage_channels=True)
    async def giveaway(self, ctx: Context):
        return await ctx.send_help()

    @giveaway.command(
        name="reroll",
        description="Reroll a winner for the specified giveaway",
        example=",giveaway reroll discord.com/channels/... 3",
    )
    @has_permissions(manage_channels=True)
    async def reroll(
        self,
        ctx: Context,
        message: Optional[Message] = None,
        winners: Optional[int] = 1,
    ):
        if not message:
            message = await self.bot.get_reference(ctx.message)
            if not message:
                raise CommandError("A message link is required")
        if not (
            giveaway := await self.bot.db.fetchrow(
                """SELECT entries, win_message_id, prize, host FROM giveaways WHERE message_id = $1""",
                message.id,
            )
        ):
            raise CommandError("that is not a giveaway")
        if not giveaway.win_message_id:
            raise CommandError("that giveaway isn't over yet")
        if winners < 1:
            raise CommandError("winner count must be an integer higher than 1")
        entries = [
            ctx.guild.get_member(i) for i in giveaway.entries if ctx.guild.get_member(i)
        ]
        new_winners = sample(entries, winners)
        winners_string = ", ".join(m.mention for m in new_winners)
        embed = Embed(
            title=f"Winners for {shorten(giveaway.prize, 25)}",
            description=f"{winners_string} {'have' if winners > 1 else 'has'} won the giveaway from <@{giveaway.host}>",
        )
        await message.edit(embed=embed)
        return await ctx.message.add_reaction("👍")

    @giveaway.command(
        name="end",
        description="End an active giveaway early",
        example=",giveaway end discord.com/channels/....",
    )
    @has_permissions(manage_channels=True)
    async def end(self, ctx: Context, message: Optional[Message] = None):
        if not message:
            message = await self.bot.get_reference(ctx.message)
            if not message:
                raise CommandError("A message link is required")
        if not (
            giveaway := await self.bot.db.fetchrow(
                """SELECT * FROM giveaways WHERE message_id = $1""", message.id
            )
        ):
            raise CommandError("that is not a giveaway")
        self.bot.dispatch("giveaway_end", ctx.guild, message.channel, giveaway)
        return await ctx.message.add_reaction("👍")

    @giveaway.command(
        name="list", description="List every active giveaway in the server"
    )
    @has_permissions(manage_channels=True)
    async def giveaway_list(self, ctx: Context):
        giveaways = await self.bot.db.fetch(
            "SELECT * FROM giveaways WHERE guild_id = $1" "", ctx.guild.id
        )

        if not giveaways:
            raise CommandError("there are no active giveaways in this server")
        embed = Embed(title="Giveaways").set_author(
            name=str(ctx.author), icon_url=ctx.author.display_avatar.url
        )
        rows = []

        def get_message_link(record: Record) -> str:
            return f"https://discord.com/channels/{record.guild_id}/{record.channel_id}/{record.message_id}"

        for giveaway in giveaways:
            if giveaway.win_message_id:
                continue
            else:
                rows.append(f"[**{giveaway.prize}**]({get_message_link(giveaway)})")
        if len(rows) == 0:
            raise CommandError("there are no active giveaways in this server")
        rows = [f"`{i}` {row}" for i, row in enumerate(rows, start=1)]
        return await ctx.paginate(embed, rows)

    @giveaway.command(
        name="cancel",
        description="Delete a giveaway without picking any winners",
        example=",giveaway cancel discord.com/channels/...",
    )
    @has_permissions(manage_channels=True)
    async def giveaway_cancel(self, ctx: Context, message: Optional[Message] = None):
        if not message:
            message = await self.bot.get_reference(ctx.message)
            if not message:
                raise CommandError("A message link is required")
        await self.bot.db.execute(
            """DELETE FROM giveaways WHERE message_id = $1""", message.id
        )
        await message.delete()
        return await ctx.success("successfully cancelled that giveaway")

    @giveaway.command(
        name="start",
        description="Start a giveaway with your provided duration, winners and prize description",
        example=",giveaways start #gw 24h 2 Concert Tickets",
    )
    @has_permissions(manage_channels=True)
    async def start(
        self,
        ctx: Context,
        channel: TextChannel,
        duration: Expiration,
        winners: int,
        *,
        prize: str,
    ):
        end_time = datetime.now() + timedelta(seconds=duration)
        embed = Embed(
            title=prize,
            description=f"React with 🎉 to enter the giveaway.\n**Ends:** {utils.format_dt(end_time, style='R')} ({utils.format_dt(end_time, style='F')})\n**Winners:** {winners}\n**Hosted by:** {str(ctx.author)}",
            timestamp=datetime.now(),
        )
        message = await channel.send(embed=embed)
        await message.add_reaction("🎉")
        await self.bot.db.execute(
            """INSERT INTO giveaways (guild_id, channel_id, message_id, winner_count, prize, expiration, entries, hosts) VALUES($1, $2, $3, $4, $5, $6, $7, $8)""",
            ctx.guild.id,
            channel.id,
            message.id,
            winners,
            prize,
            end_time,
            [],
            [ctx.author.id],
        )
        return await ctx.message.add_reaction("👍")


async def setup(bot: Client):
    await bot.add_cog(Giveaway(bot))
