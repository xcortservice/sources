import math
from contextlib import suppress
from typing import Literal, Optional, Union

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from discord import Attachment, Client, Embed, Message, VoiceChannel
from discord.ext.commands import (Cog, CommandError, command, group,
                                  hybrid_group)
from wavelink import LavalinkLoadException, Node
from wavelink import Playable as Track
from wavelink import Playlist, Pool, QueueMode, Search, TrackSource
from wavelink.filters import (Equalizer, Filters, Karaoke, LowPass, Rotation,
                              Timescale, Vibrato)

from .panel import Panel
from .player import HonestPlayer, Context
from .utils import format_duration, pluralize


async def scrape_spotify(query: str) -> str:
    async with ClientSession() as session:
        async with session.get(query) as response:
            soup = BeautifulSoup(await response.read(), "html.parser")
            artist = soup.find(
                "meta", attrs={"name": "music:musician_description"}
            ).attrs["content"]
            title = soup.find("meta", attrs={"name": "twitter:title"}).attrs["content"]
    return f"{title} {artist}"


def required_votes(cmd: str, channel: VoiceChannel):
    """Method which returns required votes based on amount of members in a channel."""

    required = math.ceil((len(channel.members) - 1) / 2.5)
    if cmd == "stop":
        if len(channel.members) == 3:
            required = 2

    return required or 1


