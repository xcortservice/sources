import re
from asyncio import (CancelledError, Lock, all_tasks, as_completed,
                     create_task, ensure_future, gather, sleep)
from collections import defaultdict
from io import BytesIO
from itertools import chain
from random import choice, shuffle
from typing import Any, Dict, List, Optional, Union

import msgspec
from cashews import cache
from discord import (Client, Embed, File, Guild, Member, Message, TextChannel,
                     Thread, User, ui, utils)
from discord.ext.commands import (Cog, CommandError, check, command, group,
                                  has_permissions, hybrid_command,
                                  hybrid_group)
from discord.http import iteration
from loguru import logger
from system.managers.flags.fun import BlackTeaFlags
from system.patch.context import Context
from system.worker import offloaded
from tools import timeit

from .games.blacktea import BlackteaButton, start_blacktea

URL_RE = re.compile(
    r"([\w+]+\:\/\/)?([\w\d-]+\.)*[\w-]+[\.\:]\w+([\/\?\=\&\#]?[\w-]+)*\/?", flags=re.I
)


@offloaded
def read_words():
    with open("data/words.txt", "r") as file:
        data = file.read().splitlines()
    return data


def blacktea_round():
    async def predicate(ctx: Context):
        if ctx.bot.blacktea_matches.get(ctx.guild.id):
            await ctx.alert("There's a match of blacktea in progress")

        return ctx.guild.id not in ctx.bot.blacktea_matches.keys()

    return check(predicate)


@offloaded
def generate_wc(data: dict):
    text = data["text"]
    from io import BytesIO

    from wordcloud import ImageColorGenerator  # type: ignore
    from wordcloud import WordCloud as WCloud  # type: ignore

    resolution = {"width": 1920, "height": 1080}
    wc = WCloud(**resolution)
    wc.generate(text=text)
    file = BytesIO()
    image = wc.to_image()
    image.save(file, format="PNG")
    file.seek(0)
    return file.getvalue()


@offloaded
def load_pack():
    with open("data/pack.yaml", "rb") as file:
        data = file.read()
    return msgspec.yaml.decode(data)


