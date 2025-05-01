from typing import List

from discord.ext.commands import CommandError, Converter
from loguru import logger
from munch import Munch
from system.patch.context import Context
from typing_extensions import Type


class Timeframe(Converter[str]):
    def __init__(self: "Timeframe", period: str):
        self.period = period

    def __str__(self: "Timeframe") -> str:
        if self.period == "7day":
            return "weekly"

        elif self.period == "1month":
            return "monthly"

        elif self.period == "3month":
            return "past 3 months"

        elif self.period == "6month":
            return "past 6 months"

        elif self.period == "12month":
            return "yearly"

        return "overall"

    @classmethod
    async def convert(
        cls: Type["Timeframe"], ctx: Context, argument: str
    ) -> "Timeframe":
        if argument in (
            "weekly",
            "week",
            "1week",
            "7days",
            "7day",
            "7ds",
            "7d",
        ):
            return cls("7day")

        elif argument in (
            "monthly",
            "month",
            "1month",
            "1m",
            "30days",
            "30day",
            "30ds",
            "30d",
        ):
            return cls("1month")

        elif argument in (
            "3months",
            "3month",
            "3ms",
            "3m",
            "90days",
            "90day",
            "90ds",
            "90d",
        ):
            return cls("3month")

        elif argument in (
            "halfyear",
            "6months",
            "6month",
            "6mo",
            "6ms",
            "6m",
            "180days",
            "180day",
            "180ds",
            "180d",
        ):
            return cls("6month")

        elif argument in (
            "yearly",
            "year",
            "yr",
            "1year",
            "1y",
            "12months",
            "12month",
            "12mo",
            "12ms",
            "12m",
            "365days",
            "365day",
            "365ds",
            "365d",
        ):
            return cls("12month")

        return cls("overall")


class Artist(Converter[str]):
    @classmethod
    async def fallback(self: "Artist", ctx: Context) -> str:
        lastfm = ctx.bot.get_cog("LastFM")
        if not lastfm:
            raise CommandError("No LastFM Cog Found")

        if (
            not hasattr(ctx, "lastfm")
            and not hasattr(ctx, "_LastFMlastfm")
            and not hasattr(ctx, "_Contextlastfm")
        ):
            await lastfm.cog_check(ctx)
            if (
                not hasattr(ctx, "lastfm")
                and not hasattr(ctx, "_LastFMlastfm")
                and not hasattr(ctx, "_Contextlastfm")
            ):
                logger.info(dir(ctx))
        tracks: List[Munch] = await lastfm.client.request(
            method="user.getrecenttracks",
            username=getattr(
                ctx,
                "_LastFMlastfm",
                getattr(ctx, "_Contextlastfm", getattr(ctx, "lastfm", None)),
            ).username,
            slug="recenttracks.track",
            limit=1,
        )
        if not tracks:
            raise CommandError(
                f"Recent tracks aren't available for `{getattr(ctx, '_LastFMlastfm', getattr(ctx, '_Contextlastfm', None)).username}`!"
            )

        track = tracks[0]
        return track.artist["#text"]

    @classmethod
    async def convert(self: "Artist", ctx: Context, argument: str) -> str:
        lastfm = ctx.bot.get_cog("LastFM")
        if not lastfm:
            return
        if not hasattr(ctx, "_LastFMlastfm") and not hasattr(ctx, "_Contextlastfm"):
            logger.info(f"{dir(ctx)}")
            await lastfm.cog_check(ctx)
        artist: Munch = await lastfm.client.request(
            method="artist.getinfo",
            artist=argument,
            slug="artist",
        )
        if not artist:
            raise CommandError(f"Artist matching `{argument}` not found!")

        return artist.name


