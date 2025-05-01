from discord.ext.commands import (
    Cog,
    command,
    group,
    CommandError,
    param,
    Boolean,
    has_permissions,
)
from asyncspotify import Client as SpotifyClient
from asyncspotify import ClientCredentialsFlow as SpotifyClientCredentialsFlow
from system.patch.context import Context
from discord import Client, Message, Embed, File, Member, User, Guild, utils
from discord.ext import commands
from asyncio import gather, sleep, ensure_future
from system.classes.builtins import shorten
from humanize import intcomma as comma
from typing import Optional, List, Union, Dict, Tuple, Any
from .classes.client import ClientSession
from .classes import lastfm
from .classes.lastfm import Client as LastFMClient
from time import perf_counter
from yarl import URL
from loguru import logger
import aiohttp
from io import BytesIO
from system.worker import offloaded
from bs4 import BeautifulSoup
from discord import Color, HTTPException, NotFound
from discord.utils import escape_markdown as escape_md
from .converters import Timeframe, Artist, Album, Track
import discord
import orjson
from datetime import datetime
import urllib
import pytz
from system.classes.music import soundcloud, itunes
from lxml import html
from munch import Munch
from system.managers.flags.lastfm import CollageFlags

def format_duration(value: int, ms: bool = True) -> str:
    h = int((value / (1000 * 60 * 60)) % 24) if ms else int((value / (60 * 60)) % 24)
    m = int((value / (1000 * 60)) % 60) if ms else int((value / 60) % 60)
    s = int((value / 1000) % 60) if ms else int(value % 60)

    result = ""
    if h:
        result += f"{h}:"

    result += "00:" if not m else f"{m}:"
    result += "00" if not s else f"{str(s).zfill(2)}"

    return result

UTC = pytz.timezone('UTC')
log = logger


def space(value: str, max_character: int):
    needed = max_character - len(value) + 1
    s = " "
    return s * needed


async def fetch(session, url, params=None, handling="json"):
    async with session.get(url, params=params, verify_ssl=False) as response:
        if response.status != 200:
            return None
        if handling == "json":
            return await response.json()
        if handling == "text":
            return await response.text()
        return await response


async def scrape_artist_image(artist):
    url = f"https://www.last.fm/music/{urllib.parse.quote_plus(str(artist))}/+images"
    async with aiohttp.ClientSession(json_serialize=orjson.dumps) as session:
        data = await fetch(session, url, handling="text")
    if data is None:
        return None

    soup = BeautifulSoup(data, "html.parser")
    image = soup.find("img", {"class": "image-list-image"})
    if image is None:
        try:
            image = (
                soup.find("li", {"class": "image-list-item-wrapper"})
                .find("a")
                .find("img")
            )
        except AttributeError:
            image = None

    return image


class plural:
    def __init__(
        self: "plural",
        value: Union[int, str, List[Any]],
        number: bool = True,
        md: str = "",
    ):
        self.value: int = (
            len(value)
            if isinstance(value, list)
            else (
                int(value.split(" ", 1)[-1])
                if value.startswith(("CREATE", "DELETE"))
                else int(value)
            )
            if isinstance(value, str)
            else value
        )
        self.number: bool = number
        self.md: str = md

    def __format__(self: "plural", format_spec: str) -> str:
        v = self.value
        singular, sep, plural = format_spec.partition("|")
        plural = plural or f"{singular}s"
        result = f"{self.md}{v:,}{self.md} " if self.number else ""

        result += plural if abs(v) != 1 else singular
        return result


def loggg(message: str):
    from logging import getLogger

    logg = getLogger(__name__)
    logg.info(message)
    log.info(message)



