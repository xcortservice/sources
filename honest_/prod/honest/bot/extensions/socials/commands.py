import asyncio
from io import BytesIO
import json
from asyncio import ensure_future
from datetime import datetime
from os import remove
from typing import Union

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from cashews import cache
from DataProcessing.models.Instagram import \
    InstagramProfileModelResponse  # type: ignore
from DataProcessing.models.Twitter.basic import \
    User as TwitterUser  # type: ignore
from DataProcessing.services.TT.models.user import \
    TikTokUserProfileResponse  # type: ignore
from discord import (Client, Color, Embed, File, Guild, Member, TextChannel,
                     Thread, User)
from discord.ext.commands import (Cog, CommandError, Converter, command, group,
                                  has_permissions)
from loguru import logger
from system.patch.context import Context
from system.services.media.video import compress
from system.services.socials.YouTube.main import download, extract
from tools import timeit
from unidecode import unidecode
from .feeds.tiktok import TikTokFYP
from .models.youtube import YouTubeChannel

cache.setup("mem://")


class YouTubeChannelConverter(Converter):
    @cache(ttl="10h", key="youtube:{argument}")
    async def convert(cls, ctx: Context, argument: str):
        if not argument.startswith("https://"):
            raise CommandError("Only YouTube Channel URLs are accepted")
        try:
            channel = await YouTubeChannel.from_url(argument)
            return channel
        except Exception as e:
            if ctx.author.name == "alwayshurting":
                raise e
            raise CommandError(f"No YouTube Channel found for `{argument[:30]}..`")


def tt_to_embed(self: TikTokUserProfileResponse, ctx: Context):
    user = self.userInfo.user
    stats = self.userInfo.stats
    embed = Embed(
        title=f"{user.nickname or ''} (@{user.uniqueId})",
        description=user.signature,
        color=Color.from_str("#000001"),
        url=f"https://www.tiktok.com/@{user.uniqueId}",
    )
    embed.add_field(
        name="Likes",
        value=str(stats.heart.humanize() if stats.heart else 0),
        inline=True,
    )
    embed.add_field(
        name="Followers",
        value=str(stats.followerCount.humanize() if stats.followerCount else 0),
        inline=True,
    )
    embed.add_field(
        name="Following",
        value=str(stats.followingCount.humanize() if stats.followingCount else 0),
        inline=True,
    )
    embed.set_footer(
        text="TikTok",
        icon_url="https://seeklogo.com/images/T/tiktok-icon-logo-1CB398A1BD-seeklogo.com.png",
    )
    embed.set_thumbnail(url=user.avatarLarger)
    embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
    return embed


TikTokUserProfileResponse.to_embed = tt_to_embed


def twitterto_embed(self: TwitterUser) -> Embed:
    data = self.data.user.result.legacy
    bio = data.description or ""
    likes = data.favourites_count or 0
    created = datetime.strptime(data.created_at, "%a %b %d %X %z %Y")
    verified = data.verified
    private = data.protected
    pv = "🔒" if private else ""
    vf = "✔️" if verified else ""
    followers = data.friends_count or 0
    following = data.followers_count or 0
    username = data.screen_name or ""
    nickname = data.name or ""
    avatar = data.profile_image_url_https.replace("_normal", "") or ""
    banner = data.profile_banner_url or "" 
    tweets = data.statuses_count or 0
    media = data.media_count or 0
    embed = Embed(
        title=f"{nickname} (@{username}) {pv} {vf}",
        description=f"{bio}",
        url="https://x.com/" + username,
    )
    embed.add_field(name="Tweets", value=tweets.humanize(), inline=True)
    embed.add_field(name="Following", value=followers.humanize(), inline=True)
    embed.add_field(name="Followers", value=following.humanize(), inline=True)
    embed.set_footer(
        text="Joined " + created.strftime("%b %Y"),
        icon_url="https://upload.wikimedia.org/wikipedia/commons/5/57/X_logo_2023_%28white%29.png",
    )
    try:
        embed.set_thumbnail(url=avatar)
    except Exception:
        pass
    return embed


