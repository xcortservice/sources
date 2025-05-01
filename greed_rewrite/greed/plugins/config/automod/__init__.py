import discord
import humanfriendly

from datetime import timedelta
from asyncio import gather
from typing import (
    Union, 
    List, 
    Optional, 
    Dict, 
    Any, 
    Literal
)

from discord import (
    Guild, 
    Embed, 
    Member, 
    Role, 
    TextChannel, 
    AutoModTrigger, 
    AutoModRuleTriggerType, 
    AutoModRuleEventType, 
    AutoModRuleAction, 
    AutoModRuleActionType
)
from discord.ext.commands import (
    Cog,
    group,
    CommandError,
    has_permissions,
    bot_has_permissions,
)

from greed.shared.config import Colors
from greed.framework import Context, Greed
from greed.framework.discord.migrate import clear_keywords, add_keyword

TUPLE = ()
DICT = {}

default_timeout = 20


class Automod(Cog):
    def __init__(self, bot: Greed) -> None:
        self.bot = bot
        self.cache: Dict[int, List[str]] = {}
        self.filter_whitelist: Dict[int, List[int]] = {}
        self.filter_settings: Dict[int, Dict[str, Dict[str, Any]]] = {}
        self.filter_timeouts: Dict[int, str] = {}

    async def get_filter_settings(self, guild_id: int) -> Dict[str, Dict[str, Any]]:
        """
        Get filter settings from cache or database
        """
        if guild_id not in self.filter_settings:
            records = await self.bot.db.fetch(
                """
                SELECT event, is_enabled, threshold 
                FROM filter_event 
                WHERE guild_id = $1
                """,
                guild_id,
            )
            self.filter_settings[guild_id] = {
                record["event"]: {
                    "is_enabled": record["is_enabled"],
                    "threshold": record["threshold"],
                }
                for record in records
            }
        return self.filter_settings[guild_id]

    async def get_filter_timeout(self, guild_id: int) -> str:
        """
        Get filter timeout from cache or database
        """
        if guild_id not in self.filter_timeouts:
            timeout = await self.bot.db.fetchval(
                """
                SELECT timeframe 
                FROM automod_timeout 
                WHERE guild_id = $1
                """,
                guild_id,
            )
            self.filter_timeouts[guild_id] = timeout or "20s"
        
        return self.filter_timeouts[guild_id]

    async def update_filter_settings(self, guild_id: int) -> None:
        """
        Update filter settings in cache
        """
        if guild_id in self.filter_settings:
            del self.filter_settings[guild_id]
        await self.get_filter_settings(guild_id)

    async def update_filter_timeout(self, guild_id: int) -> None:
        """
        Update filter timeout in cache
        """
        if guild_id in self.filter_timeouts:
            del self.filter_timeouts[guild_id]
        await self.get_filter_timeout(guild_id)

    async def check_setup(self, guild: Guild) -> bool:
        """
        Check if the filter has been setup.
        """
        if not await self.bot.db.fetchrow(
            """
            SELECT * FROM filter_setup 
            WHERE guild_id = $1
            """,
            guild.id,
        ):
            raise CommandError(
                "Filter has not been setup with the `filter setup` command"
            )

        return True

    @group(
        name="filter",
        aliases=(
            "chatfilter",
            "automod",
        ),
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def filter(self, ctx: Context) -> None:
        """
        View a variety of options to help clean the chat.
        """
        return await ctx.send_help(ctx.command)

    @filter.command(name="clear")
    @has_permissions(manage_guild=True)
    async def filter_clear(self, ctx: Context) -> None:
        """
        Clear all filtered words
        """
        await self.check_setup(ctx.guild)
        await clear_keywords(ctx.guild)

        record = await self.bot.db.fetch(
            """
            SELECT * FROM filter 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )
        if not record:
            return await ctx.embed(
                message="There aren't any filtered words in this server!",
                message_type="warned",
            )

        await self.bot.db.execute(
            """
            DELETE FROM filter 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        await self.bot.cache.setup_filter()
        return await ctx.embed(
            message="Removed all filtered words from the filter list",
            message_type="approved",
        )

    @filter.command(name="add", aliases=["create"])
    @has_permissions(manage_guild=True)
    async def filter_add(self, ctx: Context, *, keywords: str) -> None:
        """
        Add a word to the filter.
        """
        await self.check_setup(ctx.guild)

        if "," in keywords:
            keywords = [f.strip() for f in keywords.split(",")]
        else:
            keywords = [keywords]

        for keyword in keywords:
            record = await self.bot.db.fetch(
                """
                SELECT * FROM filter 
                WHERE guild_id = $1 
                AND keyword = $2
                """,
                ctx.guild.id,
                keyword,
            )
            if record:
                return await ctx.embed(
                    message="That is already a filtered word!", 
                    message_type="warned"
                )

            if len(keyword.split()) > 1:
                return await ctx.embed(
                    message="The keyword must be one word!", 
                    message_type="warned"
                )

            if len(keyword) > 32:
                return await ctx.embed(
                    message="Please provide a valid keyword under 32 characters!",
                    message_type="warned",
                )

            await self.bot.db.execute(
                """
                INSERT INTO filter (guild_id, keyword) 
                VALUES ($1, $2)
                """,
                ctx.guild.id,
                keyword,
            )

        self.bot.cache.filter[ctx.guild.id] = [
            _data.keyword
            for _data in await self.bot.db.fetch(
                """
                SELECT keyword 
                FROM filter 
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
        ]

        await add_keyword(ctx.guild, keywords)
        return await ctx.embed(
            message=f"Added the word(s): `{', '.join(keywords)}`",
            message_type="approved",
        )

    @filter.command(name="list", aliases=["words"])
    @has_permissions(manage_guild=True)
    async def filter_list(self, ctx: Context) -> None:
        """
        View every filtered word.
        """
        await self.check_setup(ctx.guild)
        records = await self.bot.db.fetch(
            """
            SELECT keyword 
            FROM filter 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )
        if not records:
            return await ctx.embed(
                message="There aren't any filtered words in this server!",
                message_type="warned",
            )

        return await ctx.paginate(
            entries=records, 
            embed=Embed(title="Filtered Words")
        )

    @filter.command(
        name="whitelist",
        aliases=(
            "exempt",
            "ignore",
        ),
    )
    @has_permissions(manage_guild=True)
    async def filter_whitelist(
        self,
        ctx: Context,
        source: Union[Member, TextChannel, Role],
    ) -> None:
        """
        Exempt roles from the word filter.
        """
        event = (ctx.parameters.get("event") or "all").lower()
        if "," in event:
            event = event.split(",")

        valid_events = {
            "invites",
            "links",
            "spam",
            "emojis",
            "massmention",
            "snipe",
            "headers",
            "nicknames",
            "spoilers",
            "caps",
            "keywords",
            "all",
        }

        if isinstance(event, list):
            for e in event:
                e = e.strip()
                if e not in valid_events:
                    return await ctx.embed(
                        message=f"`{event}` is not a valid event!",
                        message_type="warned",
                    )
        else:
            if event not in valid_events:
                return await ctx.embed(
                    message=f"`{event}` is not a valid event!", 
                    message_type="warned"
                )

        await self.check_setup(ctx.guild)
        if isinstance(source, Member):
            if await self.bot.hierarchy(ctx, source, ctx.author) is False:
                return

        if await self.bot.db.fetch(
            """
            SELECT * FROM filter_whitelist 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            ctx.guild.id,
            source.id,
        ):
            await self.bot.db.execute(
                """
                DELETE FROM filter_whitelist 
                WHERE guild_id = $1 
                AND user_id = $2
                """,
                ctx.guild.id,
                source.id,
            )

            await ctx.embed(
                message=f"Successfuly unwhitelisted {source.mention}",
                message_type="approved",
            )
        else:
            if isinstance(event, list):
                for e in event:
                    await self.bot.db.execute(
                        """
                        INSERT INTO filter_whitelist (guild_id, user_id, events)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (guild_id, user_id)
                        DO UPDATE SET events = filter_whitelist.events || ',' || EXCLUDED.events;
                        """,
                        ctx.guild.id,
                        source.id,
                        e,
                    )
                m = ", ".join(m for m in event)
            else:
                await self.bot.db.execute(
                    """
                    INSERT INTO filter_whitelist (guild_id, user_id, events)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id, user_id)
                    DO UPDATE SET events = filter_whitelist.events || ',' || EXCLUDED.events;
                    """,
                    ctx.guild.id,
                    source.id,
                    event,
                )
                m = event

            await ctx.embed(
                message=f"Successfully whitelisted {source.mention} for the event(s) `{m}`",
                message_type="approved",
            )

        self.bot.cache.filter_whitelist[ctx.guild.id] = [
            data.user_id
            for data in await self.bot.db.fetch(
                """
                SELECT * FROM filter_whitelist 
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
        ]
        return

    async def get_member(self, id: int) -> Optional[discord.User]:
        """
        Get the member from the guild.
        """
        if user := self.bot.get_user(id):
            return user

        return await self.bot.fetch_user(id)

    def get_object(
        self, guild: Guild, id: int
    ) -> Optional[Union[Member, Role, TextChannel]]:
        """
        Get the object from the guild.
        """
        if user := guild.get_member(id):
            return user

        elif role := guild.get_role(id):
            return role

        elif channel := guild.get_channel(id):
            return channel

        else:
            return None

    def get_rows(self, guild: Guild, data: List[Dict[str, Any]]) -> List[str]:
        """
        Get the rows for the embed.
        """
        rows = []
        i = 0
        for row in data:
            obj = self.get_object(guild, row["user_id"])
            if obj == None:
                continue
            if isinstance(obj, discord.Member):
                rt = "member"
            elif isinstance(obj, discord.Role):
                rt = "role"
            elif isinstance(obj, discord.TextChannel):
                rt = "channel"
            else:
                pass
            if not rt:
                pass
            else:
                i += 1
                events = row.get("events", "all")
                if "," in events:
                    e = ", ".join(f"**{m}**" for m in events.split(","))
                else:
                    e = f"**{events}**"
                rows.append(f"`{i}` {obj.mention}: `{rt}` - {e}")
        return rows

    @filter.command(name="whitelisted")
    @has_permissions(manage_guild=True)
    async def filter_whitelisted(self, ctx: Context) -> None:
        """
        View whitelisted objects.
        """
        await self.check_setup(ctx.guild)
        records = await self.bot.db.fetch(
            """
            SELECT user_id, events 
            FROM filter_whitelist 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )
        if not records:
            return await ctx.embed(
                message="There are no whitelists setup!", 
                message_type="warned"
            )

        return await ctx.paginate(
            entries=records,
            embed=Embed(
                title="Whitelisted Objects",
                description="\n".join(self.get_rows(ctx.guild, records)),
            ),
        )

    @filter.command(
        name="reset",
        brief="Reset all automod settings",
        example=",filter reset",
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_reset(self, ctx: Context) -> None:
        """
        Reset the filter.
        """
        await self.check_setup(ctx.guild)
        tables = [
            """
            DELETE FROM filter_event 
            WHERE guild_id = $1
            """,
            """
            DELETE FROM filter_setup 
            WHERE guild_id = $1
            """,
            """
            DELETE FROM automod_timeout 
            WHERE guild_id = $1
            """,
            """
            DELETE FROM filter 
            WHERE guild_id = $1
            """,
            """
            DELETE FROM filter_whitelist 
            WHERE guild_id = $1
            """,
        ]
        await gather(*[self.bot.db.execute(table, ctx.guild.id) for table in tables])
        return await ctx.embed(
            message="Filter has been reset", 
            message_type="approved"
        )

    @filter.command(
        name="setup",
        brief="Setup the automod filtering for the guild",
        example=",filter setup",
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_setup(self, ctx: Context) -> None:
        """
        Setup the filter
        """
        setup = False
        
        try:
            await self.check_setup(ctx.guild)
            setup = True
        
        except Exception:
            pass
        
        if setup is True:
            return await ctx.embed(
                message="Filter has already been setup!", 
                message_type="warned"
            )
        
        if self.bot.check_bot_hierarchy(ctx.guild) is False:
            return await ctx.embed(
                message="My top role has to be in the top 5 roles!", 
                message_type="warned"
            )
        
        await self.bot.db.execute(
            """
            INSERT INTO filter_setup (guild_id) 
            VALUES ($1)
            """, 
            ctx.guild.id
        )
        
        await self.bot.db.execute(
            """
            INSERT INTO automod_timeout (guild_id, timeframe) 
            VALUES($1, $2) 
            ON CONFLICT(guild_id) 
            DO UPDATE SET timeframe = excluded.timeframe
            """,
            ctx.guild.id,
            "20s",
        )
        return await ctx.embed("Filter has been **setup**", "approved")

    @filter.command(
        name="nicknames",
        aliases=(
            "nick",
            "nicks",
        ),
    )
    @has_permissions(manage_guild=True)
    async def filter_nicknames(self, ctx: Context, state: bool) -> None:
        """
        Automatically reset nicknames if a filtered word is detected.
        """
        await self.check_setup(ctx.guild)
        if state == await self.bot.db.fetchval(
            """
            SELECT is_enabled 
            FROM filter_event 
            WHERE guild_id = $1 
            AND event = $2
            """,
            ctx.guild.id,
            "nicknames",
        ):
            return await ctx.embed(
                message="That is already the current state!", 
                message_type="warned"
            )

        await self.bot.db.execute(
            """
            INSERT INTO filter_event (guild_id, event, is_enabled) 
            VALUES ($1, $2, $3) ON CONFLICT (guild_id, event) 
            DO UPDATE SET is_enabled = EXCLUDED.is_enabled
            """,
            ctx.guild.id,
            "nicknames",
            state,
        )

        await self.bot.cache.setup_filter()
        return await ctx.embed(
            message=f"{'Enabled' if state else 'Disabled'} the **nickname filter",
            message_type="approved",
        )

    async def get_int(self, string: str) -> str:
        """
        Extract integers from a string.
        """
        return "".join(s for s in string if s.isdigit())

    def get_state(self, state: bool) -> str:
        """
        Get the emoji state for a boolean value.
        """
        return "✅" if state else "❌"

    @filter.command(
        name="snipe",
        aliases=("snipes", "s"),
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_snipe(self, ctx: Context, state: bool):
        """
        Automatically delete messages that contain filtered words.
        """
        settings = await self.get_filter_settings(ctx.guild.id)
        if "snipe" in settings and settings["snipe"]["is_enabled"] == state:
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        await self.bot.db.execute(
            """
            INSERT INTO filter_event (guild_id, event, is_enabled) 
            VALUES ($1, $2, $3) 
            ON CONFLICT (guild_id, event) 
            DO UPDATE SET is_enabled = EXCLUDED.is_enabled
            """,
            ctx.guild.id,
            "snipe",
            state,
        )
        await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            message=f"{'Enabled' if state else 'Disabled'} the snipe filter",
            message_type="approved",
        )

    @filter.command(name="settings")
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_settings(self, ctx: Context):
        """
        View the current filter settings.
        """
        rows = []
        event_types = [
            "invites",
            "links",
            "spam",
            "emojis",
            "massmention",
            "snipe",
            "headers",
            "nicknames",
            "spoilers",
            "caps",
        ]
        e = []

        async def get_timeout():
            keywords = await self.bot.db.fetch(
                """
                SELECT keyword FROM filter 
                WHERE guild_id = $1
                """, 
                ctx.guild.id
            )
            words = [keyword["keyword"] for keyword in keywords]
            if len(words) > 0:
                word_list = ", ".join(words)
            else:
                word_list = "No filtered words"
            timeout = await self.get_filter_timeout(ctx.guild.id)
            rows.insert(
                0, f"**Timeout:** `{timeout}`\n**Filtered Words:** ```{word_list}```"
            )

        async def get_events():
            settings = await self.get_filter_settings(ctx.guild.id)
            for event_type in event_types:
                if event_type in settings:
                    is_enabled = settings[event_type]["is_enabled"]
                    threshold = settings[event_type]["threshold"]
                    e.append(event_type.lower())
                    if event_type not in ["invites", "links", "snipe"]:
                        limit = f"- limit: `{threshold}`" if is_enabled else ""
                        rows.append(
                            f"**Filter [{event_type}]({self.bot.domain}/commands):** {self.get_state(is_enabled)} {limit}"
                        )
                    else:
                        rows.append(
                            f"**Filter [{event_type}]({self.bot.domain}/commands):** {self.get_state(is_enabled)}"
                        )
                else:
                    rows.append(
                        f"**Filter [{event_type}]({self.bot.domain}/commands):** {self.get_state(False)}"
                    )

        await gather(*[get_timeout(), get_events()])
        for event_type in event_types:
            if event_type.lower() not in e:
                rows.append(
                    f"**Filter [{event_type.lower()}]({self.bot.domain}/commands):** {self.get_state(False)}"
                )

        embed = Embed(
            title="Automod settings",
            color=Colors().information,
            description="\n".join(rows),
        )
        await ctx.send(embed=embed)

    @filter.command(
        name="headers",
        aliases=["head"],
        brief="enable or disable the header filter",
        example="filter headers true --threshold 5",
        parameters={
            "threshold": {
                "converter": int,
                "description": "The limit for spoilers in one message",
                "aliases": ["limit"],
            }
        },
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def headers(self, ctx: Context, state: bool):
        await self.check_setup(ctx.guild)
        threshold = (
            ctx.parameters.get("threshold")
            or await self.bot.db.fetchval(
                "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                ctx.guild.id,
                "headers",
            )
            or 5
        )

        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "headers",
        ) and threshold == await self.bot.db.fetchval(
            "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "headers",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        if state:
            if (
                threshold
                == await self.bot.db.fetchval(
                    "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                    ctx.guild.id,
                    "headers",
                )
                and ctx.parameters.get("threshold") is not None
            ):
                return await ctx.embed(
                    "That is **already** the **current threshold**", "warned"
                )

            if threshold > 127 or threshold < 1:
                return await ctx.embed(
                    "Provide a **valid** threshold between **1** and **127**", "warned"
                )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled, threshold) VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled, threshold = EXCLUDED.threshold;",
            ctx.guild.id,
            "headers",
            state,
            threshold,
        )
        await self.update_filter_settings(ctx.guild.id)
        if state is True:
            h = f"(with a threshold of `{threshold}`)"
        else:
            h = ""
        return await ctx.embed(
            f"**Filter headers** set to **{'enabled' if state is True else 'disabled'}** {h}",
            "approved",
        )

    @filter.command(name="migrate", brief="migrate filtered words to automod")
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def migrate(self, ctx: Context):
        await self.check_setup(ctx.guild)
        keywords = await self.bot.db.fetch(
            "SELECT keyword FROM filter WHERE guild_id = $1", ctx.guild.id
        )
        if not keywords:
            return await ctx.embed("No filtered words found to migrate.", "warned")
        from tool.migrate import add_keyword  # type: ignore

        words = [keyword["keyword"] for keyword in keywords]
        await add_keyword(ctx.guild, words, True)
        return await ctx.embed("Migrated words to automod", "approved")

    @filter.command(
        name="images",
        aliases=["img"],
        brief="enable or disable the image filter",
        example="filter images true --threshold 5",
        parameters={
            "threshold": {
                "converter": int,
                "description": "The limit for spoilers in one message",
                "aliases": ["limit"],
            }
        },
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def images(self, ctx: Context, state: bool):
        await self.check_setup(ctx.guild)
        threshold = (
            ctx.parameters.get("threshold")
            or await self.bot.db.fetchval(
                "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                ctx.guild.id,
                "images",
            )
            or 5
        )

        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "images",
        ) and threshold == await self.bot.db.fetchval(
            "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "images",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        if state:
            if (
                threshold
                == await self.bot.db.fetchval(
                    "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                    ctx.guild.id,
                    "images",
                )
                and ctx.parameters.get("threshold") is not None
            ):
                return await ctx.embed(
                    "That is **already** the **current threshold**", "warned"
                )

            if threshold > 127 or threshold < 1:
                return await ctx.embed(
                    "Provide a **valid** threshold between **1** and **127**", "warned"
                )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled, threshold) VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled, threshold = EXCLUDED.threshold;",
            ctx.guild.id,
            "images",
            state,
            threshold,
        )
        if state is True:
            h = f"(with a threshold of `{threshold}`)"
        else:
            h = ""
        await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            f"**Filter images** set to **{'enabled' if state is True else 'disabled'}** {h}",
            "approved",
        )

    @filter.command(
        name="timeout",
        aliases=["to", "time"],
        brief="Set the amount of time someone will be muted when they break an automod rule",
        example=",filter timeout 60s",
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_timeout(self, ctx: Context, *, time: str):
        await self.check_setup(ctx.guild)
        if "minute" in time.lower():
            time = f"{await self.get_int(time)} minutes"
        elif "m" in time.lower():
            time = f"{await self.get_int(time)} minutes"
        elif "second" in time.lower():
            time = f"{await self.get_int(time)} seconds"
        elif "s" in time.lower():
            time = f"{await self.get_int(time)} seconds"
        elif "hour" in time.lower():
            time = f"{await self.get_int(time)} hours"
        elif "h" in time.lower():
            time = f"{await self.get_int(time)} hours"
        else:
            time = f"{await self.get_int(time)} seconds"

        try:
            converted = humanfriendly.parse_timespan(time)
            if converted < 20:
                return await ctx.embed(
                    "**Punishment timeout** must be **20 seconds** or above", "warned"
                )
        except Exception:
            return await ctx.embed(
                f"Could not convert `{time}` into a timeframe", "warned"
            )
        await self.bot.db.execute(
            """INSERT INTO automod_timeout (guild_id,timeframe) VALUES($1,$2) ON CONFLICT(guild_id) DO UPDATE SET timeframe = excluded.timeframe""",
            ctx.guild.id,
            time,
        )
        await self.update_filter_timeout(ctx.guild.id)
        return await ctx.embed(
            f"**Punishment timeout** is now `{time}`",
            "approved",
        )

    @filter.command(
        name="spoilers",
        aliases=("spoiler",),
        example=",filter spoilers enable",
        brief="Manage spoiler images being sent in the server",
        parameters={
            "threshold": {
                "converter": int,
                "description": "The limit for spoilers in one message",
                "aliases": ["limit"],
            }
        },
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_spoilers(self, ctx: Context, state: bool):
        await self.check_setup(ctx.guild)
        threshold = (
            ctx.parameters.get("threshold")
            or await self.bot.db.fetchval(
                "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                ctx.guild.id,
                "spoilers",
            )
            or 5
        )

        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "spoilers",
        ) and threshold == await self.bot.db.fetchval(
            "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "spoilers",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        if state:
            if (
                threshold
                == await self.bot.db.fetchval(
                    "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                    ctx.guild.id,
                    "spoilers",
                )
                and ctx.parameters.get("threshold") is not None
            ):
                return await ctx.embed(
                    "That is **already** the **current threshold**", "warned"
                )

            if threshold > 127 or threshold < 1:
                return await ctx.embed(
                    "Provide a **valid** threshold between **1** and **127**", "warned"
                )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled, threshold) VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled, threshold = EXCLUDED.threshold;",
            ctx.guild.id,
            "spoilers",
            state,
            threshold,
        )

        await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            f"**{'Enabled' if state else 'Disabled'}** the **spoiler filter** {f'(with threshold: `{threshold}`)' if state else ''}",
            "approved",
        )

    @filter.command(
        name="links",
        aliases=("urls",),
        brief="Prevent all links from being sent in the server",
        example=",filter links all true --punishment delete",
        parameters={
            "punishment": {
                "converter": str,
                "description": "The punishment for breaking the rule",
                "aliases": ["p"],
                "choices": ["delete", "timeout"],
            }
        },
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_links(
        self, 
        ctx: Context, 
        filter_type: Literal["invites", "external", "all"],
        state: bool,
        punishment: str = "delete"
    ) -> None:
        """
        Configure Discord's AutoMod for link filtering.
        
        Types:
        - invites - Only Discord invite links
        - external - Only non-Discord links
        - all - All types of links
        """
        patterns = {
            "invites": [
                r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|com/invite))/[a-zA-Z0-9-]+"
            ],
            "external": [
                r"(?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?",
                r"(?:https?://)?(?:\d{1,3}\.){3}\d{1,3}(?:/[^\s]*)?"
            ],
            "all": [
                r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|com/invite))/[a-zA-Z0-9-]+",
                r"(?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?",
                r"(?:https?://)?(?:\d{1,3}\.){3}\d{1,3}(?:/[^\s]*)?"
            ]
        }

        try:
            if not state:
                rules = await ctx.guild.fetch_automod_rules()
                for rule in rules:
                    if rule.name == f"Greed - {filter_type.title()} Filter":
                        await rule.delete()
                return await ctx.embed(
                    f"Removed {filter_type} filter",
                    "approved"
                )

            actions = [AutoModRuleAction(type=AutoModRuleActionType.block_message)]
            
            if punishment == "timeout":
                actions.append(
                    AutoModRuleAction(
                        type=AutoModRuleActionType.timeout,
                        duration=timedelta(hours=1)
                    )
                )

            trigger = AutoModTrigger(
                type=AutoModRuleTriggerType.keyword,
                regex_patterns=patterns[filter_type]
            )

            exempt_roles = [role for role in ctx.guild.roles if role.permissions.manage_guild]

            rule = await ctx.guild.create_automod_rule(
                name=f"Greed - {filter_type.title()} Filter",
                event_type=AutoModRuleEventType.message_send,
                trigger=trigger,
                actions=actions,
                enabled=True,
                exempt_roles=exempt_roles,
                reason="Created via Greed filter command"
            )
            return await ctx.embed(
                f"Created {filter_type} filter with **{punishment}** punishment",
                "approved"
            )

        except discord.Forbidden:
            return await ctx.embed(
                "I need `manage_guild` permissions to manage AutoMod rules",
                "warned"
            )
        except discord.HTTPException as e:
            return await ctx.embed(
                f"Failed to manage AutoMod rule: {e}",
                "warned"
            )

    @filter.command(
        name="spam",
        brief="Prevent users from laddering/spamming in the server",
        example=",filter spam true --threshold 10",
        parameters={
            "threshold": {
                "converter": int,
                "description": "The limit of messages for one user in 5 seconds",
                "aliases": ["limit"],
            }
        },
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_spam(self, ctx: Context, state: bool):
        await self.check_setup(ctx.guild)
        threshold = (
            ctx.parameters.get("threshold")
            or await self.bot.db.fetchval(
                "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                ctx.guild.id,
                "spam",
            )
            or 5
        )

        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "spam",
        ) and threshold == await self.bot.db.fetchval(
            "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "spam",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        if state:
            if (
                threshold
                == await self.bot.db.fetchval(
                    "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                    ctx.guild.id,
                    "spam",
                )
                and ctx.parameters.get("threshold") is not None
            ):
                return await ctx.embed(
                    "That is **already** the **current threshold**", "warned"
                )

            if threshold > 127 or threshold < 1:
                return await ctx.embed(
                    "Provide a **valid** threshold between **1** and **127**", "warned"
                )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled, threshold) VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled, threshold = EXCLUDED.threshold;",
            ctx.guild.id,
            "spam",
            state,
            threshold,
        )
        if ctx.guild.id in self.bot.cache.filter_event:
            self.bot.cache.filter_event[ctx.guild.id]["spam"] = {
                "is_enabled": state,
                "threshold": threshold,
            }
        else:
            await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            f"**{'Enabled' if state else 'Disabled'}** the **spam filter** {f'(with threshold: `{threshold}`)' if state else ''}",
            "approved",
        )

    @filter.command(
        name="emojis",
        brief="Limit the amount of emojis that can be sent in one message",
        aliases=("emoji",),
        example=",filter emojis true --threshold 3",
        parameters={
            "threshold": {
                "converter": int,
                "description": "The limit for emojis in one message",
                "aliases": ["limit"],
            }
        },
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_emojis(self, ctx: Context, state: bool):
        await self.check_setup(ctx.guild)
        threshold = (
            ctx.parameters.get("threshold")
            or await self.bot.db.fetchval(
                "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                ctx.guild.id,
                "emojis",
            )
            or 5
        )

        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "emojis",
        ) and threshold == await self.bot.db.fetchval(
            "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "emojis",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        if state:
            if (
                threshold
                == await self.bot.db.fetchval(
                    "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                    ctx.guild.id,
                    "emojis",
                )
                and ctx.parameters.get("threshold") is not None
            ):
                return await ctx.embed(
                    "That is **already** the **current threshold**", "warned"
                )

            if threshold > 127 or threshold < 1:
                return await ctx.embed(
                    "Provide a **valid** threshold between **1** and **127**", "warned"
                )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled, threshold) VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled, threshold = EXCLUDED.threshold;",
            ctx.guild.id,
            "emojis",
            state,
            threshold,
        )

        await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            f"**{'Enabled' if state else 'Disabled'}** the **emoji filter** {f'(with threshold: `{threshold}`)' if state else ''}",
            "approved",
        )

    @filter.command(
        name="invites",
        aliases=("invs",),
        brief="Stop outside server invites from being sent in the guild",
        example=",filter invites true",
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_invites(self, ctx: Context, state: bool):
        await self.check_setup(ctx.guild)
        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "invites",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled) VALUES ($1, $2, $3) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled;",
            ctx.guild.id,
            "invites",
            state,
        )
        await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            f"**{'Enabled' if state else 'Disabled'}** the **invite filter**",
            "approved",
        )

    @filter.command(
        name="caps",
        aliases=("capslock",),
        brief="Limit how many capital letters can be sent in a single message",
        example=",filter caps true --threshold 6",
        parameters={
            "threshold": {
                "converter": int,
                "description": "The limit for caps in one message",
                "aliases": ["limit"],
            }
        },
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_caps(self, ctx: Context, state: bool):
        """
        Delete any messages exceeding the threshold for caps
        """
        threshold = (
            ctx.parameters.get("threshold")
            or await self.bot.db.fetchval(
                "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                ctx.guild.id,
                "caps",
            )
            or 5
        )
        await self.check_setup(ctx.guild)
        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "caps",
        ) and threshold == await self.bot.db.fetchval(
            "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "caps",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        if state:
            if (
                threshold
                == await self.bot.db.fetchval(
                    "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                    ctx.guild.id,
                    "invites",
                )
                and ctx.parameters.get("threshold") is not None
            ):
                return await ctx.embed(
                    "That is **already** the **current threshold**", "warned"
                )

            if threshold > 127 or threshold < 1:
                return await ctx.embed(
                    "Provide a **valid** threshold between **1** and **127**", "warned"
                )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled, threshold) VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled, threshold = EXCLUDED.threshold;",
            ctx.guild.id,
            "caps",
            state,
            threshold,
        )

        await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            f"**{'Enabled' if state else 'Disabled'}** the **caps filter** {f'(with threshold: `{threshold}`)' if state else ''}",
            "approved",
        )

    @filter.command(
        name="massmention",
        brief="Prevent users from mentioning more than a set amount of members at once",
        example=",filter massmention true --threshold 4",
        aliases=("mentions",),
        parameters={
            "threshold": {
                "converter": int,
                "description": "The limit for mentions in one message",
                "aliases": ["limit"],
            }
        },
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_massmention(self, ctx: Context, state: bool):
        """
        Delete any messages exceeding the threshold for mentions
        """
        await self.check_setup(ctx.guild)
        threshold = (
            ctx.parameters.get("threshold")
            or await self.bot.db.fetchval(
                "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                ctx.guild.id,
                "massmention",
            )
            or 5
        )

        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "massmention",
        ) and threshold == await self.bot.db.fetchval(
            "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "massmention",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        if state:
            if (
                threshold
                == await self.bot.db.fetchval(
                    "SELECT threshold FROM filter_event WHERE guild_id = $1 AND event = $2",
                    ctx.guild.id,
                    "invites",
                )
                and ctx.parameters.get("threshold") is not None
            ):
                return await ctx.embed(
                    "That is **already** the **current threshold**", "warned"
                )

            if threshold > 127 or threshold < 1:
                return await ctx.embed(
                    "Provide a **valid** threshold between **1** and **127**", "warned"
                )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled, threshold) VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled, threshold = EXCLUDED.threshold;",
            ctx.guild.id,
            "massmention",
            state,
            threshold,
        )

        await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            f"**{'Enabled' if state else 'Disabled'}** the **mention filter** {f'(with threshold: `{threshold}`)' if state else ''}",
            "approved",
        )

    @filter.command(
        name="remove",
        aliases=("delete",),
        brief="Remove a filtered word from the filter list",
        example=",filter remove stupid",
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_remove(self, ctx: Context, *, keyword: str):
        from tool.migrate import remove_keyword  # type: ignore

        await self.check_setup(ctx.guild)
        if not await self.bot.db.fetch(
            "SELECT * FROM filter WHERE guild_id = $1 AND keyword = $2",
            ctx.guild.id,
            keyword,
        ):
            return await ctx.embed("That isn't a **filtered word**.", "warned")

        await self.bot.db.execute(
            "DELETE FROM filter WHERE guild_id = $1 AND keyword = $2;",
            ctx.guild.id,
            keyword,
        )
        await remove_keyword(ctx.guild, keyword)
        self.bot.cache.filter[ctx.guild.id].remove(keyword)
        return await ctx.embed(
            f"**Removed** the `{keyword}` from the **filtered list**",
            "approved",
        )

    @filter.command(
        name="punishment",
        aliases=["punish"],
        brief="Set the punishment for breaking automod rules",
        example=",filter punishment delete",
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_punishment(self, ctx: Context, *, punishment: str):
        await self.check_setup(ctx.guild)
        if punishment.lower() not in ["delete", "timeout", "kick", "ban", "jail"]:
            return await ctx.embed(f"That is not a **valid punishment**", "warned")

        await self.bot.db.execute(
            "INSERT INTO filter_setup (guild_id, punishment) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET punishment = EXCLUDED.punishment;",
            ctx.guild.id,
            punishment.lower(),
        )
        return await ctx.embed(
            f"**Punishment** for breaking automod rules is now `{punishment.lower()}`",
            "approved",
        )

    @filter.command(
        name="punishments",
        brief="View the current punishment for breaking automod rules",
        example=",filter punishments",
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_punishments(self, ctx: Context):
        await self.check_setup(ctx.guild)
        punishment = await self.bot.db.fetchval(
            "SELECT punishment FROM filter_setup WHERE guild_id = $1", ctx.guild.id
        )
        if not punishment:
            p = [
                "delete",
                "timeout",
                "kick",
                "ban",
            ]
            embed = discord.Embed(
                title="Punishments",
                description="\n".join(f"**{i}**" for i in p),
                color=Colors().information,
            )
            return await ctx.send(embed=embed)
        return await ctx.embed(
            f"**Punishment** for breaking automod rules is `{punishment}`",
            "approved",
        )

    @filter.command(
        name="keywords",
        aliases=("keyword",),
        brief="Enable or disable the keyword filtering in chat",
        example=",filter keywords true",
    )
    @bot_has_permissions(administrator=True)
    @has_permissions(manage_guild=True)
    async def filter_keywords(self, ctx: Context, state: bool):
        await self.check_setup(ctx.guild)
        if state == await self.bot.db.fetchval(
            "SELECT is_enabled FROM filter_event WHERE guild_id = $1 AND event = $2",
            ctx.guild.id,
            "keywords",
        ):
            return await ctx.embed(
                "That is **already** the **current state**", "warned"
            )

        await self.bot.db.execute(
            "INSERT INTO filter_event (guild_id, event, is_enabled) VALUES ($1, $2, $3) ON CONFLICT (guild_id, event) DO UPDATE SET is_enabled = EXCLUDED.is_enabled;",
            ctx.guild.id,
            "keywords",
            state,
        )
        await self.update_filter_settings(ctx.guild.id)
        return await ctx.embed(
            f"**{'Enabled' if state else 'Disabled'}** the **keyword filter**",
            "approved",
        )


async def setup(bot: Greed):
    await bot.add_cog(Automod(bot))
