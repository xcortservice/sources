import random
import traceback
from asyncio import Future, Lock, as_completed, create_task
from collections import defaultdict as collection
from datetime import datetime
from typing import (Any, Callable, Coroutine, Dict, List, Optional, Type,
                    TypeVar, Union)

import numpy as np
import orjson
from cashews import cache
from data.config import CONFIG
from discord import Client, Embed, Guild, Member, Message, VoiceChannel
from discord.ext import tasks
from discord.ext.commands import Context
from loguru import logger
from pydantic import BaseModel
from scipy.optimize import fsolve
from typing_extensions import Self
from xxhash import xxh64_hexdigest as hash_

level_data = {1: 0, 2: 15, 3: 80, 4: 255, 5: 624, 6: 1295, 7: 2400, 8: 4095}

# Extract levels and xp values
levels = np.array(list(level_data.keys()))
xp_values = np.array(list(level_data.values()))

# Fit a polynomial of degree 7
coefficients = np.polyfit(levels, xp_values, deg=len(levels) - 1)

# Create a polynomial function from the coefficients
polynomial = np.poly1d(coefficients)
DEFAULT_MULTIPLIER = 0.05
DEFAULT_LEVEL_MESSAGE = (
    "{embed}{content: {user.mention} you have leveled up to {level}}"
)
cache.setup("mem://")
T = TypeVar("T")
Coro = Coroutine[Any, Any, T]
CoroT = TypeVar("CoroT", bound=Callable[..., Coro[Any]])


def get_timestamp():
    return datetime.now().timestamp()


def get_bar(bot: Client, percentage: int) -> str:
    bar = [
        bot.config["emojis"]["levels"]["white_left_rounded"],
        bot.config["emojis"]["levels"]["white"],
        bot.config["emojis"]["levels"]["white"],
        bot.config["emojis"]["levels"]["white"],
        bot.config["emojis"]["levels"]["white"],
        bot.config["emojis"]["levels"]["white"],
        bot.config["emojis"]["levels"]["white"],
        bot.config["emojis"]["levels"]["white"],
        bot.config["emojis"]["levels"]["white"],
        bot.config["emojis"]["levels"]["white_right_rounded"],
    ]
    if percentage < 1:
        return "".join(b for b in bar)
    bright = bot.config["emojis"]["levels"]["blue_right_rounded"]
    bleft = bot.config["emojis"]["levels"]["blue_left_rounded"]
    blue = bot.config["emojis"]["levels"]["blue"]
    if percentage > 2:
        bar[0] = bleft
    string = str(percentage)
    total = string[0]
    total = int(total)
    if percentage > 10:
        if percentage != 100:
            for i in range(total):
                if i == 9:
                    bar[i] = bright
                elif i == 0:
                    bar[i] = bleft
                else:
                    bar[i] = blue
        else:
            bar[0] = bleft
            for i in range(total):
                if i == 0:
                    bar[i] = bleft
                elif i == 9:
                    bar[i] = bright
                else:
                    bar[i] = blue
    return "".join(b for b in bar)


class LevelSettings(BaseModel):
    multiplier: Optional[float] = DEFAULT_MULTIPLIER
    award_message: Optional[str] = None
    award_message_mode: Optional[str] = "DM"
    roles: Optional[List[List[int]]] = None
    roles_stack: Optional[bool] = True
    channel_id: Optional[int] = None
    ignored: Optional[List[int]] = None
    locked: Optional[bool] = False

    @classmethod
    async def from_query(cls: Type["LevelSettings"], bot: Client, guild_id: int):
        data = await bot.db.fetchrow(
            """SELECT multiplier, award_message, award_message_mode, roles, ignored, locked, roles_stack, channel_id FROM text_level_settings WHERE guild_id = $1""",
            guild_id,
            cached=False,
        )
        if not data:
            return cls()
        if not data.multiplier or data.multiplier == None:
            data.multiplier = DEFAULT_MULTIPLIER
        if data.roles:
            data.roles = orjson.loads(data.roles)
        else:
            data.roles = None
        if data.ignored:
            data.ignored = orjson.loads(data.ignored)
        else:
            data.ignored = None
        if not data.award_message:
            data.award_message = DEFAULT_LEVEL_MESSAGE
        if data:
            return cls(
                multiplier=data.multiplier,
                roles=data.roles,
                ignored=data.ignored,
                award_message=data.award_message,
                channel_id=data.channel_id,
                locked=data.locked,
                roles_stack=data.roles_stack,
                award_message_mode=data.award_message_mode,
            )
        else:
            return cls()

    def get_channel(self, ctx: Union[Context, Guild], string: Optional[bool] = False):
        if not self.channel_id:
            if string:
                return "N/A"
            else:
                return None
        if isinstance(ctx, Context):
            channel = ctx.guild.get_channel(self.channel_id)
        else:
            channel = ctx.get_channel(self.channel_id)
        if channel:
            if string:
                return channel.mention
            else:
                return channel
        if string:
            return "N/A"
        else:
            return None