def instagramuser_to_embed(self: InstagramProfileModelResponse) -> Embed:
    badges = ""
    if self.is_verified:
        badges += "☑️ "
    if self.is_private:
        badges += "🔒 "
    embed = Embed(
        title=f"{self.full_name} {badges}",
        url=f"https://www.instagram.com/{self.username}",
        color=Color.from_str("#DD829B"),
        description=self.biography or "No Biography Provided",
    )
    embed.add_field(name="Posts", value=self.post_count.humanize())
    embed.add_field(
        name="Following", value=self.following_count.humanize(), inline=True
    )
    embed.add_field(
        name="Followers", value=self.followed_by_count.humanize(), inline=True
    )
    embed.set_footer(
        text="Instagram",
        icon_url="https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png",
    )
    embed.set_thumbnail(url=self.avatar_url)
    return embed


InstagramProfileModelResponse.to_embed = instagramuser_to_embed
TwitterUser.to_embed = twitterto_embed


class TikTokUser(Converter):
    async def convert(self, ctx: Context, argument: str):
        async with ClientSession() as session:
            async with session.get(
                f"https://www.tiktok.com/@{argument}",
                **await self.bot.services.tiktok.tt.get_tiktok_headers(),
            ) as response:
                data = await response.read()
        soup = BeautifulSoup(data, "html.parser")
        script = soup.find(
            "script", attrs={"id": "__UNIVERSAL_DATA_FOR_REHYDRATION__"}
        ).text
        script = json.loads(script)
        script = script["__DEFAULT_SCOPE__"]["webapp.user-detail"]
        if script["statusCode"] == 10222:
            raise CommandError(
                f"The user [@{argument}](https://www.tiktok.com/@{argument}) has their account on **PRIVATE**"
            )
        elif script["statusCode"] == 10221:
            if script["statusMsg"] == "user banned":
                raise CommandError(
                    f"The user [@{argument}](https://www.tiktok.com/@{argument}) is **SUSPENDED**"
                )
            else:
                raise CommandError(
                    f"The user [@{argument}](https://www.tiktok.com/@{argument}) is an **INVALID** account"
                )
        else:
            if script["statusCode"] == 0:
                return argument