class LastFM(Cog):
    def __init__(self: "LastFM", bot: Client):
        self.bot = bot
        self.tasks: List[int] = []
        self.client = LastFMClient()
        self.spotify_client: SpotifyClient = SpotifyClient(
            SpotifyClientCredentialsFlow(
                client_id="d069c1918d4348668d01ff3c1beb585d",
                client_secret="3f841f6ab6a84ef09265945f7492b2eb",
            )
        )

    async def cog_load(self: "LastFM") -> None:
        await self.spotify_client.authorize()

    async def scrape_play_locations(self: "LastFM", ctx: Context, data: Munch):
        track_name = data.name
        artist_name = data.artist["#text"]
        if cached := await self.bot.db.fetchrow("""SELECT spotify, youtube, itunes FROM lastfm.locations WHERE track = $1 AND artist = $2""", track_name, artist_name):
            return {"youtube": cached.youtube, "spotify": cached.spotify, "itunes": cached.itunes.replace("geo.", "") if cached.itunes else None}
        url = data.url
        async with ClientSession() as session:
            async with session.get(url) as response:
                data = await response.text()
        tree = html.fromstring(data)
        youtube = tree.xpath('//a[contains(@class, "play-this-track-playlink") and contains(@class, "play-this-track-playlink--youtube")]/@href')[0] if len(tree.xpath('//a[contains(@class, "play-this-track-playlink") and contains(@class, "play-this-track-playlink--youtube")]/@href')) > 0 else None
        spotify = tree.xpath('//a[contains(@class, "play-this-track-playlink") and contains(@class, "play-this-track-playlink--spotify")]/@href')[0] if len(tree.xpath('//a[contains(@class, "play-this-track-playlink") and contains(@class, "play-this-track-playlink--spotify")]/@href')) > 0 else None
        itunes = tree.xpath('//a[contains(@class, "play-this-track-playlink") and contains(@class, "play-this-track-playlink--itunes")]/@href')[0] if len(tree.xpath('//a[contains(@class, "play-this-track-playlink") and contains(@class, "play-this-track-playlink--itunes")]/@href')) > 0 else None
        await self.bot.db.execute("""INSERT INTO lastfm.locations (track, artist, youtube, spotify, itunes) VALUES($1, $2, $3, $4, $5) ON CONFLICT(track, artist) DO UPDATE SET youtube = excluded.youtube, itunes = excluded.itunes, spotify = excluded.spotify""", track_name, artist_name, youtube, spotify, itunes)
        return {"youtube": youtube, "spotify": spotify, "itunes": itunes.replace("geo.", "") if itunes else None}


    async def cog_check(self: "LastFM", ctx: Context):
        if not ctx.command:
            return False
        if ctx.author.id in self.tasks:
            raise CommandError("You're libraries are currently being indexed")
        if getattr(
            ctx,
            "lastfm",
            getattr(ctx, "_LastFMlastfm", getattr(ctx, "_Contextlastfm", None)),
        ):
            return True

        if (
            ctx.command.qualified_name
            in (
                "lastfm login",
#                "lastfm logout",
                "lastfm",
                "fm", "spotifytrack", "spotifyalbum", "itunes"
            )
            or "login" in ctx.command.qualified_name
        ):
            return True

        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT *
                FROM lastfm.config
                WHERE user_id = $1
                """,
                ctx.author.id,
            )
        ):
            raise CommandError("You haven't connected your Last.fm account!")

        ctx.lastfm = data
        return True

    def url(self, value: str) -> URL:
        return URL(f"https://last.fm/music/{value}")

    async def scrape_artist_image(self, artist: str) -> str:
        if url := await self.bot.db.fetchval(
            """SELECT image_url FROM lastfm.artist_avatars WHERE artist = $1""", artist
        ):
            return url
        a = await scrape_artist_image(artist)
        if not a:
            return ""
        if not a.attrs:
            return ""
        image = a.attrs.get("src", "")
        await self.bot.db.execute(
            """INSERT INTO lastfm.artist_avatars (artist, image_url) VALUES($1, $2) ON CONFLICT(artist) DO UPDATE SET image_url = excluded.image_url""",
            artist,
            image,
        )
        return image

    async def index(self, ctx: Context):
        username = await self.bot.db.fetchval(
            """SELECT username FROM lastfm_data WHERE user_id = $1""", ctx.author.id
        )
        if not username:
            raise CommandError("you have not logged in using `lastfm login`")
        if ctx.author.id in self.tasks:
            return await ctx.fail(
                "Your current library is being indexed, please try again later!"
            )

        data = await self.client.request(
            method="user.getinfo",
            username=username,
            slug="user",
        )

        self.tasks.append(ctx.author.id)
        await self.bot.db.execute(
            """
            INSERT INTO lastfm.config (user_id, username) 
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username
            """,
            ctx.author.id,
            data.name,
        )

        message = await ctx.success(
            f"Your Last.fm account has been set as [`{data.name}`]({data.url})!"
        )

        start = perf_counter()
        await gather(
            *[
                self.bot.db.execute(query, ctx.author.id)
                for query in (
                    "DELETE FROM lastfm.artists WHERE user_id = $1",
                    "DELETE FROM lastfm.albums WHERE user_id = $1",
                    "DELETE FROM lastfm.tracks WHERE user_id = $1",
                    "DELETE FROM lastfm.crowns WHERE user_id = $1",
                )
            ]
        )

        async for library, items in lastfm.index(ctx, user=data):
            if library == "artists":
                await self.bot.db.executemany(
                    """
                    INSERT INTO lastfm.artists
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, artist)
                    DO UPDATE SET
                    plays = EXCLUDED.plays
                    """,
                    [
                        (
                            ctx.author.id,
                            data.name,
                            artist["name"],
                            int(artist["playcount"]),
                        )
                        for artist in items
                    ],
                )

            elif library == "albums":
                await self.bot.db.executemany(
                    """
                    INSERT INTO lastfm.albums
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id, artist, album)
                    DO UPDATE SET
                    plays = EXCLUDED.plays
                    """,
                    [
                        (
                            ctx.author.id,
                            data.name,
                            album["artist"]["name"],
                            album["name"],
                            int(album["playcount"]),
                        )
                        for album in items
                    ],
                )

            elif library == "tracks":
                await self.bot.db.executemany(
                    """
                    INSERT INTO lastfm.tracks
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id, artist, track)
                    DO UPDATE SET
                    plays = EXCLUDED.plays
                    """,
                    [
                        (
                            ctx.author.id,
                            data.name,
                            track["artist"]["name"],
                            track["name"],
                            int(track["playcount"]) if track.get("playcount") else 1,
                        )
                        for track in items
                    ],
                )

        elapsed = perf_counter() - start
        log.info(f"Succesfully indexed {data.name}'s library in {elapsed:.2f}s.")

        self.tasks.remove(ctx.author.id)
        return message

    async def send_nowplaying(self, ctx: Context, member: Optional[Member] = None, as_data: Optional[bool] = False):
        member = member or ctx.author
        if not isinstance(member, Member):
            member = ctx.author
        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT * 
                FROM lastfm.config
                WHERE user_id = $1
                """,
                member.id,
            )
        ):
            return await ctx.fail(
                "You haven't connected your Last.fm account!"
                if member == ctx.author
                else f"`{member}` hasn't connected their Last.fm account!"
            )
        # ensure_future(
        #     self.bot.db.execute(
        #         """UPDATE lastfm.config SET nowplaying_uses = lastfm.config.nowplaying_uses + 1 WHERE user_id = $1""",
        #         ctx.author.id,
        #     )
        # )
        tracks, user = await gather(
            *[
                self.client.request(
                    method="user.getrecenttracks",
                    username=data.username,
                    slug="recenttracks.track",
                    limit=1,
                ),
                self.client.request(
                    method="user.getinfo",
                    username=data.username,
                    slug="user",
                ),
            ]
        )
        if not tracks and not as_data:
            return await ctx.fail(
                f"Recent tracks aren't available for `{data.username}`!"
            )

        track = tracks[0]
        artist = track.artist["#text"]
        ensure_future(self.scrape_play_locations(ctx, track))
        if as_data:
            return (track, artist, track.album.get("#text", None))
        track.data = (
            await self.client.request(
                method="track.getinfo",
                username=data.username,
                track=track.name,
                artist=artist,
                slug="track",
            )
            or track
        )
        if msg := data.message:
            try:
                artist_image_url = await self.scrape_artist_image(artist)
            except Exception:
                artist_image_url = ""
            artist_plays = (
                await self.bot.db.fetchval(
                    """SELECT plays FROM lastfm.artists WHERE user_id = $1 AND artist = $2""",
                    member.id,
                    artist,
                )
                or 0
            )
            variables = {
                "{user.name}": data.username,
                "{user.avatar}": user.image[1].get(
                    "#text",
                    "https://lastfm.freetls.fastly.net/i/u/avatar170s/818148bf682d429dc215c1705eb27b98.png",
                )
                or "https://lastfm.freetls.fastly.net/i/u/avatar170s/818148bf682d429dc215c1705eb27b98.png",
                "{user.plays}": user.playcount,
                "{proper(user.plays)}": comma(int(user.playcount)),
                "{user.artist_crown}": "👑"
                if await self.bot.db.fetchrow(
                    """SELECT * FROM lastfm.crowns WHERE user_id = $1 AND guild_id = $2 AND artist = $3""",
                    member.id,
                    ctx.guild.id,
                    artist,
                )
                else "",
                "{user.url}": f"https://last.fm/user/{user.username}",
                "{author}": str(member),
                "{author.nickname}": member.nick if member.nick else "N/A",
                "{album.name}": track.album.get("#text", "N/A"),
                "{lower(album.name)}": track.album.get("#text", "N/A").lower(),
                "{album.url}": track.album.get("url", track.get("url")),
                "{album.cover}": track.data.album.images[1].get("url", ""),
                "{track.name}": track.name,
                "{lower(track.name)}": track.name.lower(),
                "{track.url}": track.url or "",
                "{track.spotify_url}": "",
                "{track.release_date}": discord.utils.format_dt(
                    datetime.strptime(
                        track.data.get("wiki", {}).get("published"), "%d %b %Y, %H:%M"
                    )
                )
                if track.data.wiki.get("published")
                else "N/A",
                "{track.duration}": format_duration(int(track.data.duration))
                if track.data.get("duration")
                else "N/A",
                "{track.plays}": track.data.userplaycount or 0,
                "{proper(track.plays)}": comma(track.data.userplaycount or 0),
                "{artist.name}": artist,
                "{lower(artist.name)}": artist.lower(),
                "{artist.plays}": artist_plays,
                "{proper(artist.plays)}": comma(artist_plays),
                "{artist.url}": track.data.artist.get("url", ""),
                "{artist.image}": artist_image_url,
            }
            for variable, value in variables.items():
                msg = msg.replace(variable, value)
            message = await self.bot.send_embed(ctx, msg, user=member)
        else:
            embed = Embed(color=data.color)
            embed.set_author(
                url=user.url,
                name=user.name,
                icon_url=user.image[-1]["#text"].replace(".png", ".gif"),
            )
            embed.set_thumbnail(url=track.image[-1]["#text"])

            embed.add_field(
                name="Track",
                value=f"[{track.name}]({track.url})",
                inline=len(track.name) <= 20,
            )
            embed.add_field(
                name="Artist",
                value=f"[{artist}]({self.url(artist)})",
                inline=len(artist) <= 20,
            )

            embed.set_footer(
                text=(
                    f"Plays: {comma(track.data.userplaycount or 0)} ∙ "
                    f"Scrobbles: {comma(user.playcount)} ∙ "
                    f"Album: {shorten(track.album.get('#text', 'N/A'), 16)}"
                ),
            )

            message = await ctx.send(embed=embed)
        reactions = data.reactions or ["🔥", "🗑"]
        for reaction in reactions:
            self.bot.ioloop.add_callback(
                message.add_reaction,
                reaction,
            )

        return message

    @group(
        name="lastfm", aliases=["fm", "lf"], description="Commands to integrate last.fm into discord", invoke_without_command=True
    )
    async def lastfm(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        return await self.send_nowplaying(ctx, member)

    @command(
        name="nowplaying",
        aliases=["np", "now"],
        description="Shows your current song or another user's current song playing from Last.fm",
        example=",nowplaying @aiohttp",
    )
    async def nowplaying(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        return await self.send_nowplaying(ctx, member)

    @lastfm.command(
        name="login", description="Login and authenticate honest to use your account"
    )
    async def lastfm_login(self, ctx: Context):
        await ctx.message.add_reaction("📩")
        session = ClientSession()
        _ = await lastfm.login(session, ctx)
        if _:
            await self.cog_check(ctx)
            return await self.lastfm_update(ctx)

    @lastfm.command(
        name="logout",
        description="Remove your Last.fm account with coffin's internal system",
    )
    async def lastfm_logout(self, ctx: Context):
        class ConfirmReset(discord.ui.View):
            def __init__(self, bot):
                super().__init__(timeout=15)
                self.bot = bot
                self.value = None

            @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
            async def approve(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                if interaction.user != ctx.author:
                    embed = Embed(
                        description=f"<:warning:1286583936113311755> {interaction.user.mention}: Your interaction is not allowed on this embed",
                        color=0xE69705,
                    )
                    return await interaction.response.send_message(
                        embed=embed, ephemeral=True
                    )

                await interaction.response.defer()
                await gather(
                    *[
                        self.bot.db.execute(query, interaction.user.id)
                        for query in (
                            "DELETE FROM lastfm.artists WHERE user_id = $1",
                            "DELETE FROM lastfm.albums WHERE user_id = $1",
                            "DELETE FROM lastfm.tracks WHERE user_id = $1",
                            "DELETE FROM lastfm.crowns WHERE user_id = $1",
                            "DELETE FROM lastfm.config WHERE user_id = $1",
                            "DELETE FROM lastfm_data WHERE user_id = $1",
                        )
                    ]
                )
                embed = Embed(
                    description=f"<:check:1286583241905803356> {interaction.user.mention}: Your account has been **removed**. Unauthorize [honest](https://last.fm/settings/applications) here",
                    color=0x90DA68,
                )
                await message.edit(embed=embed, view=None)
                self.value = True
                self.stop()

            @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
            async def decline(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                if interaction.user != ctx.author:
                    embed = Embed(
                        description=f"<:warning:1286583936113311755> {interaction.user.mention}: Your interaction is not allowed on this embed",
                        color=0xE69705,
                    )
                    return await interaction.response.send_message(
                        embed=embed, ephemeral=True
                    )
                await message.delete()
                self.value = False
                self.stop()

        embed = Embed(
            description=f"<:settings:1287327423746146334> {ctx.author.mention}: Are you sure that you want to **logout** of lastfm?",
            color=0x6E879C,
        )
        view = ConfirmReset(self.bot)
        message = await ctx.send(embed=embed, view=view)
        await view.wait()
        if view.value is None:
            await message.delete()

    @lastfm.command(name="update", aliases=["refresh", "index"])
    async def lastfm_update(self, ctx: Context) -> Message:
        """
        Refresh your local Last.fm library.
        """
        await self.cog_check(ctx)
        logger.info(dir(ctx))
        if ctx.author.id in self.tasks:
            return await ctx.fail(
                "Your library is already being indexed, please try again later!"
            )
        self.tasks.append(ctx.author.id)
        message = await ctx.normal("Starting index of your Last.fm library...")
        username = await self.bot.db.fetchval("""SELECT username FROM lastfm.config WHERE user_id = $1""", ctx.author.id)

        start = perf_counter()
        await gather(
            *[
                self.bot.db.execute(query, ctx.author.id)
                for query in (
                    "DELETE FROM lastfm.artists WHERE user_id = $1",
                    "DELETE FROM lastfm.albums WHERE user_id = $1",
                    "DELETE FROM lastfm.tracks WHERE user_id = $1",
                    "DELETE FROM lastfm.crowns WHERE user_id = $1",
                )
            ]
        )

        async for library, items in lastfm.index(ctx, user=username):
            if library == "artists":
                await self.bot.db.executemany(
                    """
                    INSERT INTO lastfm.artists
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, artist)
                    DO UPDATE SET
                    plays = EXCLUDED.plays
                    """,
                    [
                        (
                            ctx.author.id,
                            username,
                            artist if isinstance(artist, str) else artist["name"],
                            int(artist["playcount"]) if artist.get("playcount") else 0,
                        )
                        for artist in items
                    ],
                )
                await self.bot.db.executemany(
                    """
                    UPDATE lastfm.crowns
                    SET plays = $3
                    WHERE user_id = $1
                    AND artist = $2
                    """,
                    [
                        (
                            ctx.author.id,
                            artist["name"] if isinstance(artist, dict) else artist,
                            int(artist["playcount"])
                            if not isinstance(artist, str)
                            else 0,
                        )
                        for artist in items
                    ],
                )

            elif library == "albums":
                await self.bot.db.executemany(
                    """
                    INSERT INTO lastfm.albums
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id, artist, album)
                    DO UPDATE SET
                    plays = EXCLUDED.plays
                    """,
                    [
                        (
                            ctx.author.id,
                            username,
                            album["artist"]["name"],
                            album["name"],
                            int(album["playcount"]) if isinstance(album, dict) else 0,
                        )
                        for album in items
                        if not isinstance(album, str)
                    ],
                )

            elif library == "tracks":
                await self.bot.db.executemany(
                    """
                    INSERT INTO lastfm.tracks
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id, artist, track)
                    DO UPDATE SET
                    plays = EXCLUDED.plays
                    """,
                    [
                        (
                            ctx.author.id,
                            username,
                            track["artist"]["name"],
                            track["name"],
                            int(track["playcount"]) if track.get("playcount") else 1,
                        )
                        for track in items
                        if not isinstance(track, str)
                    ],
                )
            embed = message.embeds[0]
            embed.description = (
                f"Stored `{len(items):,}` {library} from your Last.fm library..."
            )
            await message.edit(embed=embed)

        elapsed = perf_counter() - start
        try:
            log.info(
                f"Succesfully indexed {ctx.lastfm.username}'s library in {elapsed:.2f}s."
            )
        except AttributeError:
            log.info(f"{dir(ctx)}")

        await sleep(1)
        self.tasks.remove(ctx.author.id)
        embed = message.embeds[0]
        embed.description = "Your Last.fm library has been refreshed."
        return await message.edit(embed=embed)
    
    @lastfm.command(name = "favorites", description = "View yours or a member's liked tracks", example = ",lastfm favorites @aiohttp")
    async def lastfm_favorites(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT * 
                FROM lastfm.config
                WHERE user_id = $1
                """,
                member.id,
            )
        ):
            return await ctx.fail(
                "You haven't connected your Last.fm account!"
                if member == ctx.author
                else f"`{member}` hasn't connected their Last.fm account!"
            )
        favorites = await lastfm.api_request({"method": "user.getLovedTracks", "username": data.username, "limit": 1000})
        if not favorites:
            raise CommandError(f"{data.username} has not **favorited** any tracks")
        favorites = favorites["lovedtracks"]["track"]

        def get_datetime_object(uts: int):
            return datetime.fromtimestamp(uts, UTC)
        
        def format_row(data: dict):
            return f"[**{data['name']}**]({data['url']}) by **{data['artist']['name']} ({utils.format_dt(get_datetime_object(data['date']['uts']), style='R')})"
        rows = [f"`{i}` {format_row(favorite)}" for i, favorite in enumerate(favorites, start = 1)]
        embed = Embed(title = f"Liked songs for {data.username}").set_author(name = ctx.author.display_name, icon_url = ctx.author.display_avatar.url)
        return await ctx.paginate(embed, rows, 10, "liked")

    @lastfm.command(name="streak", description="check a member's listening streak", example=",lastfm streak @aiohttp")
    async def lastfm_streak(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT * 
                FROM lastfm.config
                WHERE user_id = $1
                """,
                member.id,
            )
        ):
            return await ctx.fail(
                "You haven't connected your Last.fm account!"
                if member == ctx.author
                else f"`{member}` hasn't connected their Last.fm account!"
            )
        tracks, user = await gather(
            *[
                self.client.request(
                    method="user.getrecenttracks",
                    username=data.username,
                    slug="recenttracks.track",
                    limit=200,
                ),
                self.client.request(
                    method="user.getinfo",
                    username=data.username,
                    slug="user",
                ),
            ]
        )
        track_name = tracks[0].name
        artist_name = tracks[0].artist["#text"]
        album_name = tracks[0].album["#text"]
        track_data = await self.client.request(
            method="track.getinfo",
            username=data.username,
            track=track_name,
            artist=artist_name,
            slug="track",
        )
        artist_streak = 0
        album_streak = 0
        track_streak = 0
        for i, track in enumerate(tracks, start=0):
            if i == 0:
                continue
            if track.name == track_name:
                track_streak += 1
            if track.album["#text"] == album_name:
                album_streak += 1
            if track.artist["#text"] == artist_name:
                artist_streak += 1
        description = ""
        album_url = track_data.album.get("url", track_data["url"])
        if artist_streak > 0:
            description += f"**Artist:** {plural(artist_streak):play} in a row for [{artist_name}](https://last.fm/music/{artist_name.replace(' ', '+')})"
        if album_streak > 0:
            description += f"\n**Album:** {plural(album_streak):play} in a row for [{album_name}]({album_url})"
        if track_streak > 0:
            description += f"\n**Track:** {plural(track_streak):play} in a row for [{track_name}]({track_data['url']})"
        if artist_streak == 0 and track_streak == 0 and album_streak == 0:
            description = f"**{data.username}** has no active streaks"
        return await ctx.send(
            embed=Embed(
                title=f"{data.username}'s streak overview", description=description
            )
        )

    @lastfm.command(
        name="taste",
        description="Compare your music taste between you and someone else",
        example=",lastfm taste @aiohttp 1d",
    )
    async def lastfm_taste(
        self,
        ctx: Context,
        member: Member,
        period: Timeframe = param(
            default=Timeframe("overall"),
            description="The backlog period.",
        ),
    ):
        if not (
            author_data := await self.bot.db.fetch(
                """SELECT artist, plays FROM lastfm.artists WHERE user_id = $1""",
                ctx.author.id,
            )
        ):
            raise CommandError("you have not set your lastfm using `lastfm login`")
        if not (
            user_data := await self.bot.db.fetch(
                """SELECT artist, plays FROM lastfm.artists WHERE user_id = $1""",
                member.id,
            )
        ):
            raise CommandError(
                f"{member.mention} has not set their lastfm using `lastfm login`"
            )
        author_artists = {d.artist: d.plays for d in author_data}
        user_artists = {d.artist: d.plays for d in user_data}
        shared = [k for k in user_artists.keys() if author_artists.get(k)]
        if len(shared) == 0:
            raise CommandError("No shared artists found")
        amount = len(max(shared, key=len))
        rows = []
        author_username = await self.bot.db.fetchval(
            """SELECT username FROM lastfm.config WHERE user_id = $1""", ctx.author.id
        )
        user_username = await self.bot.db.fetchval(
            """SELECT username FROM lastfm.config WHERE user_id = $1""", member.id
        )
        for i, artist in enumerate(shared, start=1):
            spaces = space(artist, amount)
            symbol = ">" if author_artists[artist] > user_artists[artist] else "<"
            rows.append(
                f"{artist}{spaces}{author_artists[artist]} {symbol} {user_artists[artist]}\n"
            )
            if i == 10:
                break
        return await ctx.send(
            embed=Embed(
                title=f"Taste Comparison {author_username} vs {user_username}",
                description=f"```{''.join(r for r in rows)}```",
            ).set_author(
                name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
            )
        )

    @lastfm.group(
        name="customcommand",
        aliases=["customnp", "cc", "customfm"],
        description="Set your own custom Now Playing command",
        example="lastfm customcommand aiohttpfm --public",
        invoke_without_command=True,
        parameters={
            "public": {
                "converter": Boolean,
                "description": "make all users able to use your custom command",
                "default": False,
            },
        },
    )
    async def customcommand(self, ctx: Context, command: str):
        public = ctx.parameters.get("public")
        try:
            public = await public
        except Exception:
            pass
        if "--public" in ctx.message.content and not public:
            public = True
        if public and not ctx.author.guild_permissions.manage_guild:
            public = False
        await self.bot.db.execute(
            """INSERT INTO lastfm.commands (guild_id, user_id, public, command) VALUES($1, $2, $3, $4) ON CONFLICT(guild_id, user_id) DO UPDATE SET public = excluded.public, command = excluded.command""",
            ctx.guild.id,
            ctx.author.id,
            public,
            command,
        )
        if public:
            m = "\n**Public** flag is enabled - command usable by everyone"
        else:
            m = f"\n**Public** flag is disabled - command usable by only {ctx.author.mention}"
        return await ctx.success(
            f"Updated your custom **Now Playing** command to: `{command}`{m}"
        )

    @customcommand.command(
        name="public",
        description="Toggle public flag for a custom command",
        example=",lastfm customcommand public True",
    )
    @has_permissions(manage_guild=True)
    async def customcommand_public(self, ctx: Context, substring: Boolean):
        await self.bot.db.execute(
            """UPDATE lastfm.commands SET public = $1 WHERE user_id = $2 AND guild_id = $3""",
            substring,
            ctx.author.id,
            ctx.guild.id,
        )
        if substring:
            m = "**Public** flag is enabled -- command usable by everyone"
        else:
            m = f"**Public** flag is disabled - command usable by only {ctx.author.mention}"
        return await ctx.success(m)

    @customcommand.command(
        name="remove",
        description="Remove a custom command for a member",
        example=",lastfm customcommand remove aiohttp",
    )
    @has_permissions(manage_guild=True)
    async def customcommand_remove(
        self, ctx: Context, *, member: Optional[Member] = commands.Author
    ):
        await self.bot.db.execute(
            """DELETE FROM lastfm.commands WHERE guild_id = $1 AND user_id = $2""",
            ctx.guild.id,
            member.id,
        )
        return await ctx.success(
            f"""successfully **removed** {"your" if member == ctx.author else f"{member.mention}'s"} custom **Now Playing** command"""
        )

    @customcommand.command(
        name="cleanup", description="Clean up custom commands from absent members"
    )
    @has_permissions(administrator=True)
    async def customcommand_cleanup(self, ctx: Context):
        data = await self.bot.db.fetch(
            """SELECT * FROM lastfm.commands WHERE guild_id = $1""", ctx.guild.id
        )
        if not data:
            raise CommandError("there are no custom command entries for this server")
        to_delete = []
        for entry in data:
            if not ctx.guild.get_member(entry.user_id):
                to_delete.append(entry.user_id)

        await self.bot.db.execute(
            """DELETE FROM lastfm.commands WHERE guild_id = $1 AND user_id = ANY($2::BIGINT[])""",
            to_delete,
        )
        return await ctx.success(
            f"successfully cleaned up `{len(to_delete)}` **custom commands**"
        )

    @customcommand.command(name="reset", description="Resets all custom commands")
    @has_permissions(manage_guild=True)
    async def customcommand_reset(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM lastfm.commands WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.success("successfully reset **ALL** custom commands")

    @customcommand.command(
        name="list",
        aliases=["ls", "l", "show", "view"],
        description="View list of custom commands for NP",
    )
    @has_permissions(manage_guild=True)
    async def customcommand_list(self, ctx: Context):
        data = await self.bot.db.fetch(
            """SELECT * FROM lastfm.commands WHERE guild_id = $1""", ctx.guild.id
        )

        def get_entry(row):
            if member := ctx.guild.get_member(row.user_id):
                return f"{row.command} - **{str(member)}**"
            else:
                return f"Unknown (`{row.user_id}`)"

        rows = [f"`{i}` {get_entry(row)}" for i, row in enumerate(data, start=1)]
        if len(rows) == 0:
            raise CommandError("there are no custom command entries for this server")
        return await ctx.paginate(
            Embed(title="Custom Commands").set_author(
                name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
            ),
            rows,
        )

    @customcommand.group(
        name="blacklist",
        aliases=["bl", "ignore", "allow"],
        description="Blacklist users their own Now Playing command",
        invoke_without_command=True,
        example=",lastfm customcommand blacklist @aiohttp",
    )
    @has_permissions(manage_guild=True)
    async def customcommand_blacklist(self, ctx: Context, *, member: Member):
        if await self.bot.db.fetchrow(
            """SELECT * FROM lastfm.command_blacklist WHERE guild_id = $1 AND user_id = $2""",
            ctx.guild.id,
            member.id,
        ):
            await self.bot.db.execute(
                """DELETE FROM lastfm.command_blacklist WHERE guild_id = $1 AND user_id = $2""",
                ctx.guild.id,
                member.id,
            )
            return await ctx.success(
                f"Enabled {member.mention}'s custom **Now Playing** command"
            )
        else:
            await self.bot.db.execute(
                """INSERT INTO lastfm.command_blacklist (guild_id, user_id) VALUES($1, $2) ON CONFLICT(guild_id, user_id) DO NOTHING""",
                ctx.guild.id,
                member.id,
            )
            return await ctx.success(
                f"Disabled {member.mention}'s custom **Now Playing** command"
            )

    @customcommand_blacklist.command(
        name="list",
        aliases=["ls", "s", "show", "view"],
        description="View list of blacklisted custom command users for NP",
    )
    @has_permissions(manage_guild=True)
    async def customcommand_blacklist_list(self, ctx: Context):
        if not (
            data := await self.bot.db.fetch(
                """SELECT user_id FROM lastfm.command_blacklist WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError(
                "there are no custom command blacklist entries in this server"
            )
        rows = [
            f"`{i} **{str(ctx.guild.get_member(u.user_id) or 'Unknown')} (`{u.user_id}`)"
            for i, u in enumerate(data, start=1)
        ]
        return await ctx.paginate(
            Embed(title="Blacklisted Custom Commands").set_author(
                name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
            ),
            rows,
        )

    @lastfm.command(
        name="color",
        aliases=["colour"],
    )
    async def lastfm_color(
        self,
        ctx: Context,
        color: Color,
    ) -> Message:
        """
        Set a custom now playing embed color.
        """
        await self.cog_check(ctx)
        await self.bot.db.execute(
            """
            UPDATE lastfm.config
            SET color = $2
            WHERE user_id = $1
            """,
            ctx.author.id,
            color.value,
        )
        return await ctx.success(
            f"Your Last.fm embed color has been set as `{color}`!",
            color=color,
        )

    @lastfm.command(
        name="react",
        aliases=["reacts", "reactions"],
    )
    async def lastfm_reactions(
        self,
        ctx: Context,
        upvote: str,
        downvote: str,
    ) -> Optional[Message]:
        """
        Set a custom upvote and downvote reaction.
        """
        await self.cog_check(ctx)
        if upvote == downvote:
            return await ctx.send_help(ctx.command)

        for reaction in (upvote, downvote):
            try:
                await ctx.message.add_reaction(reaction)
            except (HTTPException, NotFound, TypeError):
                return await ctx.fail(
                    f"I'm not capable of using **{reaction}**, try using an emoji from this server!"
                )

        await self.bot.db.execute(
            """
            UPDATE lastfm.config
            SET reactions = $2
            WHERE user_id = $1
            """,
            ctx.author.id,
            [upvote, downvote],
        )
        return await ctx.success(
            f"Your Last.fm reactions have been set as {upvote} and {downvote}"
        )

    @lastfm.command(
        name="recent",
        aliases=["lp"],
    )
    async def lastfm_recent(
        self,
        ctx: Context,
        member: Optional[Member],
    ) -> Message:
        """
        View your recent tracks.
        """
        await self.cog_check(ctx)
        member = member or ctx.author

        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT * 
                FROM lastfm.config
                WHERE user_id = $1
                """,
                member.id,
            )
        ):
            return await ctx.fail(
                "You haven't connected your Last.fm account!"
                if member == ctx.author
                else f"`{member}` hasn't connected their Last.fm account!"
            )

        tracks = await self.client.request(
            method="user.getrecenttracks",
            slug="recenttracks.track",
            username=data.username,
            limit=100,
        )
        if not tracks:
            return await ctx.fail(
                f"Recent tracks aren't available for `{data.username}`!"
            )

        return await ctx.paginate(
            Embed(
                title=f"Recent tracks for {data.username}",
            ),
            [
                (
                    f"[{track.name}]({track.url}) by **{track.artist['#text']}**"
                    + (f" *<t:{track.date.uts}:R>*" if track.date else "")
                )
                for track in tracks[:100]
            ],
        )

    @lastfm.command(
        name="topartists",
        aliases=[
            "artists",
            "tar",
            "ta",
        ],
    )
    async def lastfm_topartists(
        self,
        ctx: Context,
        member: Optional[Member],
        timeframe: Timeframe = param(
            default=Timeframe("overall"),
            description="The backlog period.",
        ),
    ) -> Message:
        """
        View your overall top artists.
        """
        await self.cog_check(ctx)
        member = member or ctx.author

        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT * 
                FROM lastfm.config
                WHERE user_id = $1
                """,
                member.id,
            )
        ):
            return await ctx.fail(
                "You haven't connected your Last.fm account!"
                if member == ctx.author
                else f"`{member}` hasn't connected their Last.fm account!"
            )

        artists = await self.client.request(
            method="user.gettopartists",
            slug="topartists.artist",
            username=data.username,
            period=timeframe.period,
            limit=10,
        )
        if not artists:
            return await ctx.fail(f"`{data.username}` doesn't have any top artists!")

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"{data.username}'s {timeframe} top artists",
            ),
            [
                f"[{artist.name}]({artist.url}) ({plural(artist.playcount):play})"
                for artist in artists
            ],
        )

    @lastfm.command(
        name="topalbums",
        aliases=[
            "albums",
            "tab",
            "tal",
        ],
    )
    async def lastfm_topalbums(
        self,
        ctx: Context,
        member: Optional[Member],
        timeframe: Timeframe = param(
            default=Timeframe("overall"),
            description="The backlog period.",
        ),
    ) -> Message:
        """
        View your overall top albums.
        """
        await self.cog_check(ctx)
        member = member or ctx.author

        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT * 
                FROM lastfm.config
                WHERE user_id = $1
                """,
                member.id,
            )
        ):
            return await ctx.fail(
                "You haven't connected your Last.fm account!"
                if member == ctx.author
                else f"`{member}` hasn't connected their Last.fm account!"
            )

        albums = await self.client.request(
            method="user.gettopalbums",
            slug="topalbums.album",
            username=data.username,
            period=timeframe.period,
            limit=10,
        )
        if not albums:
            return await ctx.fail(f"`{data.username}` doesn't have any top albums!")

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"{data.username}'s {timeframe} top albums",
            ),
            [
                f"[{album.name}]({album.url}) by **{album.artist.name}** ({plural(album.playcount):play})"
                for album in albums
            ],
        )

    @lastfm.command(
        name="toptracks",
        aliases=[
            "tracks",
            "ttr",
            "tt",
        ],
    )
    async def lastfm_toptracks(
        self,
        ctx: Context,
        member: Optional[Member],
        timeframe: Timeframe = param(
            default=Timeframe("overall"),
            description="The backlog period.",
        ),
    ) -> Message:
        """
        View your overall top tracks.
        """
        await self.cog_check(ctx)
        member = member or ctx.author

        if not (
            data := await self.bot.db.fetchrow(
                """
                SELECT * 
                FROM lastfm.config
                WHERE user_id = $1
                """,
                member.id,
            )
        ):
            return await ctx.fail(
                "You haven't connected your Last.fm account!"
                if member == ctx.author
                else f"`{member}` hasn't connected their Last.fm account!"
            )

        tracks = await self.client.request(
            method="user.gettoptracks",
            slug="toptracks.track",
            username=data.username,
            period=timeframe.period,
            limit=10,
        )
        if not tracks:
            return await ctx.fail(f"`{data.username}` doesn't have any top tracks!")

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"{data.username}'s {timeframe} top tracks",
            ),
            [
                f"[{track.name}]({track.url}) by **{track.artist.name}** ({plural(track.playcount):play})"
                for track in tracks
            ],
        )

    @lastfm.command(
        name="whoknows",
        aliases=["wk"],
    )
    async def lastfm_whoknows(
        self,
        ctx: Context,
        *,
        artist: str = param(
            converter=Artist,
            default=Artist.fallback,
        ),
    ) -> Message:
        """
        View the top listeners for an artist.
        """
        await self.cog_check(ctx)
        records = await self.bot.db.fetch(
            """
            SELECT user_id, username, plays
            FROM lastfm.artists
            WHERE user_id = ANY($2::BIGINT[])
            AND artist = $1
            ORDER BY plays DESC
            """,
            artist,
            [user.id for user in ctx.guild.members],
        )
        if not records:
            return await ctx.fail(f"Nobody in this server has listened to `{artist}`!")

        items = []
        for index, listener in enumerate(records[:100], start=1):
            user = ctx.guild.get_member(listener.user_id)
            if not user:
                continue

            rank = f"`{index}`"
            if index == 1:
                rank = "👑"
                await self.bot.db.execute(
                    """INSERT INTO lastfm.crowns (guild_id, user_id, username, artist, plays) VALUES($1, $2, $3, $4, $5) ON CONFLICT(guild_id, artist) DO UPDATE SET user_id = excluded.user_id, username = excluded.username, plays = excluded.plays""",
                    ctx.guild.id,
                    listener.user_id,
                    listener.username,
                    artist,
                    listener.plays,
                )

            items.append(
                f"{rank} [{shorten(user.name, 19)}](https://last.fm/user/{listener.username}) has {plural(listener.plays, md='**'):play}"
            )

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"Top listeners for {shorten(artist, 12)}",
            ),
            items,
        )

    @lastfm.command(name = "globalwhoknows", aliases = ["gwk"], description = "View the top listeners for an artist globally", example = ",lastfm globalwhoknows Lucki")
    async def globalwhoknows(
        self,
        ctx: Context,
        *,
        artist: str = param(
            converter=Artist,
            default=Artist.fallback,
        ),
    ) -> Message:
        await self.cog_check(ctx)
        records = await self.bot.db.fetch(
            """
            SELECT user_id, username, plays
            FROM lastfm.artists
            WHERE artist = $1
            ORDER BY plays DESC
            """,
            artist,
        )
        if not records:
            return await ctx.fail(f"Nobody has listened to `{artist}`!")

        items = []
        for index, listener in enumerate(records[:100], start=1):
            user = self.bot.get_user(listener.user_id)
            if not user:
                user = f"Unknown (`{listener.user_id}`)"
            else:
                user = shorten(user.name, 19)
            rank = f"`{index}`"
            if index == 1:
                rank = "👑"

            items.append(
                f"{rank} [{user}](https://last.fm/user/{listener.username}) has {plural(listener.plays, md='**'):play}"
            )

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"Top listeners for {shorten(artist, 12)}",
            ),
            items,
        )
    
    @lastfm.command(name = "globalwkalbum", aliases = ["gwka"], description = "View the top listeners for an album globally", example = ",lastfm globalwkalbum YOUNG GENIUS")
    async def globalwkalbum(
        self,
        ctx: Context,
        *,
        album: Album = param(
            default=Album.fallback,
        ),
    ) -> Message:
        await self.cog_check(ctx)
        records = await self.bot.db.fetch(
            """
            SELECT user_id, username, plays
            FROM lastfm.albums
            WHERE album = $1
            AND artist = $2
            ORDER BY plays DESC
            """,
            album.name,
            album.artist,
        )
        if not records:
            return await ctx.fail(
                f"Nobody has listened to `{album.name}` by *`{album.artist}`*!"
            )

        items = []
        for index, listener in enumerate(records[:100], start=1):
            user = self.bot.get_user(listener.user_id)
            if not user:
                user = f"Unknown (`{listener.user_id}`)"
            else:
                user = shorten(user.name, 19)
            index = index

            rank = f"`{index}`"
            if index == 1:
                rank = "👑"

            items.append(
                f"{rank} [{user}](https://last.fm/user/{listener.username}) has {plural(listener.plays, md='**'):play}"
            )

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"Top listeners for {shorten(album.name, 12)} by {shorten(album.artist, 12)}",
            ),
            items,
        )
    
    @lastfm.command(name = "globalwktrack", aliases = ["gwkt"], description = "View the top listeners for a track globally", example = ",lastfm globalwktrack BANG BANG!")
    async def globalwktrack(
        self,
        ctx: Context,
        *,
        track: Track = param(
            default=Track.fallback,
        ),
    ) -> Message:
        await self.cog_check(ctx)
        records = await self.bot.db.fetch(
            """
            SELECT user_id, username, plays
            FROM lastfm.tracks
            WHERE track = $1
            AND artist = $2
            ORDER BY plays DESC
            """,
            track.name,
            track.artist,
        )
        if not records:
            return await ctx.fail(
                f"Nobody has listened to `{track.name}` by *`{track.artist}`*!"
            )

        items = []
        i = 0
        for index, listener in enumerate(records[:100], start=1):
            user = self.bot.get_user(listener.user_id)
            if not user:
                user = f"Unknown (`{listener.user_id}`)"
            else:
                user = shorten(user.name, 19)
            rank = f"`{index}`"
            if index == 1:
                rank = "👑"

            items.append(
                f"{rank} [{user}](https://last.fm/user/{listener.username}) has {plural(listener.plays, md='**'):play}"
            )

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"Top listeners for {shorten(track.name, 12)} by {shorten(track.artist, 12)}",
            ),
            items,
        )

    @lastfm.command(name="crowns", description="view your crowns")
    async def crowns(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        config = await self.bot.db.fetchrow(
            """SELECT * FROM lastfm.config WHERE user_id = $1""", ctx.author.id
        )
        plays = await self.bot.db.fetch("""
            WITH max_plays AS (
                SELECT user_id
                FROM lastfm.artists
                GROUP BY user_id
                ORDER BY SUM(plays) DESC
                LIMIT 1
            )
            SELECT artist, user_id, plays
            FROM lastfm.artists
            WHERE user_id = (SELECT user_id FROM max_plays);
        """)
        crowns = [u for u in plays if u.user_id == member.id]
        for c in crowns:
            ensure_future(
                self.bot.db.execute(
                    """INSERT INTO lastfm.crowns (guild_id, user_id, username, artist, plays) VALUES($1, $2, $3, $4, $5) ON CONFLICT(guild_id, artist) DO UPDATE SET user_id = excluded.user_id, username = excluded.username, plays = excluded.plays)""",
                    ctx.guild.id,
                    config.user_id,
                    config.username,
                    c.artist,
                    c.plays,
                )
            )
        if len(crowns) == 0:
            raise CommandError(
                f"{'you' if member == ctx.author else member.mention} {'has' if member != ctx.author else 'have'} not obtained any crowns"
            )
        embed = Embed(title="Crowns", color=ctx.author.color).set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
        )
        rows = [
            f"`{i}` [**{escape_md(artist.artist)}**](https://last.fm/music/{artist.artist.replace(' ','+')}) ({plural(artist.plays,):play})"
            for i, artist in enumerate(crowns, start=1)
        ]
        return await ctx.paginate(embed, rows, 10, "crown")

    @lastfm.command(
        name="wkalbum",
        aliases=["whoknowsalbum", "wka"],
    )
    async def lastfm_wkalbum(
        self,
        ctx: Context,
        *,
        album: Album = param(
            default=Album.fallback,
        ),
    ) -> Message:
        """
        View the top listeners for an album.
        """
        await self.cog_check(ctx)
        records = await self.bot.db.fetch(
            """
            SELECT user_id, username, plays
            FROM lastfm.albums
            WHERE user_id = ANY($3::BIGINT[])
            AND album = $1
            AND artist = $2
            ORDER BY plays DESC
            """,
            album.name,
            album.artist,
            [user.id for user in ctx.guild.members],
        )
        if not records:
            return await ctx.fail(
                f"Nobody in this server has listened to `{album.name}` by *`{album.artist}`*!"
            )

        items = []
        for index, listener in enumerate(records[:100], start=1):
            user = ctx.guild.get_member(listener.user_id)
            if not user:
                continue

            rank = f"`{index}`"
            if index == 1:
                rank = "👑"

            items.append(
                f"{rank} [{shorten(user.name, 19)}](https://last.fm/user/{listener.username}) has {plural(listener.plays, md='**'):play}"
            )

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"Top listeners for {shorten(album.name, 12)} by {shorten(album.artist, 12)}",
            ),
            items,
        )
    
    async def track_collage(self, ctx: Context, **kwargs):
        recents = await self.client.request(
            method="user.getrecenttracks",
            slug="recenttracks.track",
            username=ctx.lastfm.username,
            period=kwargs["timeperiod"],
            limit=int(kwargs['size'].split("x")[0]) * int(kwargs['size'].split('x')[1]),
        )

        async def get_track_image(data: dict):
            async with ClientSession() as session:
                async with session.get(data['image'][3]['#text']) as response:
                    image = await response.read()
            return {"a": f"{data['name']} - {data['artist']['#text']}", "image": image}
        
        image_data = [await get_track_image(d) for d in recents]

        @offloaded
        def read_image(data: list, size: str):
            a, b = map(int, size.split("x"))
            from PIL import Image, ImageDraw, ImageFont
            from io import BytesIO
            font = ImageFont.truetype("data/Arial.ttf", 20)
            images = []
            for artist in data:
                d = artist["image"]
                aa = artist["a"]
                try:
                    img = Image.open(BytesIO(d)).convert("RGB").resize((250, 250))
                except Exception:
                    img = Image.new("RGB", (250, 250))

                draw = ImageDraw.Draw(img)
                draw.text(
                    (5, 200),
                    f"{aa}",
                    fill="white",
                    font=font,  
                    stroke_width=1,
                    stroke_fill=0,
                )
                images.append(img)
            w, h = (250, 250)
            grid = Image.new("RGB", (int(a) * int(w), int(b) * int(h)))

            for i, image in enumerate(images):
                grid.paste(image, ((i % a) * w, (i // a) * h))
            buffer = BytesIO()
            grid.save(buffer, format="png")
            buffer.seek(0)
            return buffer.getvalue()
        return File(fp = BytesIO(await read_image(image_data, kwargs["size"])), filename = "chart.png")

    async def album_collage(self, ctx: Context, **kwargs):
        recents = await self.client.request(
            method="user.gettopalbums",
            slug="topalbums.album",
            username=ctx.lastfm.username,
            period=kwargs["timeperiod"],
            limit=int(kwargs['size'].split("x")[0]) * int(kwargs['size'].split('x')[1]),
        )

        async def get_album_image(data: dict):
            async with ClientSession() as session:
                try:
                    async with session.get(data['image'][3]['#text']) as response:
                        image = await response.read()
                except Exception:
                    async with session.get("https://lastfm.freetls.fastly.net/i/u/300x300/c6f59c1e5e7240a4c0d427abd71f3dbb.jpg") as response:
                        image = await response.read()
            return {"a": f"{data['name']} - {data['artist']['#text']}", "image": image, "plays": data['playcount']}

        image_data = await gather(*[get_album_image(d) for d in recents])
        image_data = sorted(image_data, key = lambda x: x['plays'], reverse = True)

        @offloaded
        def read_image(data: list, size: str):
            a, b = map(int, size.split("x"))
            from PIL import Image, ImageDraw, ImageFont
            from io import BytesIO
            font = ImageFont.truetype("data/Arial.ttf", 20)
            images = []
            for artist in data:
                d = artist["image"]
                aa = artist["a"]
                plays = artist["plays"]
                try:
                    img = Image.open(BytesIO(d)).convert("RGB").resize((250, 250))
                except Exception:
                    img = Image.new("RGB", (250, 250))

                draw = ImageDraw.Draw(img)
                draw.text(
                    (5, 200),
                    f"{plays} plays\n{aa}",
                    fill="white",
                    font=font,  
                    stroke_width=1,
                    stroke_fill=0,
                )
                images.append(img)
            w, h = (250, 250)
            grid = Image.new("RGB", (int(a) * int(w), int(b) * int(h)))

            for i, image in enumerate(images):
                grid.paste(image, ((i % a) * w, (i // a) * h))
            buffer = BytesIO()
            grid.save(buffer, format="png")
            buffer.seek(0)
            return buffer.getvalue()
        return File(fp = BytesIO(await read_image(image_data, kwargs["size"])), filename = "chart.png")

    
    async def artist_collage(self, ctx: Context, **kwargs):
        artists = await self.client.request(
            method="user.gettopartists",
            slug="topartists.artist",
            username=ctx.lastfm.username,
            period=kwargs["timeperiod"],
            limit=int(kwargs['size'].split("x")[0]) * int(kwargs['size'].split('x')[1]),
        )
        async def get_artist_image(data: dict):
            async with ClientSession() as session:
                async with session.get(data["url"]+"/+images") as response:
                    soup = BeautifulSoup(await response.read(), "html.parser")
                    image = soup.find("img", {"class": "image-list-image"})
                    if image is None:
                        try:
                            image = (
                                soup.find("li", {"class": "image-list-item-wrapper"})
                                .find("a")
                                .find("img")
                            )
                        except AttributeError:
                            image = None

                    if image is None:
                        image = data["image"][2]["#text"]
                    else:
                        image = image["src"]
                async with session.get(image) as response:
                    image = await response.read()

            return {"artist": data["name"], "image": image, "plays": data["playcount"]}
        image_data = [await get_artist_image(a) for a in artists]

        @offloaded
        def read_image(data: list, size: str):
            a, b = map(int, size.split("x"))
            from PIL import Image, ImageDraw, ImageFont
            from io import BytesIO
            font = ImageFont.truetype("data/Arial.ttf", 20)
            images = []
            for artist in data:
                d = artist["image"]
                plays = artist["plays"]
                aa = artist["artist"]
                try:
                    img = Image.open(BytesIO(d)).convert("RGB").resize((250, 250))
                except Exception:
                    img = Image.new("RGB", (250, 250))

                draw = ImageDraw.Draw(img)
                draw.text(
                    (5, 200),
                    f"{plays} Plays\n{aa}",
                    fill="white",
                    font=font,  
                    stroke_width=1,
                    stroke_fill=0,
                )
                images.append(img)
            w, h = (250, 250)
            grid = Image.new("RGB", (int(a) * int(w), int(b) * int(h)))

            for i, image in enumerate(images):
                grid.paste(image, ((i % a) * w, (i // a) * h))
            buffer = BytesIO()
            grid.save(buffer, format="png")
            buffer.seek(0)
            return buffer.getvalue()
        return File(fp = BytesIO(await read_image(image_data, kwargs["size"])), filename = "chart.png")

        
    
    @lastfm.command(name = "collage", description = "generate a collage out of your most listened artists in a timeperiod", example = ",lastfm collage --size 3x3 --timeframe 7d")
    async def lastfm_collage(self, ctx: Context, *, flags: CollageFlags):
        kwargs = {"chart_type": flags.chart_type or "recent", "size": flags.size or "3x3", "username": ctx.lastfm.username, "timeperiod": flags.time_period or "overall"}
        if kwargs["chart_type"] == "artist":
            file = await self.artist_collage(ctx, **kwargs)
        elif kwargs['chart_type'] == "album":
            file = await self.album_collage(ctx, **kwargs)
        elif kwargs['chart_type'] == "recent":
            file = await self.track_collage(ctx, **kwargs)
        embed = Embed(title = f"{ctx.lastfm.username}'s {kwargs['timeperiod']} {kwargs['chart_type']} collage")
        embed.set_image(url = "attachment://chart.png")
        return await ctx.send(embed = embed, file = file)
    
    @lastfm.command(
        name="wktrack",
        aliases=["whoknowstrack", "wkt"],
    )
    async def lastfm_wktrack(
        self,
        ctx: Context,
        *,
        track: Track = param(
            default=Track.fallback,
        ),
    ) -> Message:
        """
        View the top listeners for a track.
        """
        await self.cog_check(ctx)
        records = await self.bot.db.fetch(
            """
            SELECT user_id, username, plays
            FROM lastfm.tracks
            WHERE user_id = ANY($3::BIGINT[])
            AND track = $1
            AND artist = $2
            ORDER BY plays DESC
            """,
            track.name,
            track.artist,
            [user.id for user in ctx.guild.members],
        )
        if not records:
            return await ctx.fail(
                f"Nobody in this server has listened to `{track.name}` by *`{track.artist}`*!"
            )

        items = []
        for index, listener in enumerate(records[:100], start=1):
            user = ctx.guild.get_member(listener.user_id)
            if not user:
                continue

            rank = f"`{index}`"
            if index == 1:
                rank = "👑"

            items.append(
                f"{rank} [{shorten(user.name, 19)}](https://last.fm/user/{listener.username}) has {plural(listener.plays, md='**'):play}"
            )

        return await ctx.paginate(
            Embed(
                color=ctx.lastfm.color,
                title=f"Top listeners for {shorten(track.name, 12)} by {shorten(track.artist, 12)}",
            ),
            items,
        )
    
    @lastfm.command(name = "youtube", description = "Gives YouTube link for the current song playing", example = ",lastfm youtube @aiohttp")
    async def lastfm_youtube(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        """Get the YouTube link for the current song playing."""
        try:
            track, artist, album = await self.send_nowplaying(ctx, member, True)
        except Exception:
            raise CommandError("No playing track found")
        return await ctx.invoke(self.bot.get_command("youtube"), query=f"{track.name} {artist}")
    
    @lastfm.command(name = "itunes", description = "Gives iTunes link for the current song playing", example = ",lastfm itunes @aiohttp")
    async def lastfm_itunes(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        try:
            track, artist, album = await self.send_nowplaying(ctx, member, True)
        except Exception:
            raise CommandError("No playing track found")
        try:
            query = f"{track.name} {artist}"
            url = await itunes(query = query)
            return await ctx.send(url)
        except Exception:
            raise CommandError("that track could not be found")
        
    @lastfm.command(name = "spotify", description = "Gives Spotify link for the current song playing", example = ",lastfm spotify @aiohttp")
    async def lastfm_spotify(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        try:
            track, artist, album = await self.send_nowplaying(ctx, member, True)
            if url := await self.bot.db.fetchval("""SELECT spotify FROM lastfm.locations WHERE artist = $1 AND track = $2""", artist if isinstance(artist, str) else artist.get('name', artist.get('#text')), track.name):
                return await ctx.send(url)
            query = f"{track.name} {artist if isinstance(artist, str) else artist.get('name', artist.get('#text'))}"
        except Exception as e:
            if ctx.author.name == "aiohttp":
                raise e
            raise CommandError("No playing track found")
        data = await self.spotify_client.search_track(q=query)
        if not data:
            return await ctx.warn(f"No results found on Spotify for **{query}**")

        return await ctx.send(data.link)
    
    @lastfm.command(name = "soundcloud", description = "Gives Soundcloud link for the current song playing", example = ",lastfm soundcloud @aiohttp")
    async def lastfm_soundcloud(self, ctx: Context, *, member: Optional[Member] = commands.Author):
        try:
            track, artist, album = await self.send_nowplaying(ctx, member, True)
            query = f"{track.name} {artist}"
        except Exception:
            raise CommandError("No playing track found")
        try:
            url = await soundcloud(query = query, as_url = True, search_type = "tracks")
            return await ctx.send(content = url)
        except Exception as e:
            if ctx.author.name == "aiohttp":
                raise e
            raise CommandError(f"No results found on soundcloud {track.name} by {artist}")

    @command(
        name="spotifyalbum",
        example=",spotify album Lucki Freewave 3",
        aliases=["spalbum"],
    )
    async def spotifyalbum(self, ctx: Context, *, query: str = None) -> Message:
        """
        Finds album results from the Spotify API
        """

        if not query:
            try:
                await self.cog_check(ctx)
                track, artist, album = await self.send_nowplaying(ctx, ctx.author, True)
                query = f"{album}"
            except Exception:
                return await ctx.send_help()

        data = await self.spotify_client.search_album(q=query)
        if not data:
            return await ctx.warn(f"No results found on Spotify for **{query}**")

        return await ctx.send(data.link)

    @command(
        name="spotifytrack",
        usage="<query>",
        example="Lucki Geek Monster",
        aliases=[
            "sptrack",
            "spotify",
            "sp",
        ],
    )
    async def spotifytrack(self, ctx: Context, *, query: str = None) -> Message:
        """
        Finds track results from the Spotify API
        """

        if not query:
            try:
                await self.cog_check(ctx)
                track, artist, album = await self.send_nowplaying(ctx, ctx.author, True)
                if url := await self.bot.db.fetchval("""SELECT spotify FROM lastfm.locations WHERE artist = $1 AND track = $2""", artist, track.name):
                    return await ctx.send(url)
                query = f"{track.name} {artist}"
            except Exception:
                return await ctx.send_help()

        data = await self.spotify_client.search_track(q=query)
        if not data:
            return await ctx.warn(f"No results found on Spotify for **{query}**")

        return await ctx.send(data.link)
    
    @command(name = "itunes", description = "Finds a song from the iTunes API", example = ",itunes ram ranch")
    async def itunes(self, ctx: Context, *, query: str = None) -> Message:
        if not query:
            try:
                await self.cog_check(ctx)
                track, artist, album = await self.send_nowplaying(ctx, ctx.author, True)
                if url := await self.bot.db.fetchval("""SELECT itunes FROM lastfm.locations WHERE artist = $1 AND track = $2""", artist, track.name):
                    return await ctx.send(url)
                query = f"{track.name} {artist}"
            except Exception:
                return await ctx.send_help()
        try:
            url = await itunes(query = query)
        except Exception:
            url = None
        if not url:
            raise CommandError(f"No Results found for **{query[:20]}**")
        return await ctx.send(url)
    


async def setup(bot: Client):
    await bot.add_cog(LastFM(bot))