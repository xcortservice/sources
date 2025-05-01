from __future__ import annotations

import asyncio
import discord
import random
import logging

from typing import Union, Dict
from datetime import datetime, timedelta

from discord.ext import commands
from discord.ext.commands import Cog

from greed.framework import Greed, Context
from greed.framework.pagination import Paginator
from greed.shared.config import Colors
from greed.shared.r2 import R2Client

logger = logging.getLogger("greed/plugins/config/autopfp")

VALID_CATEGORIES = {
    "anime",
    "cats",
    "com",
    "dogs",
    "eboy",
    "edgy",
    "egirls",
    "girls",
    "goth",
    "male",
    "matching",
    "scene",
}


class autopfp(Cog):
    def __init__(self, bot: "Greed"):
        self.bot = bot
        self.r2 = R2Client()
        self._batch_size = 50
        self._processing = False
        self._task = None
        self._last_processed = 0
        self._guild_timestamps: Dict[int, datetime] = {}

    async def setup_hook(self) -> None:
        self._task = self.bot.loop.create_task(self._process_batches())

    async def cog_unload(self) -> None:
        if self._task:
            self._task.cancel()

    async def _process_batches(self) -> None:
        while True:
            try:
                if not self._processing:
                    await self._process_guild_batch()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in autopfp batch processing: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _process_guild_batch(self) -> None:
        try:
            self._processing = True
            current_time = datetime.utcnow()

            self._guild_timestamps = {
                guild_id: timestamp
                for guild_id, timestamp in self._guild_timestamps.items()
                if (current_time - timestamp) < timedelta(minutes=3)
            }

            rows = await self.bot.db.fetch(
                "SELECT guild_id, channel_id, categories FROM autopfp ORDER BY guild_id"
            )

            processed_guilds = set()
            if hasattr(self.bot, "ipc") and self.bot.ipc is not None:
                try:
                    responses = await self.bot.ipc.broadcast("autopfp:get_processed")
                    for cluster_resp in responses.values():
                        processed_guilds.update(cluster_resp)
                except Exception as e:
                    logger.warning(f"Failed to get processed guilds via IPC: {e}")

            for row in rows:
                guild_id = row["guild_id"]
                last_sent = self._guild_timestamps.get(guild_id)

                if last_sent and (current_time - last_sent) < timedelta(minutes=1):
                    continue

                if guild_id in processed_guilds:
                    continue

                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                channel = guild.get_channel(row["channel_id"])
                if not channel:
                    continue

                categories = row["categories"]
                if "all" in categories:
                    category = random.choice(list(VALID_CATEGORIES))
                else:
                    category = random.choice(categories)

                try:
                    url = await self.r2.get_random_asset(category)
                    embed = discord.Embed(color=Colors().information)
                    embed.set_image(url=url)
                    image_name = url.split("/")[-1].split(".")[0]
                    embed.set_footer(
                        text=f"id: {image_name} • /autopfp report • /greedbot"
                    )

                    await channel.send(embed=embed)

                    if hasattr(self.bot, "ipc") and self.bot.ipc is not None:
                        try:
                            await self.bot.ipc.broadcast(
                                "autopfp:mark_processed", {"guild_id": guild_id}
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to mark guild as processed via IPC: {e}"
                            )

                    self._guild_timestamps[guild_id] = current_time

                except Exception as e:
                    logger.error(
                        f"Error sending autopfp for guild {guild.id}: {e}",
                        exc_info=True,
                    )

                delay = random.uniform(60, 180)
                await asyncio.sleep(delay)

        except Exception as e:
            logger.error(f"Error in _process_guild_batch: {e}", exc_info=True)
        finally:
            self._processing = False

    @commands.group(
        name="autopfp",
        usage="(subcommand) <args>",
        example=",autopfp",
        aliases=["pfp"],
        brief="Configure automatic profile picture updates",
        invoke_without_command=True,
    )
    @commands.has_permissions(manage_guild=True)
    async def autopfp(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command.qualified_name)

    @autopfp.command(
        name="add",
        usage="(channel) (category)",
        example=",autopfp add #pfp all",
        brief="Add a channel for automatic profile picture updates",
        aliases=["create"],
    )
    @commands.has_permissions(manage_guild=True)
    async def autopfp_add(
        self,
        ctx: Context,
        channel: Union[discord.TextChannel, discord.Thread],
        category: str,
    ):
        try:
            if category.lower() == "all":
                categories = ["all"]
            else:
                if category.lower() not in VALID_CATEGORIES:
                    return await ctx.embed(
                        f"Invalid category. Use `,autopfp categories` to see available categories.",
                        "warned",
                    )
                categories = [category.lower()]

            await self.bot.db.execute(
                "INSERT INTO autopfp (guild_id, channel_id, categories) VALUES ($1, $2, $3)",
                ctx.guild.id,
                channel.id,
                categories,
            )
            await ctx.embed(
                f"Added **autopfp** for {channel.mention} with category **{category}**",
                "approved",
            )
        except Exception as e:
            logger.error(f"Error in autopfp_add: {e}", exc_info=True)
            await ctx.embed(
                "An error occurred while adding the autopfp channel.", "warned"
            )

    @autopfp.command(
        name="remove",
        usage="(channel)",
        example=",autopfp remove #pfp",
        brief="Remove a channel from automatic profile picture updates",
        aliases=["delete", "del", "rm"],
    )
    @commands.has_permissions(manage_guild=True)
    async def autopfp_remove(
        self,
        ctx: Context,
        channel: Union[discord.TextChannel, discord.Thread],
    ):
        try:
            result = await self.bot.db.execute(
                "DELETE FROM autopfp WHERE guild_id = $1 AND channel_id = $2",
                ctx.guild.id,
                channel.id,
            )
            if result == "DELETE 0":
                return await ctx.embed(
                    f"There isn't an **autopfp** channel set for {channel.mention}",
                    "warned",
                )

            await ctx.embed(
                f"Removed the **autopfp** for {channel.mention}",
                "approved",
            )
        except Exception as e:
            logger.error(f"Error in autopfp_remove: {e}", exc_info=True)
            await ctx.embed(
                "An error occurred while removing the autopfp channel.", "warned"
            )

    @autopfp.command(
        name="list",
        aliases=["show", "all"],
        brief="List all channels configured for automatic profile picture updates",
        example=",autopfp list",
    )
    @commands.has_permissions(manage_guild=True)
    async def autopfp_list(self, ctx: Context):
        try:
            rows = await self.bot.db.fetch(
                "SELECT channel_id, categories FROM autopfp WHERE guild_id = $1",
                ctx.guild.id,
            )

            if not rows:
                return await ctx.embed(
                    "No **autopfp** channels have been set up", "warned"
                )

            autopfp_channels = []
            for row in rows:
                if channel := ctx.guild.get_channel(row["channel_id"]):
                    categories = ", ".join(row["categories"])
                    autopfp_channels.append(f"{channel.mention} - **{categories}**")

            embed = discord.Embed(
                title="AutoPFP Channels",
                color=Colors().information,
            )
            paginator = Paginator(ctx, autopfp_channels, embed=embed)
            await paginator.start()

        except Exception as e:
            logger.error(f"Error in autopfp_list: {e}", exc_info=True)
            await ctx.embed(
                "An error occurred while listing autopfp channels.", "warned"
            )

    @autopfp.command(
        name="categories",
        aliases=["cats"],
        brief="List all available categories",
        example=",autopfp categories",
    )
    @commands.has_permissions(manage_guild=True)
    async def autopfp_categories(self, ctx: Context):
        try:
            embed = discord.Embed(
                title="Available Categories",
                description="\n".join(
                    f"• **{cat}**" for cat in sorted(VALID_CATEGORIES)
                ),
                color=Colors().information,
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in autopfp_categories: {e}", exc_info=True)
            await ctx.embed("An error occurred while listing categories.", "warned")

    @commands.hybrid_command(
        name="report",
        brief="Report an inappropriate autopfp image",
        example=",autopfp report dogs image",
    )
    @commands.has_permissions(manage_guild=True)
    async def autopfp_report(
        self,
        ctx: Context,
        category: str,
        image_id: str,
    ):
        try:
            if category.lower() not in VALID_CATEGORIES:
                return await ctx.embed(
                    f"Invalid category. Use `,autopfp categories` to see available categories.",
                    "warned",
                )

            full_path = f"avatars/{category}/{image_id}"
            logger.info(
                f"Report received for image {full_path} in category {category} from {ctx.author}"
            )

            await ctx.embed(
                f"Report submitted for image in category **{category}**.\nThe moderation team will review it shortly.",
                "approved",
            )

        except Exception as e:
            logger.error(f"Error in autopfp_report: {e}", exc_info=True)
            await ctx.embed("An error occurred while submitting the report.", "warned")


async def setup(bot: Greed) -> None:
    await bot.add_cog(autopfp(bot))
