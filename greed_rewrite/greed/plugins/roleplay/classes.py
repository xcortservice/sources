from discord import Embed, Member, Message

from greed.framework import Context, Greed
from greed.framework.tools.utilities import ordinal

from .actions import ACTIONS

from yarl import URL
from aiohttp import ClientSession, TCPConnector
from typing import Optional, cast
from logging import getLogger
from random import randint

log = getLogger("Greed/roleplay")

BASE_URL = URL.build(scheme="https", host="nekos.best")


class NekoAPISend:
    """
    Class to handle sending requests to the Neko API and formatting the response as an embed.
    This class is used to fetch roleplay images and send them in a Discord channel.
    It also tracks the number of times a user has interacted with another user in a specific roleplay category.
    It uses the aiohttp library for making asynchronous HTTP requests and yarl for URL handling.
    Attributes:
        bot (Greed): The main bot instance.
    Methods:
        send(ctx: Context, member: Optional[Member], category: str) -> Message:
            Sends a request to the Neko API and returns the response as an embed.
        r2_send(ctx: Context, member: Optional[Member], category: str) -> Message:
            Sends a request to the R2 bucket and returns the response as an embed.
    """

    def __init__(self, bot: Greed):
        self.bot = bot

    async def send(
        self,
        ctx: Context,
        member: Optional[Member],
        category: str,
    ) -> Message:
        """
        Dispatches a request to the Neko API and sends the response as an embed.
        """
        url = BASE_URL.with_path(f"/api/v2/{category}")

        async with ctx.typing():
            connector = TCPConnector()

            async with ClientSession(
                connector=connector
            ) as session:
                async with session.get(
                    url,
                    # proxy=ctx.config.authentication.proxy
                ) as response:
                    try:
                        data = await response.json()
                        if not data.get("results"):
                            log.error(
                                f"API returned no results: {await response.text()}"
                            )
                            return await ctx.embed(
                                "Something went wrong, please try again later!",
                                "warned",
                            )

                    except Exception as e:
                        log.error(
                            f"Failed to parse API response: {str(e)} | Status: {response.status} | Body: {await response.text()}"
                        )
                        return await ctx.embed(
                            "Something went wrong, please try again later!",
                            "warned",
                        )

                embed = Embed(
                    color=ctx.author.top_role.color
                )
                amount = 0

                if member:
                    amount = 0
                    if member != ctx.author:
                        amount = cast(
                            int,
                            await self.bot.pool.fetchval(
                                """
                                INSERT INTO interactions (user1_id, user2_id, interaction, count)
                                VALUES ($1, $2, $3, 1)
                                ON CONFLICT (user1_id, user2_id, interaction)
                                DO UPDATE SET count = interactions.count + 1
                                RETURNING count
                                """,
                                ctx.author.id,
                                member.id,
                                category,
                            ),
                        )

                if (
                    member is not None
                    and member != ctx.author
                ):
                    embed.description = (
                        f"{ctx.author.mention} just **{ACTIONS[category]}** {member.mention}"
                        + (
                            f" for the **{ordinal(amount)}** time"
                            if member != ctx.author
                            and amount
                            else ""
                        )
                    )

                else:
                    embed.description = ""

                embed.set_author(
                    name=ctx.author.display_name,
                    icon_url=ctx.author.display_avatar,
                )
                embed.set_image(
                    url=data["results"][0]["url"]
                )
                return await ctx.send(embed=embed)

    async def r2_send(
        self,
        ctx: Context,
        member: Optional[Member],
        category: str,
    ) -> Message:
        """
        Dispatches a request to the R2 bucket and sends the response as an embed.
        """
        if category == "fuck":
            url = f"https://r2.evict.bot/roleplay/{category}/{category}{randint(1, 11)}.gif"

        if category == "nutkick":
            url = f"https://r2.evict.bot/roleplay/{category}/{category}{randint(1, 8)}.gif"

        if category == "spank":
            url = f"https://r2.evict.bot/roleplay/{category}/{category}{randint(1, 13)}.gif"

        async with ctx.typing():
            connector = TCPConnector()

            async with ClientSession(
                connector=connector
            ) as session:
                async with session.get(url) as response:
                    embed = Embed(
                        color=ctx.author.top_role.color
                    )
                    amount = 0

                if member:
                    amount = 0
                    if member != ctx.author:
                        amount = cast(
                            int,
                            await self.bot.pool.fetchval(
                                """
                                INSERT INTO interactions (user1_id, user2_id, interaction, count)
                                VALUES ($1, $2, $3, 1)
                                ON CONFLICT (user1_id, user2_id, interaction)
                                DO UPDATE SET count = interactions.count + 1
                                RETURNING count
                                """,
                                ctx.author.id,
                                member.id,
                                category,
                            ),
                        )

                if (
                    member is not None
                    and member != ctx.author
                ):
                    embed.description = (
                        f"{ctx.author.mention} just **{ACTIONS[category]}** {member.mention}"
                        + (
                            f" for the **{ordinal(amount)}** time"
                            if member != ctx.author
                            and amount
                            else ""
                        )
                    )

                else:
                    embed.description = ""

                embed.set_author(
                    name=ctx.author.display_name,
                    icon_url=ctx.author.display_avatar,
                )
                embed.set_image(url=url)
                return await ctx.send(embed=embed)