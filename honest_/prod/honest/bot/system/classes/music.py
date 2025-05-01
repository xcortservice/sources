import re
from asyncio import Queue
from typing import Literal, Optional, Union

from aiohttp import ClientSession
from async_timeout import timeout
from bs4 import BeautifulSoup
from data.config import CONFIG
from discord.ext.commands import CommandError
from pomice import Filter, Player, SearchType, Track, filters

from ..patch.context import Context

filters_aliases = {
    "nightcore": ["up-tempo", "speed-up", "fast"],
    "chipmunk": ["high-pitch", "squeaky", "alvin-style"],
    "karaoke": ["instrumental", "sing-along", "vocal removal"],
    "eightd": ["8d audio", "surround sound", "spatial audio"],
    "vaporwave": ["chillwave", "retro aesthetic", "lo-fi"],
    "soft": ["mellow", "gentle", "smooth"],
    "boost": ["enhancement", "amplify", "loudness"],
    "metal": ["heavy metal", "hard rock", "aggressive"],
    "flat": ["neutral", "no eq", "balanced"],
    "piano": ["keys", "grand piano", "soft keys"],
}


class FILTERS:
    @property
    def nightcore(self) -> filters.Timescale:
        return filters.Timescale(
            tag="NightCore",
            speed=1.2999999523162842,
            pitch=1.2999999523162842,
            rate=1,
        )

    @property
    def chipmunk(self) -> filters.Timescale:
        return filters.Timescale(
            tag="ChipMunk",
            speed=1.05,
            pitch=1.35,
            rate=1.25,
        )

    @property
    def karaoke(self) -> filters.Karaoke:
        return filters.Karaoke(
            tag="Karaoke_",
            level=1.0,
            mono_level=1.0,
            filter_band=220.0,
            filter_width=100.0,
        )

    @property
    def eightd(self) -> filters.Rotation:
        return filters.Rotation(rotation_hertz=0.2, tag="8D")

    @property
    def vaporwave(self) -> filters.Equalizer:
        return filters.Equalizer(
            tag="Vaporwave",
            levels=[
                (1, 0.3),
                (0, 0.3),
            ],
        )

    @property
    def vibrato(self) -> filters.Vibrato:
        return filters.Vibrato(frequency=10, depth=0.9, tag="Vibrato")

    @property
    def soft(self) -> filters.LowPass:
        return filters.LowPass(smoothing=20.0, tag="Soft")

    @property
    def boost(self) -> filters.Equalizer:
        return filters.Equalizer(
            tag="Boost",
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
        )

    @property
    def metal(self) -> filters.Equalizer:
        return filters.Equalizer(
            tag="Metal",
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
        )

    @property
    def flat(self) -> filters.Equalizer:
        return filters.Equalizer(
            tag="Flat",
            levels=[
                (0, 0.0),
                (1, 0.0),
                (2, 0.0),
                (3, 0.0),
                (4, 0.0),
                (5, 0.0),
                (6, 0.0),
                (7, 0.0),
                (8, 0.0),
                (9, 0.0),
                (10, 0.0),
                (11, 0.0),
                (12, 0.0),
                (13, 0.0),
                (14, 0.0),
            ],
        )

    @property
    def piano(self) -> filters.Equalizer:
        return filters.Equalizer(
            tag="Piano",
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
        )


Filters = FILTERS()