class Album:
    def __init__(self: "Album", name: str, artist: str):
        self.name = name
        self.artist = artist

    @classmethod
    async def fallback(cls: Type["Album"], ctx: Context) -> "Album":
        lastfm = ctx.bot.get_cog("LastFM")
        if not lastfm:
            return
        if (
            not hasattr(ctx, "lastfm")
            and not hasattr(ctx, "_LastFMlastfm")
            and not hasattr(ctx, "_Contextlastfm")
        ):
            await lastfm.cog_check(ctx)
            if (
                not hasattr(ctx, "lastfm")
                and not hasattr(ctx, "_LastFMlastfm")
                and not hasattr(ctx, "_Contextlastfm")
            ):
                logger.info(dir(ctx))

        tracks: List[Munch] = await lastfm.client.request(
            method="user.getrecenttracks",
            username=getattr(
                ctx,
                "_LastFMlastfm",
                getattr(ctx, "_Contextlastfm", getattr(ctx, "lastfm", None)),
            ).username,
            slug="recenttracks.track",
            limit=1,
        )
        if not tracks:
            raise CommandError(
                f"Recent tracks aren't available for `{getattr(ctx, '_LastFMlastfm', getattr(ctx, '_Contextlastfm', None)).username}`!"
            )

        track = tracks[0]
        if not track.album:
            raise CommandError("Your current track doesn't have an album!")

        return cls(
            name=track.album["#text"],
            artist=track.artist["#text"],
        )

    @classmethod
    async def convert(cls: Type["Album"], ctx: Context, argument: str) -> str:
        lastfm = ctx.bot.get_cog("LastFM")
        if not lastfm:
            return
        if (
            not hasattr(ctx, "lastfm")
            and not hasattr(ctx, "_LastFMlastfm")
            and not hasattr(ctx, "_Contextlastfm")
        ):
            await lastfm.cog_check(ctx)
            if (
                not hasattr(ctx, "lastfm")
                and not hasattr(ctx, "_LastFMlastfm")
                and not hasattr(ctx, "_Contextlastfm")
            ):
                logger.info(dir(ctx))

        albums: List[Munch] = await lastfm.client.request(
            slug="results.albummatches.album",
            method="album.search",
            album=argument,
        )
        if not albums:
            raise CommandError(f"Album matching `{argument}` not found!")

        album = albums[0]
        return cls(
            name=album.name,
            artist=album.artist,
        )


class Track:
    def __init__(self: "Track", name: str, artist: str):
        self.name = name
        self.artist = artist

    @classmethod
    async def fallback(cls: Type["Track"], ctx: Context) -> "Track":
        lastfm = ctx.bot.get_cog("LastFM")
        if not lastfm:
            return
        if (
            not hasattr(ctx, "lastfm")
            and not hasattr(ctx, "_LastFMlastfm")
            and not hasattr(ctx, "_Contextlastfm")
        ):
            await lastfm.cog_check(ctx)
            if (
                not hasattr(ctx, "lastfm")
                and not hasattr(ctx, "_LastFMlastfm")
                and not hasattr(ctx, "_Contextlastfm")
            ):
                logger.info(dir(ctx))

        tracks: List[Munch] = await lastfm.client.request(
            method="user.getrecenttracks",
            username=getattr(
                ctx,
                "_LastFMlastfm",
                getattr(ctx, "_Contextlastfm", getattr(ctx, "lastfm", None)),
            ).username,
            slug="recenttracks.track",
            limit=1,
        )
        if not tracks:
            raise CommandError(
                f"Recent tracks aren't available for `{getattr(ctx, '_LastFMlastfm', getattr(ctx, '_Contextlastfm', None)).username}`!"
            )

        track = tracks[0]
        return cls(
            name=track.name,
            artist=track.artist["#text"],
        )

    @classmethod
    async def convert(cls: Type["Track"], ctx: Context, argument: str) -> str:
        lastfm = ctx.bot.get_cog("LastFM")
        if not lastfm:
            return
        if (
            not hasattr(ctx, "lastfm")
            and not hasattr(ctx, "_LastFMlastfm")
            and not hasattr(ctx, "_Contextlastfm")
        ):
            await lastfm.cog_check(ctx)
            if (
                not hasattr(ctx, "lastfm")
                and not hasattr(ctx, "_LastFMlastfm")
                and not hasattr(ctx, "_Contextlastfm")
            ):
                logger.info(dir(ctx))

        tracks: List[Munch] = await lastfm.client.request(
            slug="results.trackmatches.track",
            method="track.search",
            track=argument,
        )
        if not tracks:
            raise CommandError(f"Track matching `{argument}` not found!")

        track = tracks[0]
        return cls(
            name=track.name,
            artist=track.artist,
        )
