import discord
from discord import Embed
from discord.ext import commands
from discord.ext.commands import Cog, group, has_permissions
from typing import Optional

from greed.framework import Context
from greed.framework.pagination import Paginator

from greed.framework import Greed


class WordStats(Cog):
    def __init__(self, bot: "Greed"):
        self.bot = bot

    @commands.group(name="wordstats", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def wordstats(self, ctx: Context) -> discord.Message:
        """
        Manage word statistics settings
        """
        if ctx.subcommand_passed is not None:
            return await ctx.send_help(ctx.command)

        config = await self.bot.db.fetchrow(
            """
            SELECT enabled, count_bots, channel_whitelist, channel_blacklist
            FROM stats.config
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        if not config:
            await self.bot.db.execute(
                """
                INSERT INTO stats.config (guild_id, enabled, count_bots)
                VALUES ($1, $2, $3)
                """,
                ctx.guild.id,
                False,
                False,
            )
            config = {
                "enabled": False,
                "count_bots": False,
                "channel_whitelist": None,
                "channel_blacklist": None,
            }

        embed = Embed(title="Word Statistics Settings", color=0x2D2B31)
        embed.add_field(
            name="Status",
            value="Enabled" if config["enabled"] else "Disabled",
            inline=False,
        )
        embed.add_field(
            name="Count Bot Messages",
            value="Yes" if config["count_bots"] else "No",
            inline=False,
        )
        if config["channel_whitelist"]:
            channels = [f"<#{cid}>" for cid in config["channel_whitelist"]]
            embed.add_field(
                name="Whitelisted Channels",
                value=", ".join(channels) if channels else "None",
                inline=False,
            )
        if config["channel_blacklist"]:
            channels = [f"<#{cid}>" for cid in config["channel_blacklist"]]
            embed.add_field(
                name="Blacklisted Channels",
                value=", ".join(channels) if channels else "None",
                inline=False,
            )

        await ctx.send(embed=embed)

    @wordstats.command()
    @has_permissions(manage_guild=True)
    async def enable(self, ctx: Context):
        """
        Enable word statistics tracking
        """
        await self.bot.db.execute(
            """
            INSERT INTO stats.config (guild_id, enabled)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) 
            DO UPDATE SET enabled = $2
            """,
            ctx.guild.id,
            True,
        )
        await ctx.embed("Word statistics tracking has been enabled.", "approved")

    @wordstats.command()
    @has_permissions(manage_guild=True)
    async def disable(self, ctx: Context):
        """
        Disable word statistics tracking
        """
        await self.bot.db.execute(
            """
            INSERT INTO stats.config (guild_id, enabled)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) 
            DO UPDATE SET enabled = $2
            """,
            ctx.guild.id,
            False,
        )
        await ctx.embed("Word statistics tracking has been disabled.", "warned")

    @wordstats.command()
    @has_permissions(manage_guild=True)
    async def bots(self, ctx, count: bool):
        """
        Toggle whether to count bot messages
        """
        await self.bot.db.execute(
            """
            INSERT INTO stats.config (guild_id, count_bots)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) 
            DO UPDATE SET count_bots = $2
            """,
            ctx.guild.id,
            count,
        )
        await ctx.embed(
            f"Bot message counting has been {'enabled' if count else 'disabled'}.",
            "approved",
        )

    @wordstats.command()
    @has_permissions(manage_guild=True)
    async def whitelist(self, ctx, channel: discord.TextChannel):
        """
        Add a channel to the whitelist
        """
        config = await self.bot.db.fetchrow(
            """
            SELECT channel_whitelist
            FROM stats.config
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        whitelist = (
            config["channel_whitelist"]
            if config and config["channel_whitelist"]
            else []
        )
        if channel.id in whitelist:
            await ctx.embed("This channel is already whitelisted.", "warned")
            return

        whitelist.append(channel.id)
        await self.bot.db.execute(
            """
            INSERT INTO stats.config (guild_id, channel_whitelist)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) 
            DO UPDATE SET channel_whitelist = $2
            """,
            ctx.guild.id,
            whitelist,
        )
        await ctx.embed(f"Added {channel.mention} to the whitelist.", "approved")

    @wordstats.command()
    @has_permissions(manage_guild=True)
    async def blacklist(self, ctx, channel: discord.TextChannel):
        """
        Add a channel to the blacklist
        """
        config = await self.bot.db.fetchrow(
            """
            SELECT channel_blacklist
            FROM stats.config
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        blacklist = (
            config["channel_blacklist"]
            if config and config["channel_blacklist"]
            else []
        )
        if channel.id in blacklist:
            await ctx.embed("This channel is already blacklisted.", "warned")
            return

        blacklist.append(channel.id)
        await self.bot.db.execute(
            """
            INSERT INTO stats.config (guild_id, channel_blacklist)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) 
            DO UPDATE SET channel_blacklist = $2
            """,
            ctx.guild.id,
            blacklist,
        )
        await ctx.embed(f"Added {channel.mention} to the blacklist.", "approved")

    @wordstats.command()
    @has_permissions(manage_guild=True)
    async def remove_whitelist(self, ctx, channel: discord.TextChannel):
        """
        Remove a channel from the whitelist
        """
        config = await self.bot.db.fetchrow(
            """
            SELECT channel_whitelist
            FROM stats.config
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        if (
            not config
            or not config["channel_whitelist"]
            or channel.id not in config["channel_whitelist"]
        ):
            await ctx.embed("This channel is not whitelisted.", "warned")
            return

        whitelist = [cid for cid in config["channel_whitelist"] if cid != channel.id]
        await self.bot.db.execute(
            """
            UPDATE stats.config
            SET channel_whitelist = $2
            WHERE guild_id = $1
            """,
            ctx.guild.id,
            whitelist,
        )
        await ctx.embed(f"Removed {channel.mention} from the whitelist.", "approved")

    @wordstats.command()
    @has_permissions(manage_guild=True)
    async def remove_blacklist(self, ctx, channel: discord.TextChannel):
        """
        Remove a channel from the blacklist
        """
        config = await self.bot.db.fetchrow(
            """
            SELECT channel_blacklist
            FROM stats.config
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        if (
            not config
            or not config["channel_blacklist"]
            or channel.id not in config["channel_blacklist"]
        ):
            await ctx.embed("This channel is not blacklisted.", "warned")
            return

        blacklist = [cid for cid in config["channel_blacklist"] if cid != channel.id]
        await self.bot.db.execute(
            """
            UPDATE stats.config
            SET channel_blacklist = $2
            WHERE guild_id = $1
            """,
            ctx.guild.id,
            blacklist,
        )
        await ctx.embed(f"Removed {channel.mention} from the blacklist.", "approved")

    @wordstats.command(name="stats")
    async def wordstats_stats(
        self, ctx: Context, word: str, user: Optional[discord.Member] = None
    ) -> discord.Message:
        """
        View statistics for a specific word.
        word: The word to check
        user: Optional user to check stats for
        """
        word = word.lower()
        user_id = user.id if user else ctx.author.id

        stats = await self.bot.db.fetchrow(
            """
            SELECT count, last_used
            FROM stats.word_usage
            WHERE guild_id = $1 AND word = $2 AND user_id = $3
            """,
            ctx.guild.id,
            word,
            user_id,
        )

        if not stats:
            return await ctx.embed(f"No usage found for word **{word}**", "warned")

        embed = Embed(title=f"Word Statistics: {word}", color=0xCCCCFF)

        target = user or ctx.author
        embed.description = (
            f"**{target.mention}** has said **{word}** {stats['count']:,} times"
        )
        embed.add_field(
            name="Last Used", value=discord.utils.format_dt(stats["last_used"], "R")
        )

        return await ctx.send(embed=embed)

    @wordstats.command(name="top")
    async def wordstats_top(
        self, ctx: Context, word: str, limit: int = 10
    ) -> discord.Message:
        """
        View top users for a specific word.
        word: The word to check
        limit: Number of users to show (default: 10)
        """
        word = word.lower()

        data = await self.bot.db.fetch(
            """
            SELECT user_id, count
            FROM stats.word_usage
            WHERE guild_id = $1 AND word = $2
            ORDER BY count DESC
            LIMIT $3
            """,
            ctx.guild.id,
            word,
            limit,
        )

        if not data:
            return await ctx.embed(f"No usage found for word **{word}**", "warned")

        embed = Embed(title=f"Top Users for: {word}", color=0xCCCCFF)

        pages = []
        for i, row in enumerate(data, 1):
            user = ctx.guild.get_member(row["user_id"])
            user_text = user.mention if user else f"Unknown User ({row['user_id']})"
            pages.append(f"{i}. {user_text}: {row['count']:,} times")

        paginator = Paginator(ctx, pages=pages, embed=embed, per_page=10)
        return await paginator.start()

    @wordstats.group(name="command", aliases=["cmd"], invoke_without_command=True)
    async def wordstats_command(self, ctx: Context) -> discord.Message:
        """
        Create custom commands to track specific words.
        """
        return await ctx.send_help(ctx.command)

    @wordstats_command.command(name="add", example="fword fuck")
    async def wordstats_command_add(
        self, ctx: Context, command: str, word: str
    ) -> discord.Message:
        """Create a custom command to track a word"""
        command = command.lower()
        word = word.lower()

        if self.bot.get_command(command):
            return await ctx.embed(
                f"Command `{command}` already exists as a bot command!", "warned"
            )

        existing = await self.bot.db.fetchrow(
            """
            SELECT command
            FROM stats.custom_commands
            WHERE guild_id = $1 AND command = $2
            """,
            ctx.guild.id,
            command,
        )

        if existing:
            return await ctx.embed(
                f"Command `{command}` already exists for this server!", "warned"
            )

        await self.bot.db.execute(
            """
            INSERT INTO stats.custom_commands (guild_id, command, word, created_by)
            VALUES ($1, $2, $3, $4)
            """,
            ctx.guild.id,
            command,
            word,
            ctx.author.id,
        )
        return await ctx.embed(
            f"Created command `{command}` to track the word **{word}**!",
            "approved",
        )

    @wordstats_command.command(name="remove", example="fword")
    async def wordstats_command_remove(
        self, ctx: Context, command: str
    ) -> discord.Message:
        """Remove a custom word tracking command"""
        command = command.lower()
        result = await self.bot.db.execute(
            """
            DELETE FROM stats.custom_commands
            WHERE guild_id = $1 AND command = $2
            """,
            ctx.guild.id,
            command,
        )

        if result == "DELETE 0":
            return await ctx.embed(f"Command `{command}` doesn't exist!", "warned")

        return await ctx.embed(f"Removed command `{command}`!", "approved")

    @wordstats_command.command(name="list")
    async def wordstats_command_list(self, ctx: Context) -> discord.Message:
        """View all custom word tracking commands"""
        data = await self.bot.db.fetch(
            """
            SELECT command, word, created_by, created_at
            FROM stats.custom_commands
            WHERE guild_id = $1
            ORDER BY command
            """,
            ctx.guild.id,
        )

        if not data:
            return await ctx.embed("No custom commands configured!", "warned")

        embed = Embed(title="Custom Word Commands")
        pages = [
            f"`;{cmd['command']}` tracks **{cmd['word']}** - Created by {ctx.guild.get_member(cmd['created_by']).mention} "
            f"({discord.utils.format_dt(cmd['created_at'], 'R')})"
            for cmd in data
        ]

        paginator = Paginator(ctx, pages=pages, embed=embed, per_page=10)
        return await paginator.start()

    async def process_custom_command(
        self, ctx: Context, command: str
    ) -> Optional[discord.Message]:
        """Process a custom word tracking command"""
        data = await self.bot.db.fetchrow(
            """
            SELECT word
            FROM stats.custom_commands
            WHERE guild_id = $1 AND command = $2
            """,
            ctx.guild.id,
            command,
        )

        if not data:
            return None

        word = data["word"]

        target_id = (
            ctx.message.mentions[0].id if ctx.message.mentions else ctx.author.id
        )

        stats = (
            await self.bot.db.fetchval(
                """
            SELECT count
            FROM stats.word_usage
            WHERE guild_id = $1 AND word = $2 AND user_id = $3
            """,
                ctx.guild.id,
                word,
                target_id,
            )
            or 0
        )

        user = ctx.guild.get_member(target_id)
        user_text = user.mention if user else f"Unknown User ({target_id})"

        embed = Embed(
            description=f"{user_text} has said **{word}** {stats:,} times",
            color=0xCCCCFF,
        )
        return await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(WordStats(bot))