class Fun(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.locks = defaultdict(Lock)
        self.buttons: Dict[int, BlackteaButton] = {}

    async def cog_load(self):
        bible = await load_pack()
        shuffle(bible)
        self.pack_bible = iteration(bible)
        if not await self.bot.redis.exists("words"):
            await self.load_words()

    async def load_words(self):
        words = await read_words()
        await self.bot.redis.sadd("words", *words)
        return True

    @command(
        name="pack", description="blaze that nigga yahurd", example=",pack jonathan"
    )
    async def pack(self, ctx: Context, *, member: Member):
        async with self.locks["pack"]:
            tasks = [
                create_task(ctx.send(f"{member.mention} {next(self.pack_bible)}"))
                for i in range(5)
            ]
            for t in as_completed(tasks):
                await t
                await sleep(0.5)
        return

    def filter_messages(
        self,
        message: Message,
        user: Optional[Member] = None,
        channel: Optional[TextChannel] = None,
    ) -> bool:
        val = True
        if user is not None:
            if message.author.id != user.id:
                val = False
        if channel is not None:
            if message.channel.id != channel.id:
                val = False
        return val

    @cache(ttl=111200, key="messages:{channel}")
    async def do_fetch(self, channel: TextChannel, limit: int = 5000) -> List[Message]:
        messages = [
            m async for m in channel.history(limit=limit) if m.content is not None
        ]
        ensure_future(gather(*[self.bot.redis.add_message(m) for m in messages]))
        return messages

    async def fetch_messages(self, channel: TextChannel, user: Optional[Member] = None):
        messages = await self.do_fetch(channel)
        return [m for m in messages if self.filter_messages(m, user) is not False]

    async def clean_message(self, message: Union[Message, str, bytes]) -> str:
        if isinstance(message, bytes):
            message = str(message)
        try:
            message = (message.encode("utf-8")).decode("utf-8")
        except Exception:
            pass
        if isinstance(message, str):
            try:
                message = message.decode("utf-8")
            except Exception:
                pass
            text = URL_RE.sub("", message)
            text = text + ""
            return text
        text = URL_RE.sub("", message.clean_content)
        text = text + " "
        return text

    async def get_guild_messages(self, guild: Guild):
        messages = list(
            chain.from_iterable(
                await gather(
                    *[self.bot.redis.get_all_messages(guild, u) for u in guild.members]
                )
            )
        )
        messages = [i.decode() for i in messages]
        content = await gather(*[self.clean_message(m) for m in messages])
        text = " ".join(c for c in content)
        return text

    async def get_messages(
        self, ctx, user: Optional[Member] = None, channel: Optional[TextChannel] = None
    ) -> str:
        if channel is None:
            messages = await self.bot.redis.get_all_messages(ctx.guild, user)
            messages = [i.decode() for i in messages]
            if len(messages) < 200:
                _messages = []
                i = 0
                for c in ctx.guild.text_channels:
                    m = await self.fetch_messages(c, user)
                    i += len(m)
                    if len(messages) + i >= 200:
                        _messages.extend(m)
                        break
                    else:
                        _messages.extend(m)
                if isinstance(_messages[0], list):
                    _messages = list(chain.from_iterable(_messages))
                messages.extend(_messages)
        else:
            messages = await self.bot.redis.get_messages(ctx)
            messages = [i.decode() for i in messages]
            if len(messages) <= 200:
                m = await self.fetch_messages(channel, user)
                if isinstance(m[0], list):
                    m = list(chain.from_iterable(m))
                for _ in m:
                    messages.append(_)
        if isinstance(messages[0], list):
            messages = list(chain.from_iterable(messages))
        content = await gather(*[self.clean_message(m) for m in messages])
        text = " ".join(c for c in content)
        return text

    #    @offloaded
    def _generate_wc(self, data: dict):
        text = data["text"]
        from io import BytesIO

        from wordcloud import WordCloud as WCloud  # type: ignore

        kwargs = {
            "mask": None,
            "color_func": None,
            "mode": "RGB",
            "font_path": "data/Arial.ttf",
            "background_color": "black",
            "max_words": 200,
            "max_font_size": 50,
            "stopwords": [],
            "min_word_length": 3,
            "width": 600,
            "height": 400,
            "normalize_plurals": True,
        }
        wc = WCloud(**kwargs)
        wc.generate(text=text)
        file = BytesIO()
        image = wc.to_image()
        image.save(file, format="PNG")
        file.seek(0)
        return file.getvalue()

    async def get_global_messages(self, user: Union[Member, User]):
        if user := self.bot.get_user(user):
            guilds = {
                str(g.id): [str(c.id) for c in g.text_channels]
                for g in user.mutual_guilds
            }
            id = user.id
        else:
            guilds = {}
            id = user
        for source in self.bot.sources:
            if source != self.bot.cluster_name:
                data = await self.bot.ipc.request(
                    "get_wc_guilds", source=source, user_id=id
                )
                guilds.update(data)
        messages = list(
            chain.from_iterable(
                await gather(
                    *[
                        self.bot.redis.get_all_messages(guild, user, channels)
                        for guild, channels in guilds.items()
                    ]
                )
            )
        )
        messages = [i.decode() for i in messages]
        #        messages = [m.encode('UTF-8').decode('UTF-8') for m in messages]
        messages = await gather(*[self.clean_message(m) for m in messages])
        text = " ".join(m for m in messages)
        text = " ".join(m for m in text.split(" "))
        return text

    async def do_wc(
        self,
        ctx,
        user: Optional[Member] = None,
        channel: Optional[TextChannel] = None,
        is_global: Optional[bool] = False,
    ):
        if is_global is True:
            s = " global "
        else:
            s = ""
        async with timeit() as timer:
            message = await ctx.normal(f"Please wait while I fetch{s} messages...")
            if is_global is True:
                text = await self.get_global_messages(user)
            else:
                if user is not None:
                    text = await self.get_messages(ctx, user, channel)
                else:
                    if channel is None:
                        text = await self.get_guild_messages(ctx.guild)
                    else:
                        text = await self.get_messages(ctx, user, channel)
            file = await generate_wc({"text": text})
            file = File(fp=BytesIO(file), filename="wordcloud.png")
        timed = f"took {int(timer.elapsed)} seconds"
        return await message.edit(
            attachments=[file],
            embed=Embed(
                color=message.embeds[0].color,
                description=f"{self.bot.config['emojis']['success']} {ctx.author.mention}: successfully generated **wordcloud**",
            ).set_footer(text=timed),
        )

    @hybrid_group(
        name="wordcloud",
        aliases=["wc", "wcloud", "words"],
        description="generate a collage of top words said by a user or in a channel/server",
        invoke_without_command=True,
        with_app_command=True,
    )
    async def wordcloud(
        self,
        ctx,
        user: Optional[Union[User, Member]] = None,
        channel: Optional[TextChannel] = None,
    ):
        if "-global" in ctx.message.content:
            is_global = True
        else:
            is_global = False
        return await self.do_wc(ctx, user, channel, is_global)

    @wordcloud.command(
        name="global",
        description="make a wordcloud of a user's global messages",
        with_app_command=True,
    )
    async def wordcloud_global(
        self, ctx, *, user: Optional[Union[Member, User]] = None
    ):
        user = user or ctx.author
        message = await ctx.normal(
            "please wait while I fetch all of the messages needed.."
        )
        async with timeit() as timer:
            try:
                text = await self.get_global_messages(user.id or user)
                file = await generate_wc({"text": text})
            except Exception:
                return await message.edit(
                    embed=Embed(
                        color=self.bot.color,
                        description="no **messages** found for that user",
                    )
                )
        return await message.edit(
            attachments=[File(fp=BytesIO(file), filename="wordcloud.png")],
            embed=Embed(
                color=self.bot.color,
                description=f"{self.bot.config['emojis']['success']} {ctx.author.mention}: successfully generated the wordcloud",
            ).set_footer(text=f"took {int(timer.elapsed)} seconds"),
        )

    def get_button(self, guild: Guild):
        if button := self.buttons.get(guild.id):
            return button.users
        else:
            return []

    @hybrid_group(
        name="blacktea",
        description="Find a word with 3 letters!",
        invoke_without_command=True,
    )
    @blacktea_round()
    async def blacktea(self: "Fun", ctx: Context, *, flags: BlackTeaFlags):
        return await create_task(
            start_blacktea(ctx, life_count=flags.lives, timeout=flags.timeout),
            name=f"blacktea-{ctx.guild.id}",
        )

    @blacktea.command(
        name="end", aliases=["stop"], description="end an existing game of blacktea"
    )
    @has_permissions(manage_guild=True)
    async def blacktea_end(self, ctx: Context):
        tasks = all_tasks()
        task = None
        for _t in tasks:
            if _t.get_name() == f"blacktea-{ctx.guild.id}":
                task = _t
                break
        if not task:
            raise CommandError("there is no current blacktea game going on")
        task.cancel()
        if messages := self.bot.blacktea_messages.get(ctx.guild.id):
            for chunk in utils.chunk_list(messages, 99):
                await ctx.channel.delete_messages(chunk)
        try:
            await task
        except CancelledError:
            pass
        return await ctx.success("successfully ended the ongoing blacktea game")


async def setup(bot: Client):
    await bot.add_cog(Fun(bot))