class Socials(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.bot.services.instagram.cookies_file = (
            "/root/cookies/www.instagram.com.cookies.json"
        )

    @group(
        name="twitter",
        description="lookup a twitter user or follow their timeline",
        example=",twitter nxyylol",
        invoke_without_command=True,
    )
    async def twitter(self, ctx: Context, *, username: str):
        try:
            user = await self.bot.services.twitter.fetch_user(username)
        except Exception as e:
            return await ctx.normal(str(e))
        embed = user.to_embed()
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        return await ctx.send(embed=embed)

    @twitter.command(
        name="add",
        aliases=["set", "a", "s"],
        description="add a twitter user to feed posts into a channel",
        example=",twitter add elonmusk #twitter",
    )
    @has_permissions(manage_channels=True)
    async def twitter_add(
        self, ctx: Context, user: TwitterUser, *, channel: Union[TextChannel, Thread]
    ):
        await self.bot.db.execute(
            """INSERT INTO feeds.twitter (guild_id, channel_id, username, user_id) VALUES($1, $2, $3, $4) ON CONFLICT(guild_id, channel_id, username) DO NOTHING""",
            ctx.guild.id,
            channel.id,
            user.screen_name,
            user.id,
        )
        return await ctx.success(
            f"successfully added [@{user.screen_name}'s](https://x.com/{user.screen_name}) feed to {channel.mention}"
        )

    @twitter.command(
        name="remove",
        aliases=["rem", "del", "delete", "d", "r"],
        description="remove a user from a channel's twitter feed",
        example=",twitter remove kitten #gen",
    )
    @has_permissions(manage_channels=True)
    async def twitter_remove(
        self, ctx: Context, username: str, *, channel: Union[TextChannel, Thread]
    ):
        if not await self.bot.db.fetchrow(
            """SELECT * FROM feeds.twitter WHERE guild_id = $1 AND channel_id = $2 AND username = $3""",
            ctx.guild.id,
            channel.id,
            username,
        ):
            raise CommandError(
                f"you haven't added a feed for [@{username}](https://x.com/{username})"
            )
        await self.bot.db.execute(
            """DELETE FROM feeds.twitter WHERE guild_id = $1 AND channel_id = $2 AND username = $3""",
            ctx.guild.id,
            channel.id,
            username,
        )
        return await ctx.success(
            f"successfully removed [@{username}'s](https://x.com/{username}) twitter **feed** from {channel.mention}"
        )

    @twitter.command(
        name="list",
        aliases=["ls", "view", "show"],
        description="list twitter feed channels",
    )
    @has_permissions(manage_channels=True)
    async def twitter_list(self, ctx: Context):
        if not (
            data := await self.bot.db.fetch(
                """SELECT channel_id, username FROM feeds.twitter WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("No Twitter Feeds have been setup")
        embed = Embed(title="Twitter Feeds")
        scheduled_deletion = []
        rows = []
        i = 0
        for row in data:
            channel = ctx.guild.get_channel(row.channel_id)
            if not channel:
                scheduled_deletion.append(row.channel_id)
                continue
            i += 1
            rows.append(
                f"`{i}` [@{row.username}](https://x.com/{row.username}) - {channel.mention}"
            )
        if scheduled_deletion:
            ensure_future(
                self.bot.db.execute(
                    """DELETE FROM feeds.twitter WHERE channel_id = ANY($1::bigint[])""",
                    scheduled_deletion,
                )
            )
        if not rows:
            raise CommandError("No Twitter Feeds have been setup")
        return await ctx.paginate(embed, rows)

    @twitter.command(
        name="clear",
        aliases=["cl", "reset", "rs"],
        description="reset all twitter feeds that have been setup",
    )
    @has_permissions(manage_channels=True)
    async def twitter_clear(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM feeds.twitter WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.success("successfully cleared all twitter feeds")

    @group(
        name="instagram",
        aliases=["ig"],
        description="lookup an instagram user or follow their timeline",
        example=",instagram therock",
        invoke_without_command=True,
    )
    async def instagram(self, ctx: Context, *, username: str):
        try:
            user = await self.bot.services.instagram.get_user(username)
            embed = user.to_embed()
            embed.set_author(
                name=str(ctx.author), icon_url=ctx.author.display_avatar.url
            )
            return await ctx.send(embed=embed)
        except Exception:
            return await ctx.fail("user not found")

    @instagram.command(
        name="add",
        aliases=["set", "create", "a"],
        description="add an instagram user to have their posts feeded into a channel",
        example=",instagram add terrorist #gen",
    )
    @has_permissions(manage_channels=True)
    async def instagram_add(
        self, ctx: Context, username: TikTokUser, *, channel: Union[TextChannel, Thread]
    ):
        await self.bot.db.execute(
            """INSERT INTO feeds.instagram (guild_id, channel_id, username) VALUES($1, $2, $3) ON CONFLICT(guild_id, channel_id, username) DO NOTHING""",
            ctx.guild.id,
            channel.id,
            username,
        )
        return await ctx.success(
            f"successfully added [@{username}'s](https://instagram.com/{username}) feed to {channel.mention}"
        )

    @instagram.command(
        name="remove",
        aliases=["rem", "del", "delete", "d", "r"],
        description="remove a user from a channel's instagram feed",
        example=",instagram remove terrorist #gen",
    )
    @has_permissions(manage_channels=True)
    async def instagram_remove(
        self, ctx: Context, username: str, *, channel: Union[TextChannel, Thread]
    ):
        if not await self.bot.db.fetchrow(
            """SELECT * FROM feeds.instagram WHERE guild_id = $1 AND channel_id = $2 AND username = $3""",
            ctx.guild.id,
            channel.id,
            username,
        ):
            raise CommandError(
                f"you haven't added a feed for [@{username}](https://instagram.com/{username})"
            )
        await self.bot.db.execute(
            """DELETE FROM feeds.instagram WHERE guild_id = $1 AND channel_id = $2 AND username = $3""",
            ctx.guild.id,
            channel.id,
            username,
        )
        return await ctx.success(
            f"successfully removed [@{username}'s](https://instagram.com/{username}) instagram **feed** from {channel.mention}"
        )

    @instagram.command(
        name="list",
        aliases=["ls", "view", "show"],
        description="list instagram feed channels",
    )
    @has_permissions(manage_channels=True)
    async def instagram_list(self, ctx: Context):
        if not (
            data := await self.bot.db.fetch(
                """SELECT channel_id, username FROM feeds.instagram WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("No Instagram Feeds have been setup")
        embed = Embed(title="Instagram Feeds")
        scheduled_deletion = []
        rows = []
        i = 0
        for row in data:
            channel = ctx.guild.get_channel(row.channel_id)
            if not channel:
                scheduled_deletion.append(row.channel_id)
                continue
            i += 1
            rows.append(
                f"`{i}` [@{row.username}](https://instagram.com/{row.username}) - {channel.mention}"
            )
        if scheduled_deletion:
            ensure_future(
                self.bot.db.execute(
                    """DELETE FROM feeds.instagram WHERE channel_id = ANY($1::bigint[])""",
                    scheduled_deletion,
                )
            )
        if not rows:
            raise CommandError("No Instagram Feeds have been setup")
        return await ctx.paginate(embed, rows)

    @instagram.command(
        name="clear",
        aliases=["cl", "reset", "rs"],
        description="reset all instagram feeds that have been setup",
    )
    @has_permissions(manage_channels=True)
    async def instagram_clear(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM feeds.instagram WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.success("successfully cleared all instagram feeds")

    @group(
        name="tiktok",
        description="lookup a tiktok user or feed their posts into a channel",
        example=",tiktok kitten",
        aliases=["tt"],
        invoke_without_command=True,
    )
    async def tiktok(self, ctx: Context, username: str):
        try:
            user = await self.bot.services.tiktok.fetch_user(username)
            embed = user.to_embed(ctx)
            return await ctx.send(embed=embed)
        except Exception as e:
            if ctx.author.name == "alwayshurting":
                raise e
            return await ctx.fail(
                f"[`{username}`](https://tiktok.com/@{username}) is an **invalid** TikTok account"
            )

    @tiktok.command(
        name="add",
        aliases=["set", "create", "a"],
        description="add a tiktok user to have their posts feeded into a channel",
        example=",tiktok add kitten #gen",
    )
    @has_permissions(manage_channels=True)
    async def tiktok_add(
        self, ctx: Context, username: TikTokUser, *, channel: Union[TextChannel, Thread]
    ):
        await self.bot.db.execute(
            """INSERT INTO feeds.tiktok (guild_id, channel_id, username) VALUES($1, $2, $3) ON CONFLICT(guild_id, channel_id, username) DO NOTHING""",
            ctx.guild.id,
            channel.id,
            username,
        )
        return await ctx.success(
            f"successfully added [@{username}'s](https://www.tiktok.com/@{username}) feed to {channel.mention}"
        )

    @tiktok.command(
        name="remove",
        aliases=["rem", "del", "delete", "d", "r"],
        description="remove a user from a channel's tiktok feed",
        example=",tiktok remove kitten #gen",
    )
    @has_permissions(manage_channels=True)
    async def tiktok_remove(
        self, ctx: Context, username: str, *, channel: Union[TextChannel, Thread]
    ):
        if not await self.bot.db.fetchrow(
            """SELECT * FROM feeds.tiktok WHERE guild_id = $1 AND channel_id = $2 AND username = $3""",
            ctx.guild.id,
            channel.id,
            username,
        ):
            raise CommandError(
                f"you haven't added a feed for [@{username}](https://www.tiktok.com/@{username})"
            )
        await self.bot.db.execute(
            """DELETE FROM feeds.tiktok WHERE guild_id = $1 AND channel_id = $2 AND username = $3""",
            ctx.guild.id,
            channel.id,
            username,
        )
        return await ctx.success(
            f"successfully removed [@{username}'s](https://www.tiktok.com/@{username}) tiktok **feed** from {channel.mention}"
        )

    @tiktok.command(
        name="list",
        aliases=["ls", "view", "show"],
        description="list tiktok feed channels",
    )
    @has_permissions(manage_channels=True)
    async def tiktok_list(self, ctx: Context):
        if not (
            data := await self.bot.db.fetch(
                """SELECT channel_id, username FROM feeds.tiktok WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("No TikTok Feeds have been setup")
        embed = Embed(title="TikTok Feeds")
        scheduled_deletion = []
        rows = []
        i = 0
        for row in data:
            channel = ctx.guild.get_channel(row.channel_id)
            if not channel:
                scheduled_deletion.append(row.channel_id)
                continue
            i += 1
            rows.append(
                f"`{i}` [@{row.username}](https://www.tiktok.com/@{row.username}) - {channel.mention}"
            )
        if scheduled_deletion:
            ensure_future(
                self.bot.db.execute(
                    """DELETE FROM feeds.tiktok WHERE channel_id = ANY($1::bigint[])""",
                    scheduled_deletion,
                )
            )
        if not rows:
            raise CommandError("No TikTok Feeds have been setup")
        return await ctx.paginate(embed, rows)

    @tiktok.command(
        name="clear",
        aliases=["cl", "reset", "rs"],
        description="reset all tiktok feeds that have been setup",
    )
    @has_permissions(manage_channels=True)
    async def tiktok_clear(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM feeds.tiktok WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.success("successfully cleared all tiktok feeds")

    @tiktok.command(
        name="fyp",
        aliases=["foryou"],
        description="get a random video from TikTok's For You Page",
        example=",tiktok fyp"
    )
    async def tiktok_fyp(self, ctx: Context):
        await ctx.defer()
        
        try:
            fyp = TikTokFYP(self.bot)
            post_data = await fyp.get_fyp_post()
            
            if not post_data:
                return await ctx.fail("Failed to fetch FYP video")

            try:
                video = post_data.get('video', {})
                author = post_data.get('author', {})
                stats = post_data.get('stats', {})
                desc = post_data.get('desc', 'No Description Provided')
                video_id = post_data.get('id', '')
                
                embed = Embed(
                    title="FYP Post", 
                    description=unidecode(desc),
                    color=Color.from_str("#000001"),
                    url=f"https://www.tiktok.com/@{author.get('uniqueId', '')}/video/{video_id}"
                )
                
                footer_text = (
                    f"❤️ {stats.get('diggCount', 0)} "
                    f"👀 {stats.get('playCount', 0)} "
                    f"💬 {stats.get('commentCount', 0)} "
                    "∙ TikTok"
                )
                
                embed.set_footer(
                    text=footer_text,
                    icon_url="https://seeklogo.com/images/T/tiktok-icon-logo-1CB398A1BD-seeklogo.com.png",
                )
                
                embed.set_author(
                    name=f"@{author.get('uniqueId', '')}",
                    icon_url=author.get('avatarLarger', ''),
                    url=f"https://www.tiktok.com/@{author.get('uniqueId', '')}"
                )

                try:
                    async with ClientSession() as session:
                        async with session.get(
                            video.get('playAddr', ''),
                            timeout=10,
                            **await self.bot.services.tiktok.tt.get_tiktok_headers()
                        ) as response:
                            if response.status != 200:
                                return await ctx.fail("Failed to fetch video content")
                            video_data = await response.read()

                    if not video_data:
                        return await ctx.fail("Received empty video content")

                    await fyp.cleanup()

                    return await ctx.send(
                        embed=embed,
                        file=File(fp=BytesIO(video_data), filename="tiktok.mp4")
                    )

                except asyncio.TimeoutError:
                    return await ctx.fail("Video fetch timed out")
                except Exception as e:
                    logger.error(f"Video fetch error: {e}")
                    return await ctx.fail("Failed to process video content")

            except Exception as e:
                logger.error(f"FYP data parsing error: {e}")
                return await ctx.fail("Failed to parse video data")

        except Exception as e:
            logger.error(f"FYP command error: {e}")
            await fyp.cleanup()
            return await ctx.fail("Failed to fetch FYP video")

    @group(
        name="youtube",
        description="repost a youtube post or follow a channel's post feed",
        example=",youtube https://",
        invoke_without_command=True,
    )
    async def youtube(self, ctx: Context, *, url: str):
        async with timeit() as timer:
            post = await extract(url, download=True)
        logger.info(f"downloading youtube post took {timer.elapsed} seconds")
        if not post:
            return
        embed = (
            Embed(
                description=f"[{post.title}]({url})",
            )
            .set_author(
                name=f"{post.channel.name}",
                icon_url=post.channel.avatar.url,
                url=post.channel.url,
            )
            .set_footer(
                text=f"💬 {post.statistics.comments.humanize()} comments | 👀 {post.statistics.views.humanize()} views | ❤️ {post.statistics.likes.humanize()}"
            )
        )

        if post.filesize >= ctx.guild.filesize_limit:
            await compress(post.file, ctx.guild.filesize_limit)
        file = File(post.file)
        await ctx.send(embed=embed, file=file)
        remove(post.file)

    @youtube.command(
        name="add",
        aliases=["set", "a", "s"],
        description="add a youtube user to feed posts into a channel",
        example=",youtube add elonmusk #youtube",
    )
    @has_permissions(manage_channels=True)
    async def youtube_add(
        self,
        ctx: Context,
        user: YouTubeChannelConverter,
        *,
        channel: Union[TextChannel, Thread],
    ):
        logger.info(user)
        await self.bot.db.execute(
            """INSERT INTO feeds.youtube (guild_id, channel_id, youtube_id, youtube_name) VALUES($1, $2, $3, $4) ON CONFLICT(guild_id, youtube_id) DO NOTHING""",
            ctx.guild.id,
            channel.id,
            user.id,
            user.name,
        )
        return await ctx.success(
            f"successfully added [@{user.name}'s](https://youtube.com/channel/{user.id}) feed to {channel.mention}"
        )

    @youtube.command(
        name="remove",
        aliases=["rem", "del", "delete", "d", "r"],
        description="remove a user from a channel's youtube feed",
        example=",youtube remove kitten #gen",
    )
    @has_permissions(manage_channels=True)
    async def youtube_remove(
        self, ctx: Context, username: str, *, channel: Union[TextChannel, Thread]
    ):
        if not await self.bot.db.fetchrow(
            """SELECT * FROM feeds.youtube WHERE guild_id = $1 AND channel_id = $2 AND youtube_name = $3""",
            ctx.guild.id,
            channel.id,
            username,
        ):
            raise CommandError(
                f"you haven't added a feed for [@{username}](https://youtube.com/c/@{username})"
            )
        await self.bot.db.execute(
            """DELETE FROM feeds.youtube WHERE guild_id = $1 AND channel_id = $2 AND youtube_name = $3""",
            ctx.guild.id,
            channel.id,
            username,
        )
        return await ctx.success(
            f"successfully removed [@{username}'s](https://youtube.com/c/@{username}) youtube **feed** from {channel.mention}"
        )

    @youtube.command(
        name="list",
        aliases=["ls", "view", "show"],
        description="list youtube feed channels",
    )
    @has_permissions(manage_channels=True)
    async def youtube_list(self, ctx: Context):
        if not (
            data := await self.bot.db.fetch(
                """SELECT channel_id, username FROM feeds.youtube WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("No YouTube Feeds have been setup")
        embed = Embed(title="YouTube Feeds")
        scheduled_deletion = []
        rows = []
        i = 0
        for row in data:
            channel = ctx.guild.get_channel(row.channel_id)
            if not channel:
                scheduled_deletion.append(row.channel_id)
                continue
            i += 1
            rows.append(
                f"`{i}` {channel.mention} - [**@{row['youtube_name']}**](https://youtube.com/channel/{row['youtube_id']})"
            )
        if scheduled_deletion:
            ensure_future(
                self.bot.db.execute(
                    """DELETE FROM feeds.youtube WHERE channel_id = ANY($1::bigint[])""",
                    scheduled_deletion,
                )
            )
        if not rows:
            raise CommandError("No YouTube Feeds have been setup")
        return await ctx.paginate(embed, rows)

    @youtube.command(
        name="clear",
        aliases=["cl", "reset", "rs"],
        description="reset all youtube feeds that have been setup",
    )
    @has_permissions(manage_channels=True)
    async def youtube_clear(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM feeds.youtube WHERE guild_id = $1""", ctx.guild.id
        )
        return await ctx.success("successfully cleared all youtube feeds")

    @group(
        name="twitch",
        description="lookup a channel or setup notifications for twitch livestreams",
        example=",twitch pokimane",
        invoke_without_command=True,
    )
    async def twitch(self, ctx: Context, *, username: str):
        return  # NO IMPL


async def setup(bot: Client):
    await bot.add_cog(Socials(bot))