class BleedPlayer(Player):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.queue: Queue = Queue()
        self.track: Track = None
        self.loop: Literal["track", "queue", False] = False
        self.waiting: bool = False
        self.invoke_id: int = None

    async def get_tracks(
        self,
        query: str,
        *,
        ctx: Optional[Context] = None,
        search_type: Optional[SearchType] = None,
    ):
        if search_type:
            return await super().get_tracks(
                query=query, ctx=ctx, search_type=search_type
            )

        try:
            _ = await super().get_tracks(query=query, ctx=ctx)
            if not _:
                raise Exception()
            else:
                return _
        except Exception:
            return await super().get_tracks(
                query=query, ctx=ctx, search_type=SearchType.scsearch
            )

    async def insert(self, track: Track, bump: bool = False) -> Track:
        if bump:
            queue = self.queue._queue
            queue.insert(0, track)
        else:
            await self.queue.put(track)

        return track

    async def scrape_spotify(self, query: str) -> str:
        async with ClientSession() as session:
            async with session.get(query) as response:
                soup = BeautifulSoup(await response.read(), "html.parser")
                artist = soup.find(
                    "meta", attrs={"name": "music:musician_description"}
                ).attrs["content"]
                title = soup.find("meta", attrs={"name": "twitter:title"}).attrs[
                    "content"
                ]
        return f"{title} {artist}"

    async def next(self) -> Track:
        if self.is_playing or self.waiting:
            return

        self.waiting = True
        if self.loop == "track" and self.track:
            pass

        else:
            try:
                async with timeout(180):
                    self.track = await self.queue.get()
            except TimeoutError:
                if text_channel := self.guild.get_channel(self.invoke_id):
                    await text_channel.normal(
                        # Minutes
                        f"Left {self.channel.mention} due to **3 minutes** of inactivity",
                        color=0x6E879C,
                    )
                return await self.destroy()

        self.waiting = False

        if self.loop == "queue":
            await self.queue.put(self.track)

        await self.play(self.track)
        if (
            text_channel := self.guild.get_channel(self.invoke_id)
        ) and self.loop != "track":
            await text_channel.normal(
                f"{self.track.requester.mention}: Now playing [**{self.track.title}**]({self.track.uri}) in {self.channel.mention}",
                color=0x6E879C,
            )

    async def skip(self) -> Track:
        if self.is_paused:
            await self.set_pause(False)

        return await self.stop()

    async def add_filter(self, _filter: Filter):
        """Add a filter to the player"""
        return await super().add_filter(_filter, True)

    async def remove_filter(self, filter_tag: str):
        """Remove a filter from the player"""
        return await super().remove_filter(filter_tag, True)


APPLE_MUSIC_BUNDLE_REGEX = (
    r'<script type="module" crossorigin src="([a-zA-Z0-9.\-/]+)"><\/script>'
)
APPLE_MUSIC_TOKEN_REGEX = r'\w+="([A-Za-z0-9-_]*\.[A-Za-z0-9-_]*\.[A-Za-z0-9-_]*)",\w+="x-apple-jingle-correlation-key"'

CACHED_TOKEN = None


async def get_token():
    global CACHED_TOKEN
    if CACHED_TOKEN:
        return CACHED_TOKEN

    async with ClientSession() as session:
        async with session.get("https://music.apple.com/") as response:
            html = await response.text()

        bundle_url_match = re.search(APPLE_MUSIC_BUNDLE_REGEX, html)
        if not bundle_url_match:
            raise Exception("Bundle URL not found")

        bundle_url = f"https://music.apple.com/{bundle_url_match.group(1)}"

        async with session.get(bundle_url) as bundle_response:
            bundle = await bundle_response.text()

        token_match = re.search(APPLE_MUSIC_TOKEN_REGEX, bundle)
        if not token_match:
            raise Exception("Token not found")

        CACHED_TOKEN = token_match.group(1)
        return CACHED_TOKEN


