from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, List, Optional

from aiohttp import ClientSession
from cashews import cache
from discord import (Client, ClientException, Embed, Guild, HTTPException,
                     Member, Message)
from discord.opus import OpusNotLoaded
from discord.utils import escape_markdown
from system.patch.context import Context as BaseContext
from wavelink import Playable as Track
from wavelink import Player as BasePlayer
from wavelink.filters import (Equalizer, Filters, Karaoke, LowPass, Rotation,
                              Timescale, Vibrato)
from yarl import URL

from .panel import Panel
from .utils import format_duration


class Context(BaseContext):
    voice_client: HonestPlayer


@property
def nightcore() -> Timescale:
    return Timescale(speed=1.3, pitch=1.3, rate=1, tag="NightCore")


@property
def chipmunk() -> Timescale:
    return Timescale(speed=1.05, pitch=1.35, rate=1.25, tag="ChipMunk")


@property
def karaoke() -> Karaoke:
    return Karaoke(
        level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0, tag="Karaoke_"
    )


@property
def eightd() -> Rotation:
    return Rotation(rotation_hertz=0.2, tag="8D")


@property
def vaporwave() -> Equalizer:
    return Equalizer(levels=[(0, 0.3), (1, 0.3)], tag="Vaporwave")


@property
def vibrato() -> Vibrato:
    return Vibrato(frequency=10, depth=0.9, tag="Vibrato")


@property
def soft() -> LowPass:
    return LowPass(smoothing=20.0, tag="Soft")


@property
def boost() -> Equalizer:
    return Equalizer(
        levels=[
            (0, 0.10),
            (1, 0.10),
            (2, 0.05),
            (3, 0.05),
            (4, -0.05),
            (5, -0.05),
            (6, 0),
            (7, -0.05),
            (8, -0.05),
            (9, 0),
            (10, 0.05),
            (11, 0.05),
            (12, 0.10),
            (13, 0.10),
        ],
        tag="Boost",
    )


@property
def metal() -> Equalizer:
    return Equalizer(
        levels=[
            (0, 0.300),
            (1, 0.250),
            (2, 0.200),
            (3, 0.100),
            (4, 0.050),
            (5, -0.050),
            (6, -0.150),
            (7, -0.200),
            (8, -0.100),
            (9, -0.050),
            (10, 0.050),
            (11, 0.100),
            (12, 0.200),
            (13, 0.250),
            (14, 0.300),
        ],
        tag="Metal",
    )


@property
def flat() -> Equalizer:
    return Equalizer(levels=[(i, 0.0) for i in range(15)], tag="Flat")


@property
def piano() -> Equalizer:
    return Equalizer(
        levels=[
            (0, -0.25),
            (1, -0.25),
            (2, -0.125),
            (3, 0.0),
            (4, 0.25),
            (5, 0.25),
            (6, 0.0),
            (7, -0.25),
            (8, -0.25),
            (9, 0.0),
            (10, 0.0),
            (11, 0.5),
            (12, 0.25),
            (13, -0.025),
        ],
        tag="Piano",
    )


class HonestPlayer(BasePlayer):
    bot: Client
    guild: Guild
    context: Context
    skip_votes: Optional[List[Member]] = []
    controller: Optional[Message]
    synthesize: bool

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inactive_timeout = 180
        self.bot = self.client
        self.skip_votes = []
        self.controller = None
        self.synthesize = False

    @property
    def dj(self) -> Member:
        return self.context.author

    @property
    def requester(self) -> Optional[Member]:
        track = self.current
        if not track:
            return

        return self.guild.get_member(getattr(track.extras, "requester_id") or 0)

    @classmethod
    async def from_context(cls, ctx: Context) -> Optional[Message]:
        if ctx.command.name in ("dialect", "preference"):
            return

        if not (voice := ctx.author.voice) or not voice.channel:
            return await ctx.warn("You are not connected to a voice channel")

        elif (bot_voice := ctx.guild.me.voice) and voice.channel != bot_voice.channel:
            return await ctx.warn("You are not connected to my voice channel")

        elif not bot_voice or not ctx.voice_client:
            if ctx.command.name not in ("speak", "play"):
                return await ctx.warn("I'm not connected to a voice channel")

        if ctx.voice_client:
            return

        try:
            player = await voice.channel.connect(
                cls=cls,
                self_deaf=True,
            )
            player.context = ctx
        except (TimeoutError, ClientException, OpusNotLoaded) as exc:
            return await ctx.warn(
                f"I was not able to connect to {voice.channel.mention}"
            )

    async def play(
        self,
        track: Track,
        *,
        replace: bool = True,
        start: int = 0,
        end: int | None = None,
        volume: int | None = None,
        paused: bool | None = None,
        add_history: bool = True,
        filters: Filters | None = None,
        populate: bool = False,
        max_populate: int = 5,
    ) -> Track:
        self.skip_votes.clear()
        if self.controller:
            with suppress(HTTPException):
                await self.controller.delete()

        return await super().play(
            track,
            replace=replace,
            start=start,
            end=end,
            volume=volume,
            paused=paused,
            add_history=add_history,
            filters=filters,
            populate=populate,
            max_populate=max_populate,
        )

    async def pause(self, value: bool) -> None:
        await super().pause(value)
        await self.refresh_panel()

    async def embed(self, track: Track) -> Embed:
        member = self.requester
        if track.source.startswith("youtube"):
            deserialized = await self.deserialize(track.title)
        else:
            deserialized = track.title

        source, source_icon = self.pretty_source(track)

        footer: list[str] = []
        if source:
            footer.append(source)

        footer.extend(
            [
                (f"Queued by {member.display_name}" if member else "Autoplay"),
                f"{format_duration(track.length)} Remaining",
            ]
        )
        embed = Embed(
            description=f"Now playing [**{escape_markdown(deserialized)}**]({track.uri}) by **{track.author}**"
        )
        embed.set_footer(
            text=" • ".join(footer),
            icon_url=source_icon or member and member.display_avatar,
        )
        return embed

    async def send_panel(self, track: Track) -> Optional[Message]:
        embed = await self.embed(track)

        with suppress(HTTPException):
            self.controller = await self.context.send(embed=embed, view=Panel(self))

    async def refresh_panel(self):
        if not self.controller:
            return

        with suppress(HTTPException):
            await self.controller.edit(view=Panel(self))

    def pretty_source(self, track: Track) -> tuple[str | None, str | None]:
        if track.source == "spotify":
            return (
                "Spotify",
                "https://cdn.discordapp.com/emojis/1307549140858961981.webp",
            )

        elif track.source == "applemusic":
            return (
                "Apple Music",
                "https://cdn.discordapp.com/emojis/1307549141307490376.webp",
            )

        elif track.source == "soundcloud":
            return (
                "SoundCloud",
                "https://cdn.discordapp.com/emojis/1307549138988171348.webp",
            )

        elif track.source.startswith("youtube"):
            return (
                "YouTube",
                "https://cdn.discordapp.com/emojis/1307549137977217045.webp",
            )

        return None, None

    @cache(ttl="30s")
    async def deserialize(self, query: str) -> str:
        async with ClientSession() as session:
            async with session.post(
                URL.build(
                    scheme="https",
                    host="metadata-filter.vercel.app",
                    path="/api/youtube",
                    query={"track": query},
                ),
            ) as response:
                with suppress(Exception):
                    data = await response.json()
                    return data["data"]["track"]

        return query

    async def disconnect(self):
        with suppress(HTTPException):
            if self.controller:
                await self.controller.delete()

        return await super().disconnect()
