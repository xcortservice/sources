from contextlib import suppress
from typing import cast

from discord import Client, HTTPException, Member, VoiceState
from discord.ext.commands import Cog
from wavelink import (TrackEndEventPayload,  # type: ignore
                      TrackStartEventPayload)

from .player import HonestPlayer, Context


class MusicEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @Cog.listener("on_voice_state_update")
    async def check_player_activity(
        self, member: Member, before: VoiceState, after: VoiceState
    ):
        if before.channel and not after.channel and member.guild.voice_client:
            if not isinstance(before.guild.voice_client, HonestPlayer):
                return
            if before.channel == member.guild.voice_client.channel:
                if len(before.channel.members) == 2:
                    channel = member.guild.get_channel(before.channel.id)
                    members = [m for m in channel.members if m.id != self.bot.user.id]
                    if not members:
                        self.bot.dispatch(
                            "wavelink_inactive_player", before.guild.voice_client
                        )

    @Cog.listener()
    async def on_wavelink_track_end(self, payload: TrackEndEventPayload):
        client = cast(HonestPlayer, payload.player)
        if not client:
            return

        if client.queue:
            await client.play(client.queue.get())

    def is_privileged(self, ctx: Context):
        """Check whether the user is an Admin or DJ."""

        return (
            ctx.author in (ctx.voice_client.dj, ctx.voice_client.requester)
            or ctx.author.guild_permissions.kick_members
        )

    @Cog.listener()
    async def on_wavelink_track_start(self, payload: TrackStartEventPayload) -> None:
        client = cast(HonestPlayer, payload.player)
        track = payload.track

        if not client:
            return

        if client.context and track.source != "local":
            with suppress(HTTPException):
                await client.send_panel(track)

    @Cog.listener()
    async def on_wavelink_inactive_player(self, player: HonestPlayer):
        await player.disconnect()


async def setup(bot: Client):
    await bot.add_cog(MusicEvents(bot))