async def itunes(**kwargs) -> str:
    artist = kwargs.pop("artist", None)
    track = kwargs.pop("track", None)
    if not artist and not track:
        query = kwargs.pop("query").lower()
    else:
        query = f"{track} {artist}".lower()
    query = query.replace(" ", "+")
    if not CACHED_TOKEN:
        await get_token()
    async with ClientSession() as session:
        async with session.get(
            f"https://amp-api-edge.music.apple.com/v1/catalog/us/search?art%5Bmusic-videos%3Aurl%5D=c&art%5Burl%5D=f&extend=artistUrl&fields%5Balbums%5D=artistName%2CartistUrl%2Cartwork%2CcontentRating%2CeditorialArtwork%2CeditorialNotes%2Cname%2CplayParams%2CreleaseDate%2Curl%2CtrackCount&fields%5Bartists%5D=url%2Cname%2Cartwork&format%5Bresources%5D=map&include%5Balbums%5D=artists&include%5Bmusic-videos%5D=artists&include%5Bsongs%5D=artists&include%5Bstations%5D=radio-show&l=en-US&limit=21&omit%5Bresource%5D=autos&platform=web&relate%5Balbums%5D=artists&relate%5Bsongs%5D=albums&term={query}&types=activities%2Calbums%2Capple-curators%2Cartists%2Ccurators%2Ceditorial-items%2Cmusic-movies%2Cmusic-videos%2Cplaylists%2Crecord-labels%2Csongs%2Cstations%2Ctv-episodes%2Cuploaded-videos&with=lyricHighlights%2Clyrics%2CnaturalLanguage%2CserverBubbles%2Csubtitles",
            headers={
                "Authorization": f"Bearer {CACHED_TOKEN}",
                "Cookie": "geo=US; aff=ewoJIjExLTEiID0gewoJCSJleHBpcmVzIiA9ICIxNzMwMDUyOTAwMDAwIjsKCQkiY2xpY2tUaW1lIiA9ICIxNzI3NDYwOTAwMDAwIjsKCQkidG9rZW4iID0gIjEwbDNTaCI7CgkJImFwcFR5cGUiID0gIjEiOwoJfTsKfQ==; s_cc=true; pt-dm=v1~x~84pc0mu8~m~2~n~itunes%20-%20index%20(us); mk_epub=%7B%22btuid%22%3A%221cj7gaw%22%2C%22events%22%3A%22event220%3D0.188%2Cevent221%3D0.000%2Cevent222%3D0.000%2Cevent223%3D0.000%2Cevent224%3D0.002%2Cevent225%3D0.002%2Cevent226%3D0.255%2Cevent227%3D0.003%2Cevent228%3D0.081%2Cevent229%3D0.342%2C%22%2C%22prop57%22%3A%22www.us.itunes%22%7D; dslang=US-EN; site=USA; wosid-replay=mpJfj4M67bqsrGzs7iFd0g; myacinfo=DAWTKNV323952cf8084a204fb20ab2508441a07d02d3b2e85e91451e55b31f916368d352098e8786c333755e47493ab415179459abd9672552c764685e2e98084999073b7e82665eee6661a32d1d5b3bf86dcd44be4ff3488908baf669a8b9019438f7bb9a3f08a13abe1129c95fae5535d53a654f6ccc8fc35ccc82f47c4453d09b495b286304d6d5400de7f23fcc8ae15d525e00d9fc52e182acaf0064f73fffa4da7bf50522f7cd8cdc1f3e73c4ab3fa7f71bcacb46f416f267cd11ef76330fa18c0c19fd9d44e968dbc75f5e4c0a345ad9a0c57baa3912aaeb755c716c90db7b850dd2a0ffe8dc640b2ac1923dc4d393c8dc9734c06fe014767616c897f5a9f075ef9ca394803808ba8cae83c323fbf77049bec4bf76f72beb64e494568668afc742c75ee44019e4d6f407ce7835328f5aaa58a7a12ad2c411e17f45f55797ea293bb038897bf298f1cc21316411c8c884167eb630e35161cb80a76911591ff35a4df515b31ab4b23b9251d0c4b6cacd0f0a5cf5919afcb5c0721ddadf37d96b27d4253a6507a781a9d5c3c7c9e2f5a339f5fc4850dfde87da3a5a054802b521dc36e8880d3010e787d37da7561015a08a4e67713cfc6d9c7847e7f9fb49464afec5763cb2ecc6de4f0218410fd900221e8ef5099d2db78f13e1c98cd5d134e0612633b4ca028c64dbe14ea89bc068f851984704a45a8ced046d0d97a84aa7a3fb0ffc0e8a016de306aef871369d77d0081dd54bbbcbd63460d3432f56547e170eec944f36e6ac765e170574783776a1ab6a45a1fb0fbd1ee9c162596d3423d783b8fe3c4afb6d2f4f8556ee295432f91b0c62b35da6fd03dbde0902b611359dc0250b302ea917f5f75015d7c0b8cd00fb0a414ade794ad73e87a6f2b4068895d1e75ff2585a47V3; itspod=22; commerce-authorization-token=AAAAAAAAAAKRoovgdiaDGOKSGKzNXNoFDWPM2YlEcO/bK0MJmNO8QyfJl6WzR0DzIT9diBNNpFdv6YEj8+4MW3QtAh7UhOfB7GC7yndUCTkojMiVkpTVreBdoltmIJd0fg2tZTbHXONvZQ72MMax9XICVf6/ZtO6WC+mozCGAIZX04GyE7y/9dK/+f5m5P3MtjWuJSawnhXOZJbsKevVLbGexREPo9aQPxkHdnrEHj8IAIAbyjCctA==; itspod=22; media-user-token=Aos2GxE3moMAWs29IzPmtZr6PdZ1ta34lDMDwiLcgyEmDvbSsp/ZZaPe7vZp+d5QNgBrZXfClOQOpcAsD1U6SKTXqKqdBr8YDJcarBUVIbEdBTJSYtNEilMvY41vTQFrru3IxDXXGMBF1PIi7BgK5w5YHXFwYkbAWhgVygYT8oAV5W9WyWbvz0uaQlxKEphlZPiIjaspN+jUe+7gmVR8u6JFmTXtPJ9yc6gep7SWV4vc6SCiew==; itua=US; pltvcid=daa5820fd33744319974771bb5e7b7d5022; pldfltcid=90e47fe97dce4dfc98f46c9bd1a47101022; mut-refresh=1; itre=0",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "origin": "https://music.apple.com",
                "accept-language": "en-US,en;q=0.9",
                "accept": "*/*",
            },
        ) as response:
            if response.content_type == "application/json":
                data = await response.json()
            else:
                if response.status == 401:
                    await get_token()
                    return await itunes(**kwargs)
                raise CommandError(f"ITunes Returned {response.status}")
    try:
        return data["resources"]["songs"][list(data["resources"]["songs"].keys())[0]][
            "attributes"
        ]["url"]
    except KeyError:
        return data