class Level:
    def __init__(
        self, base_multiplier: float = DEFAULT_MULTIPLIER, bot: Optional[Client] = None
    ):
        self.multiplier = base_multiplier
        self.bot = bot
        self._events = ["on_text_level_up"]
        self.listeners: Dict[str, Future] = {}
        self.logger = logger
        self.startup_finished = False
        self.locks = collection(Lock)
        self.cache = {}
        self.messages = []
        self.text_cache = {}
        self.text_level_loop.start()

    async def setup(self, bot: Client) -> Self:
        self.bot = bot
        self.logger.info("Starting levelling loop")
        self.bot.loop.create_task(self.do_text_levels())
        self.bot.add_listener(self.do_message_event, "on_message")
        self.logger.info("Levelling loop started")
        return self

    @tasks.loop(minutes=2)
    async def text_level_loop(self):
        try:
            await self.do_text_levels()
        except Exception as error:
            exc = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            logger.info(f"text_level_loop raised {exc}")

    def xp_for_level(self, level: int):
        return int(polynomial(level))

    def get_xp(self, level: int, settings: LevelSettings) -> int:
        """
        :param level : Level(int)
        :return      : Amount of xp(int) needed to reach the level
        """
        return int(polynomial(level))
        # return math.ceil(math.pow((level - 1) / (settings.multiplier * (1 + math.sqrt(5))), 2))

    def get_level(self, xp: int, settings: LevelSettings) -> int:
        """
        :param xp : XP(int)
        :return   : Level(int)
        """

        def equation(level):
            return polynomial(level) - xp

        # Check if xp is within the range of known XP values
        if xp <= xp_values[-1]:
            # Use interpolation to find the level within known data points
            return int(np.interp(xp, xp_values, levels))
        else:
            # For XP beyond the known values, estimate level by finding the root
            estimated_level = fsolve(
                equation, x0=len(levels)
            )  # Initial guess is the last known level
            return int(np.round(estimated_level[0]))
        # return math.floor(settings.multiplier * (1 + math.sqrt(5)) * math.sqrt(xp)) + 1

    def xp_to_next_level(
        self,
        current_level: Optional[int] = None,
        current_xp: Optional[int] = None,
        settings: Optional[LevelSettings] = None,
    ) -> int:
        if current_xp is not None:
            current_level = self.get_level(current_xp, settings)
        return self.get_xp(current_level + 1, settings) - self.get_xp(
            current_level, settings
        )

    def add_xp(
        self,
        message: Optional[Message] = None,
        settings: Optional[LevelSettings] = None,
    ) -> int:
        if message:
            # words = message.content.split(" ")
            # eligble = len([w for w in words if len(w) > 1])
            # xp = eligble + (10 * len(message.attachments))
            # if xp == 0:
            #     xp = 1
            xp = random.randint(20, 30)
            return min(xp * settings.multiplier, 50)
        else:
            return random.randint(1, 50) / self.multiplier

    def difference(self, ts: float) -> int:
        now = int(get_timestamp())
        return now - int(ts)

    def get_key(
        self, guild: Guild, member: Member, channel: Optional[VoiceChannel] = None
    ):
        if channel:
            return hash_(f"{guild.id}-{channel.id}-{member.id}")
        return hash_(f"{guild.id}-{member.id}")

    @cache(2, "settings:{guild.id}")
    async def get_settings(self, guild: Guild) -> LevelSettings:
        return await LevelSettings.from_query(self.bot, guild.id)

    async def check_level_up(self, message: Message) -> bool:
        settings = await self.get_settings(message.guild)
        data = await self.bot.db.fetchrow(
            """SELECT xp, last_level_up FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
            message.guild.id,
            message.author.id,
        )
        if not data:
            last_level_up = 0
            xp = 0
        else:
            last_level_up = data.last_level_up or 0
            xp = data.xp or 0
        try:
            before_xp = xp or 0
            key = f"{message.guild.id}-{message.author.id}"
            added_xp = sum(
                [self.add_xp(m, settings) for m in self.text_cache[key]["messages"]]
            )
            if not before_xp:
                before_xp = 0
            after_xp = (before_xp or 0) + (added_xp or 0)
            new_level = self.get_level(int(after_xp), settings)
            if (
                self.text_cache[key].get("messaged", 0) != new_level
                and last_level_up != new_level
            ):
                if self.get_level(int(before_xp), settings) != self.get_level(
                    int(after_xp), settings
                ):
                    self.bot.dispatch(
                        "text_level_up",
                        message.guild,
                        message.author,
                        self.get_level(int(after_xp), settings),
                    )
                    await self.bot.db.execute(
                        """INSERT INTO text_levels (guild_id, user_id, xp, msgs, last_level_up) VALUES($1, $2, $3, $4, $5) ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = text_levels.xp + excluded.xp, msgs = text_levels.msgs + excluded.msgs, last_level_up = excluded.last_level_up RETURNING xp""",
                        message.guild.id,
                        message.author.id,
                        added_xp,
                        self.text_cache[key]["amount"],
                        new_level,
                    )
                    self.text_cache.pop(key)
                    return True
        except Exception as e:
            exc = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.info(f"check_level_up raised {exc}")
            pass
        return False

    async def validate_text(self, message: Message, execute: bool = False) -> bool:
        if message in self.messages:
            return False
        settings = await self.get_settings(message.guild)
        async with self.locks["text_levels"]:
            if message not in self.messages:
                self.messages.append(message)
            key = f"{message.guild.id}-{message.author.id}"
            if key in self.text_cache:
                if execute is True:
                    if message not in self.text_cache[key]["messages"]:
                        self.text_cache[key]["messages"].append(message)
                        amount = self.text_cache[key]["amount"] + 1
                    else:
                        amount = self.text_cache[key]["amount"]
                    added_xp = sum(
                        [
                            self.add_xp(m, settings)
                            for m in self.text_cache[key]["messages"]
                        ]
                    )
                    self.text_cache[key]["messages"].clear()
                    if not await self.check_level_up(message):
                        await self.bot.db.execute(
                            """INSERT INTO text_levels (guild_id, user_id, xp, msgs) VALUES($1, $2, $3, $4) ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = text_levels.xp + excluded.xp, msgs = text_levels.msgs + excluded.msgs RETURNING xp""",
                            message.guild.id,
                            message.author.id,
                            added_xp,
                            amount,
                        )
                        self.text_cache.pop(key)
                    return True
                else:
                    self.text_cache[key]["amount"] += 1
                    self.text_cache[key]["messages"].append(message)
                    await self.check_level_up(message)
                    return True
            else:
                self.text_cache[key] = {"amount": 1, "messages": [message]}
                if execute is True:
                    added_xp = sum(
                        [
                            self.add_xp(m, settings)
                            for m in self.text_cache[key]["messages"]
                        ]
                    )
                    amount = self.text_cache[key]["amount"]
                    if not await self.check_level_up(message):
                        await self.bot.db.execute(
                            """INSERT INTO text_levels (guild_id,user_id,xp,msgs) VALUES($1,$2,$3,$4) ON CONFLICT(guild_id,user_id) DO UPDATE SET xp = text_levels.xp + excluded.xp, msgs = text_levels.msgs + excluded.msgs RETURNING xp""",
                            message.guild.id,
                            message.author.id,
                            added_xp,
                            amount,
                        )
                        self.text_cache.pop(key)
                    return True
                else:
                    return True

    async def check_guild(self, guild: Guild) -> bool:
        if not (
            data := await self.bot.db.fetchrow(
                """SELECT * FROM text_level_settings WHERE guild_id = $1""", guild.id
            )
        ):
            return False
        if data.locked:
            return False
        return True

    async def get_statistics(
        self, member: Member, level: Optional[int] = None
    ) -> Optional[list]:
        vals = [0, 0]
        settings = await self.get_settings(member.guild)
        if data := await self.bot.db.fetchrow(
            """SELECT xp, msgs FROM text_levels WHERE guild_id = $1 AND user_id = $2""",
            member.guild.id,
            member.id,
            cached=False,
        ):
            vals[0] += int(data.xp)
            vals[1] += int(data.msgs)
        key = f"{member.guild.id}-{member.id}"
        if key in self.text_cache:
            added_xp = sum(
                [self.add_xp(m, settings) for m in self.text_cache[key]["messages"]]
            )
            vals[0] += added_xp
            vals[1] += len(self.text_cache[key]["messages"])
        if level:
            if self.get_level(vals[0]) >= level:
                vals[0] = int(vals[0])
                return vals
            else:
                return False
        return vals

    async def do_message_event(self, message: Message):
        if self.bot is None:
            return
        if message.author.bot:
            return
        if not message.guild:
            return
        if not await self.check_guild(message.guild):
            return
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return
        await self.validate_text(message)

    async def do_text_levels(self):
        if self.bot is None:
            return

        tasks = [
            create_task(self.validate_text(m, execute=True)) for m in self.messages
        ]
        if tasks:
            for t in as_completed(tasks):
                await t

    async def get_rank(
        self, guild: Guild, member: Member, as_tuple: Optional[bool] = False
    ) -> dict:
        data = [
            d.user_id
            for d in await self.bot.db.fetch(
                """SELECT user_id FROM text_levels WHERE guild_id = $1 ORDER BY xp ASC""",
                guild.id,
            )
        ]
        d = {m.id: await self.get_statistics(m) for m in guild.members}
        d = dict(sorted(d.items(), key=lambda x: x[1][0], reverse=True))
        if as_tuple:
            try:
                keys = list(d.keys())
                return keys.index(member.id) + 1, len(keys)
            except Exception:
                return "N/A", len(keys)
        else:
            return d

    async def get_member_xp(self, ctx: Context, member: Member) -> Embed:
        if data := await self.get_statistics(member):
            xp, amount = data
        else:
            return await ctx.fail("no data found yet")
        settings = await self.get_settings(member.guild)
        needed_xp = self.get_xp(self.get_level(xp, settings) + 1, settings)
        current_xp = xp - self.get_xp(self.get_level(xp, settings) - 1, settings)
        to_level_up = needed_xp - self.get_xp(
            (self.get_level(xp, settings) - 1), settings
        )
        percentage_completed = int((current_xp / to_level_up) * 100)
        ranking = await self.get_rank(member.guild, member, True)
        if isinstance(ranking[0], int):
            server_rank = f"`#{ranking[0]} out of {ranking[1]}`"
        else:
            if ranking[1] > 0:
                server_rank = f"`N/A out of {ranking[1]}`"
            else:
                server_rank = "`N/A`"
        # the kwargs white and black are the colors for the bar
        embed = (
            Embed(
                title=f"{str(member)}'s level",
                url=f"https://{CONFIG['domain']}",
                timestamp=datetime.now(),
            )
            .add_field(name="Level", value=self.get_level(xp, settings), inline=True)
            .add_field(name="Server Rank", value=server_rank, inline=True)
            .add_field(
                name="Experience",
                value=f"{int(current_xp)} / {to_level_up}",
                inline=True,
            )
            .add_field(
                name=f"Progress ({percentage_completed}%)",
                value=get_bar(ctx.bot, percentage_completed),
                inline=True,
            )
            .set_footer(text=f"Total Experience {int(xp)}")
            .set_thumbnail(url=member.display_avatar.url)
            .set_author(
                name=member.display_name, icon_url=ctx.bot.user.display_avatar.url
            )
        )
        return await ctx.send(embed=embed)