class MusicCommands(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    def is_privileged(self, ctx: Context):
        """Check whether the user is an Admin or DJ."""

        return (
            ctx.author in (ctx.voice_client.dj, ctx.voice_client.requester)
            or ctx.author.guild_permissions.kick_members
        )

    async def get_player(self, ctx: Context) -> HonestPlayer:
        return ctx.voice_client

    async def cog_load(self):
        nodes = [
            Node(
                identifier="honest",
                uri="http://lavalink.honest.rocks",
                password="DMSipzqL8ye?X@r#!Acstgdm",
                resume_timeout=180,
            )
        ]

        await Pool.connect(nodes=nodes, client=self.bot)

    async def cog_check(self, ctx: Context) -> None:
        c = await HonestPlayer.from_context(ctx)
        return not isinstance(c, Message)

    @command(aliases=("p",))
    async def play(
        self,
        ctx: Context,
        *,
        query: Optional[str] = None,
        file: Optional[Attachment] = None,
    ) -> Optional[Message]:
        """Play the requested song in your current voice channel."""

        tts = query.startswith("tts:") if query else False
        if query:
            query = query.replace("tts:", "/tmp/honest/")
            if "open.spotify.com" in query:
                query = await scrape_spotify(query)

        elif ctx.message.attachments:
            file = ctx.message.attachments[0]

        if file and not query:
            query = file.url

        if not query and not file:
            return await ctx.failing(
                "Please provide a song name or attach a valid audio file."
            )

        result: Optional[Search] = None
        with suppress(LavalinkLoadException):
            result = await Track.search(
                query,
                source=TrackSource.SoundCloud if not tts else "",  # type: ignore
            )

        if not result:
            return await ctx.fail(f"Couldn't find any results for **{query}**")

        if isinstance(result, Playlist):
            for track in result.tracks:
                track.extras = {"requester_id": ctx.author.id}

            await ctx.voice_client.queue.put_wait(result)
            await ctx.success(
                f"*Added [**{result.name}**]({result.url}) with {len(result.tracks)} {pluralize('track', len(result.tracks))} to the queue*"
            )
        else:
            track = result[0]
            track.extras = {"requester_id": ctx.author.id}
            if tts:
                ctx.voice_client.synthesize = True
                ctx.voice_client.queue.put_at(0, track)
            else:
                await ctx.voice_client.queue.put_wait(track)

            if track.source != "local":
                await ctx.success(
                    f"*Queued [**{track.title}**]({track.uri}) by **{track.author}***",
                )

        if not ctx.voice_client.playing:
            await ctx.voice_client.play(ctx.voice_client.queue.get())

    @command(aliases=("stop", "dc"))
    async def disconnect(self, ctx: Context) -> Message:
        """Stop the player and clear the queue."""

        if not self.is_privileged(ctx):
            return await ctx.fail("You do not have permission to stop the player")

        await ctx.voice_client.disconnect()
        return await ctx.success("Stopped the **player** and cleared the **queue**")

    @command()
    async def skip(self, ctx: Context) -> Message:
        """Skip the current track."""

        if ctx.voice_client.queue.mode == QueueMode.loop:
            return await ctx.fail("Cannot skip track while looping track")

        elif not ctx.voice_client.current:
            return await ctx.fail("There isn't a track being played")

        votes = ctx.voice_client.skip_votes
        required = required_votes("skip", ctx.voice_client.channel)
        if ctx.author in votes:
            return await ctx.fail("You have already voted to skip this track")

        votes.append(ctx.author)
        if self.is_privileged(ctx) or len(votes) >= required:
            votes.clear()
            await ctx.voice_client.skip(force=True)
            return await ctx.success("*Skipping to the next track*")

        return await ctx.success(
            f"{ctx.author.mention} has voted to skip the current track (`{len(votes)}`/`{required}` required)"
        )

    @command(aliases=("vol", "v"))
    async def volume(self, ctx: Context, volume: int) -> Message:
        """Change the volume of the player."""

        if not self.is_privileged(ctx):
            return await ctx.fail("You do not have permission to change the volume")

        if not 0 <= volume <= 100:
            return await ctx.fail("Volume must be between 0 and 100")

        await ctx.voice_client.set_volume(volume)
        return await ctx.success(f"Set volume to **{volume}%**")

    @command()
    async def pause(self, ctx: Context) -> Message:
        """Pause the current track."""

        if not self.is_privileged(ctx):
            return await ctx.fail("You do not have permission to pause the player")

        elif not ctx.voice_client.playing:
            return await ctx.fail("There isn't a track being played")

        await ctx.voice_client.pause(True)
        return await ctx.success("Paused the player")

    @command()
    async def resume(self, ctx: Context) -> Message:
        """Resume the current track."""

        if not self.is_privileged(ctx):
            return await ctx.fail("You do not have permission to resume the player")

        elif not ctx.voice_client.paused:
            return await ctx.fail("The player is not paused")

        await ctx.voice_client.pause(False)
        return await ctx.success("Resumed the player")

    @command()
    async def shuffle(self, ctx: Context) -> Message:
        """Shuffle the queue."""

        if not self.is_privileged(ctx):
            return await ctx.fail("You do not have permission to shuffle the queue")

        elif not ctx.voice_client.queue:
            return await ctx.fail("There are no tracks in the queue to shuffle")

        ctx.voice_client.queue.shuffle()
        return await ctx.success("Shuffled the queue")

    @command(aliases=("loop",))
    async def repeat(
        self,
        ctx: Context,
        option: Literal["queue", "track", "off"],
    ) -> Message:
        """Set the loop mode of the player."""

        if not self.is_privileged(ctx):
            return await ctx.fail("You do not have permission to change the loop mode")

        if option == "track":
            ctx.voice_client.queue.mode = QueueMode.loop

        elif option == "queue":
            ctx.voice_client.queue.mode = QueueMode.loop_all

        else:
            ctx.voice_client.queue.mode = QueueMode.normal

        await ctx.voice_client.refresh_panel()
        return await ctx.success(f"Set loop mode to **{option}**")

    @command(aliases=("cur",))
    async def current(self, ctx: Context) -> Message:
        """View the current track."""

        if not (track := ctx.voice_client.current):
            return await ctx.fail("There isn't a track being played")

        embed = await ctx.voice_client.embed(track)
        return await ctx.reply(embed=embed, view=Panel(self))

    @group(invoke_without_command=True)
    async def queue(self, ctx: Context):
        """View all tracks in the queue."""

        if not (tracks := ctx.voice_client.queue):
            return await ctx.fail("There are no tracks in the queue")

        return await ctx.paginate(
            Embed(
                title="Queue",
                footer={
                    "text": f"{len(tracks)} {pluralize('track', len(tracks))} • {format_duration(sum(track.length for track in tracks))}",
                },
            ),
            [
                f"**{index + 1}.** [{track.title}]({track.uri}) by **{track.author}** {f'[{requester.mention}]'}"
                for index, track in enumerate(tracks)
                if (
                    requester := ctx.guild.get_member(
                        getattr(track.extras, "requester_id") or 0
                    )
                )
            ],
        )

    @queue.command(name="view", with_app_command=True)
    async def queue_view(self, ctx: Context):
        """Alias for the `queue` command."""

        return await self.queue(ctx)

    @queue.command(name="clear", aliases=("empty",))
    async def queue_clear(self, ctx: Context) -> Message:
        """Remove all tracks from the queue."""

        if not self.is_privileged(ctx):
            return await ctx.fail("You do not have permission to clear the queue")

        ctx.voice_client.queue.clear()
        return await ctx.success("Cleared the queue")

    @queue.command(name="remove")
    async def queue_remove(self, ctx: Context, index: int) -> Message:
        """Remove a track from the queue."""

        if not self.is_privileged(ctx):
            return await ctx.fail(
                "You do not have permission to remove tracks from the queue."
            )

        if not (track := ctx.voice_client.queue[index]):
            return await ctx.fail(f"Track at index **{index}** doesn't exist")

        ctx.voice_client.queue.remove(track)
        return await ctx.success(f"Removed **{track.title}** from the queue")

    @queue.command(name="move")
    async def queue_move(
        self,
        ctx: Context,
        position: int,
        new_position: int,
    ) -> Message:
        """Move a track in the queue to a new index."""

        if not self.is_privileged(ctx):
            return await ctx.fail(
                "You do not have permission to move tracks in the queue."
            )

        queue = ctx.voice_client.queue
        if not queue:
            return await ctx.fail("No tracks are in the queue")

        elif not 0 < position <= len(queue):
            return await ctx.fail(
                f"Invalid position - must be between `1` and `{len(queue)}`"
            )

        elif not 0 < new_position <= len(queue):
            return await ctx.fail(
                f"Invalid new position - must be between `1` and `{len(queue)}`"
            )

        track = queue[position - 1]
        queue.remove(track)
        queue.put_at(new_position - 1, track)
        return await ctx.success(
            f"Moved [**{track.title}**]({track.uri}) to `{new_position}` in the queue"
        )

    @command(aliases=("remv", "rmv"), hidden=True)
    async def remove(self, ctx: Context, index: int) -> Message:
        """Remove a track from the queue."""

        return await self.queue_remove(ctx, index=index)

    @command(aliases=("mv",), hidden=True)
    async def move(self, ctx: Context, position: int, new_position: int) -> Message:
        """Move a track in the queue to a new index."""

        return await self.queue_move(ctx, position=position, new_position=new_position)

    async def clear_filters(self, ctx: Context, player: HonestPlayer):
        try:
            await player.set_filters()  # Reset filters
        except Exception as e:
            if ctx.author.name == "aiohttp":
                raise e

    @group(
        name="preset", description="Use a preset for Music", invoke_without_command=True
    )
    async def preset(self, ctx: Context):
        return await ctx.send_help()

    @preset.command(
        name="vibrato",
        description="Introduces a wavering pitch effect for dynamic tone",
        example=",preset vibrato True",
    )
    async def vibrato(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    vibrato=Vibrato({"frequency": 10, "depth": 0.9, "tag": "Vibrato"})
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="metal",
        description="Amplifies midrange for a fuller, concert-like sound, ideal for metal track",
        example=",preset metal True",
    )
    async def metal(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    equalizer=Equalizer(
                        {
                            "levels": [
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
                            "tag": "Metal",
                        }
                    )
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="flat",
        description="Represents a normal EQ setting with default levels across the board",
        example=",preset flat True",
    )
    async def flat(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    equalizer=Equalizer(
                        {"tag": "Flat", "levels": [(i, 0.0) for i in range(15)]}
                    )
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="vaporwave",
        description="Slows track playback for nostalgic and vintage half-speed effect",
        example=",preset vaporwave True",
    )
    async def vaporwave(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    equalizer=Equalizer(
                        {"tag": "VaporWave", "levels": [(0, 0.3), (1, 0.3)]}
                    )
                )
            )  # Example for Vaporwave
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="nightcore",
        description="Accelerates track playback for nightcore-style music",
        example=",preset nightcore True",
    )
    async def nightcore(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    timescale=Timescale(
                        {"tag": "NightCore", "speed": 1.3, "pitch": 1.3}
                    )
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="soft",
        description="Cuts high and mid frequencies, allowing only low frequencies",
        example=",preset soft True",
    )
    async def soft(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    low_pass=LowPass({"tag": "Soft", "smoothing": 20.0})
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="boost",
        description="Enhances track with heightened bass and highs for a lively, energetic feel",
        example=",preset boost True",
    )
    async def boost(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    equalizer=Equalizer(
                        {
                            "tag": "Boost",
                            "levels": [
                                (0, 0.5),
                                (1, 0.5),
                                (2, 0.5),
                                (3, 0.5),
                                (4, 0.5),
                                (5, 0.5),
                                (6, 0.5),
                                (7, 0.5),
                                (8, 0.5),
                                (9, 0.5),
                                (10, 0.5),
                                (11, 0.5),
                                (12, 0.5),
                                (13, 0.5),
                                (14, 0.5),
                            ],
                        }
                    )
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="8d",
        aliases=["eightd"],
        description="Creates a stereo-like panning effect, rotating audio for immersive sound",
        example=",preset 8d True",
    )
    async def eightd(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    rotation=Rotation({"rotation_hertz": 0.2, "tag": "8D"})
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="chipmunk",
        description="Accelerates track playback to produce a high-pitched, chipmunk-like sound",
        example=",preset chipmunk True",
    )
    async def chipmunk(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    timescale=Timescale({"speed": 1.5, "pitch": 1.5, "tag": "ChipMunk"})
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="piano",
        description="Enhances mid and high tones for standout piano-based tracks",
        example=",preset piano True",
    )
    async def piano(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    equalizer=Equalizer(
                        {
                            "tag": "Piano",
                            "levels": [
                                (0, 0.2),
                                (1, 0.2),
                                (2, 0.2),
                                (3, 0.2),
                                (4, 0.2),
                                (5, 0.2),
                                (6, 0.2),
                                (7, 0.2),
                                (8, 0.2),
                                (9, 0.2),
                                (10, 0.2),
                                (11, 0.2),
                                (12, 0.2),
                                (13, 0.2),
                                (14, 0.2),
                            ],
                        }
                    )
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="karaoke",
        description="Filters out vocals from the track, leaving only the instrumental",
        example=",preset karaoke True",
    )
    async def karaoke(self, ctx: Context, setting: bool):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        if setting:
            await player.set_filters(
                Filters.from_filters(
                    karaoke=Karaoke(
                        {
                            "level": 1.0,
                            "mono_level": 1.0,
                            "filter_band": 220.0,
                            "filter_width": 100.0,
                            "tag": "Karaoke_",
                        }
                    )
                )
            )
        await ctx.message.add_reaction("✅")

    @preset.command(
        name="active",
        aliases=["list", "l", "show", "view"],
        description="get the current active preset",
    )
    async def active(self, ctx: Context):
        player: HonestPlayer = await self.get_player(ctx)
        filters = player.filters
        active_filters = []
        for key, value in filters.__call__().items():
            if isinstance(value, list):
                for v in value:
                    if isinstance(v, dict):
                        if tag := v.get("tag"):
                            active_filters.append(tag)
            elif isinstance(value, dict):
                if tag := value.get("tag"):
                    active_filters.append(tag)

        if not active_filters:
            raise CommandError("You have not set any preset")
        await ctx.send(
            f"Your current preset is set to: {', '.join(f for f in set(active_filters))}"
        )

    @preset.command(name="clear", description="reset the preset that has been applied")
    async def clear(self, ctx: Context):
        player: HonestPlayer = await self.get_player(ctx)
        await self.clear_filters(ctx, player)
        await ctx.message.add_reaction("✅")


async def setup(bot: Client):
    await bot.add_cog(MusicCommands(bot))