SOUNDCLOUD_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Host": "api-v2.soundcloud.com",
    "Origin": "https://soundcloud.com",
    "Pragma": "no-cache",
    "Referer": "https://soundcloud.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Sec-GPC": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Brave";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


async def soundcloud(**kwargs) -> str:
    artist = kwargs.pop("artist", None)
    track = kwargs.pop("track", None)
    as_url = kwargs.pop("as_url", True)
    as_urls = kwargs.pop("as_urls", False)
    search_type = kwargs.pop("search_type", "tracks")
    if not artist and not track:
        query = kwargs.pop("query").lower()
    else:
        query = f"{track} {artist}".lower()
    query = query.replace(" ", "%20")
    if not search_type:
        url = f"https://api-v2.soundcloud.com/search?q={query}&sc_a_id=4bb5bdd67159000f40681f22b6d47db77ecfad5d&variant_ids=&facet=model&user_id=8984-707174-97552-694722&client_id=Fs1xmKNbd3b0EiU1o1MHY4KfC41SVpjS&limit=20&offset=0&linked_partitioning=1&app_version=1727431820&app_locale=en"
    elif search_type == "tracks":
        url = f"https://api-v2.soundcloud.com/search/tracks?q={query}&sc_a_id=4bb5bdd67159000f40681f22b6d47db77ecfad5d&variant_ids=&facet=genre&user_id=8984-707174-97552-694722&client_id=Fs1xmKNbd3b0EiU1o1MHY4KfC41SVpjS&limit=20&offset=0&linked_partitioning=1&app_version=1727431820&app_locale=e"
    async with ClientSession() as session:
        async with session.get(url, headers=SOUNDCLOUD_HEADERS) as response:
            data = await response.json()
    if as_url:
        if not data.get("collections", data.get("collection")):
            raise TypeError(f"{data}")
        return data.get("collections", data.get("collection"))[0]["permalink_url"]
    elif as_urls:
        return [
            d["permalink_url"] for d in data.get("collections", data.get("collection"))
        ]
    else:
        return data.get("collections", data.get("collection"))
