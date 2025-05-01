import io
import re
import discord
import textwrap
import random
import aiohttp
import asyncio
import datetime
import logging
import time
from random import choice
from unidecode import unidecode

from discord import (
    Message, 
    Embed, 
    TextChannel, 
    Interaction, 
    Member, 
    User,
    ButtonStyle,
    File,
    TextStyle,
    Member
)
from discord.ext.commands import (
    command, 
    group, 
    Cog, 
    cooldown, 
    BucketType,
    max_concurrency,
    hybrid_command,
    hybrid_group,
    Author
)
from discord.ui import (
    Button,
    button,
    View, 
    Select,
    TextInput,
    Modal,
    View
)
from typing import List, Dict, Literal, Set, Optional
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from typing import List
from color_processing import ColorInfo
from googleapiclient.discovery import build

from greed.framework import Greed, Context
from greed.framework.tools import offloaded, plural
from greed.shared.config import Colors

from .config.responses import eightball, roasts, nword
from .config.extras.jeyy import JeyyAPI
from .config.extras.jeyy import CommandOnCooldown
from .config.extras.alexflipnote import alexflipnote_api
from .config.extras.alexflipnote import CommandOnCooldown
from .config.extras.popcat import popcat_api
from .config.extras.popcat import CommandOnCooldown

from greed.data.emotes import EMOJIS
# from tool.managers.bing import BingService

# from greed.tool import aliases
logger = logging.getLogger("greed/fun")

IMAGE_FOLDER = "/root/greed/data/nba"
FONT_PATH = "/root/greed/data/fonts"
GOOGLE_API_KEY = "AIzaSyCgPL4hAT14sdyylXxY_R-hXJN4XMo7zZo"
SEARCH_ENGINE_ID = "8691350b6083348ae"

@offloaded
def get_dominant_color(image_bytes: bytes) -> dict:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    colors = image.getcolors(maxcolors=1000000)
    colorful_colors = [color for color in colors if len(set(color[1])) > 1]
    dominant_color = max(colorful_colors, key=lambda item: item[0])[1]
    return {"dominant_color": dominant_color}


@offloaded
def rotate_image(image_bytes: bytes, angle: int) -> bytes:
    image = Image.open(BytesIO(image_bytes)).rotate(angle, expand=True)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@offloaded
def compress_image(image_bytes: bytes, quality: int = None) -> bytes:
    image = Image.open(BytesIO(image_bytes))
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality or 10, optimize=True)
    return output.getvalue()


@offloaded
async def do_caption(para: list, image_bytes: bytes, message_data: dict):
    if isinstance(image_bytes, BytesIO):
        image_bytes = image_bytes.getvalue()

    image = Image.open(BytesIO(image_bytes))
    haikei = Image.open("quote/grad.jpeg")
    black = Image.open("quote/black.jpeg")

    w, h = (680, 370)

    haikei = haikei.resize((w, h))
    black = black.resize((w, h))

    icon = image.resize((w, h))
    icon = icon.convert("L")
    icon = icon.crop((40, 0, w, h))

    new = Image.new(mode="L", size=(w, h))
    new.paste(icon)

    sa = Image.composite(new, black, haikei.convert("L"))

    draw = ImageDraw.Draw(sa)
    fnt = ImageFont.truetype("quote/Arial.ttf", 28)

    _, _, w2, h2 = draw.textbbox((0, 0), "a", font=fnt)
    i = (int(len(para) / 2) * w2) + len(para) * 5
    current_h, pad = 120 - i, 0

    for line in para:
        if message_data["content"].replace("\n", "").isascii():
            _, _, w3, h3 = draw.textbbox(
                (0, 0), line.ljust(int(len(line) / 2 + 11), " "), font=fnt
            )
            draw.text(
                (11 * (w - w3) / 13 + 10, current_h + h2),
                line.ljust(int(len(line) / 2 + 11), " "),
                font=fnt,
                fill="#FFF",
            )
        else:
            _, _, w3, h3 = draw.textbbox(
                (0, 0), line.ljust(int(len(line) / 2 + 5), "　"), font=fnt
            )
            draw.text(
                (11 * (w - w3) / 13 + 10, current_h + h2),
                line.ljust(int(len(line) / 2 + 5), "　"),
                font=fnt,
                fill="#FFF",
            )

        current_h += h3 + pad

    font = ImageFont.truetype("quote/Arial.ttf", 15)
    _, _, authorw, _ = draw.textbbox((0, 0), f"-{message_data['author']}", font=font)
    draw.text(
        (480 - int(authorw / 2), current_h + h2 + 10),
        f"-{message_data['author']}",
        font=font,
        fill="#FFF",
    )

    output = BytesIO()
    sa.save(output, format="JPEG")
    output_bytes = output.getvalue()

    return output_bytes

class TicTacToeButton(Button):
    """
    Represents a button on the Tic Tac Toe board.
    """
    def __init__(
        self, x: int, y: int, player1: Member, player2: Member
    ):
        super().__init__(style=ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y
        self.player1 = player1
        self.player2 = player2

    async def callback(self, interaction: Interaction):
        """
        Handles the button click event.
        """
        assert self.view is not None
        view: "TicTacToe" = self.view
        if view.board[self.y][self.x] in (view.X, view.O):
            return

        if (
            view.current_player == view.X and interaction.user.id != self.player1.id
        ) or (view.current_player == view.O and interaction.user.id != self.player2.id):
            return await interaction.response.send_message(
                "It's not your turn!", ephemeral=True
            )

        self.style = (
            ButtonStyle.danger
            if view.current_player == view.X
            else ButtonStyle.success
        )
        self.label = "X" if view.current_player == view.X else "O"
        self.disabled = True
        view.board[self.y][self.x] = view.current_player
        view.switch_player()

        winner = view.check_board_winner()
        if winner is not None:
            content = (
                "It's a tie!"
                if winner == view.Tie
                else f"**{self.player1.mention if winner == view.X else self.player2.mention}** won!"
            )

            for child in view.children:
                if isinstance(child, Button):
                    child.disabled = True
            view.stop()
        else:
            content = f"It's **{self.player1.mention if view.current_player == view.X else self.player2.mention}**'s turn."

        await interaction.response.edit_message(content=content, view=view)


class TicTacToe(View):
    """
    Represents the Tic Tac Toe game board and logic.
    """
    children: List[TicTacToeButton]
    X = -1
    O = 1
    Tie = 0

    def __init__(self, player1: Member, player2: Member):
        super().__init__()
        self.current_player = self.X
        self.player1 = player1
        self.player2 = player2
        self.board = [[0 for _ in range(3)] for _ in range(3)]

        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y, player1, player2))

    def check_board_winner(self) -> Optional[int]:
        """
        Checks the board for a winner or tie.
        Returns:
            - X (-1) if player 1 wins
            - O (1) if player 2 wins
            - Tie (0) if the game is a draw
            - None if the game is still ongoing
        """
        board = self.board

        lines = (
            board
            + [list(col) for col in zip(*board)]
            + [
                [board[i][i] for i in range(3)],
                [board[i][2 - i] for i in range(3)],
            ]
        )

        for line in lines:
            if all(cell == self.X for cell in line):
                return self.X
            if all(cell == self.O for cell in line):
                return self.O

        if all(cell != 0 for row in board for cell in row):
            return self.Tie

        return None

    def switch_player(self):
        """
        Switches the current player.
        """
        self.current_player = self.O if self.current_player == self.X else self.X

    async def on_timeout(self):
        """
        Handles the timeout event when the game times out.
        """
        for item in self.children:
            item.disabled = True
        if hasattr(self, "message"):
            await self.message.edit(view=self)


class DiaryModal(Modal, title="Create a Diary Entry"):
    """
    Creates a modal for creating a diary entry.
    """
    def __init__(self):
        super().__init__()

        self.title_input = TextInput(
            label="Diary Title",
            placeholder="Enter the title of your diary",
            required=True,
            max_length=100,
        )
        self.text_input = TextInput(
            label="Diary Content",
            style=TextStyle.paragraph,
            placeholder="Write your thoughts here...",
            required=True,
            max_length=2000,
        )

        self.add_item(self.title_input)
        self.add_item(self.text_input)

    async def on_submit(self, interaction: Interaction):
        """
        Submits the diary entry.
        """
        now = datetime.now()
        date = f"{now.month}/{now.day}/{str(now.year)[2:]}"

        user_id = interaction.user.id
        title = self.title_input.value
        content = self.text_input.value
        await interaction.client.db.execute(
            "INSERT INTO diary (user_id, date, title, text) VALUES ($1, $2, $3, $4)",
            user_id,
            date,
            title,
            content,
        )

        await interaction.response.send_message(
            f"Diary entry created for {date}!", ephemeral=True
        )


class GuildData:
    """
    Holds per-guild data for the BlackTea game.
    """
    def __init__(self):
        self.players: List[int] = []
        self.lives: Dict[str, int] = {}
        self.guessed_words: Set[str] = set()


class BlackTea:
    """
    Manages the core mechanics of the BlackTea game.
    """
    LIFE_LIMIT = 3
    WORDS_URL = "https://raw.githubusercontent.com/ScriptSmith/topwords/refs/heads/master/words.txt"

    def __init__(self, bot):
        self.bot = bot
        self.color = 0xA5D287
        self.emoji = "<a:boba_tea_green_gif:1302250923858591767>"
        self.match_started = set()
        self.guild_data = {}
        self.lock = asyncio.Lock()
        self.words = []
        self.tasks = {}
        asyncio.create_task(self.fetch_word_list())

    async def fetch_word_list(self):
        """
        Fetches and preloads the word list, handling encoding issues.
        """
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.WORDS_URL) as response:
                    response.raise_for_status()
                    try:
                        text = await response.text(encoding="utf-8")
                    except UnicodeDecodeError as e:
                        logger.warning(
                            f"UTF-8 decoding failed: {e}. Falling back to ISO-8859-1."
                        )

                        text = await response.text(encoding="ISO-8859-1")

                    self.words = [
                        line.strip()
                        for line in text.splitlines()
                        if line.strip() and line.strip().isalpha()
                    ]
            except Exception as e:
                logger.error(f"Error fetching word list: {e}")
                raise RuntimeError("Failed to fetch words") from e

    def pick_random_prefix(self) -> str:
        """
        Picks a random 3-letter prefix from the list of valid words.
        """
        valid_words = [word for word in self.words if len(word) >= 3]
        if not valid_words:
            raise ValueError("No suitable words found.")
        return random.choice(valid_words)[:3]

    async def decrement_life(self, member_id: str, channel: TextChannel, reason: str):
        """
        Reduces a player's life and handles elimination if lives reach zero.
        """
        guild_id = channel.guild.id
        guild_data = self.guild_data.get(guild_id)

        if not guild_data:
            raise ValueError("Game not initialized for this guild.")

        if member_id not in guild_data.lives:
            raise ValueError("Player not in game.")

        guild_data.lives[member_id] -= 1
        remaining_lives = guild_data.lives[member_id]

        if remaining_lives <= 0:
            guild_data.players.remove(int(member_id))
            del guild_data.lives[member_id]
            await channel.send(f"☠️ <@{member_id}> is eliminated!")
        else:
            await channel.send(
                f"💥 <@{member_id}> lost a life ({reason}). {remaining_lives} lives left.",
            )

    async def handle_guess(
        self,
        user: int,
        channel: TextChannel,
        prefix: str,
        session: GuildData,
    ):
        """
        Handles a player's guessing turn with countdown reactions and timeout handling.
        """
        member = channel.guild.get_member(user)
        member_id = str(user)

        INITIAL_TIMEOUT = 7
        COUNTDOWN_REACTIONS = ["3️⃣", "2️⃣", "1️⃣"]

        prompt_message = await channel.send(
            content=member.mention,
            embed=Embed(
                description=f"🎯 {member.mention}, your word must contain: **{prefix}**. "
                f"You have 10 seconds to respond!"
            ),
        )

        try:
            message: Message = await self.bot.wait_for(
                "message",
                check=lambda m: (
                    m.channel.id == channel.id
                    and m.author.id == user
                    and m.content.lower() in self.words
                    and prefix.lower() in m.content.lower()
                    and m.content.lower() not in session.guessed_words
                ),
                timeout=INITIAL_TIMEOUT,
            )

            session.guessed_words.add(message.content.lower())
            await channel.send(
                embed=Embed(description=f"✅ Correct answer, {member.mention}!")
            )
            return True

        except asyncio.TimeoutError:
            for reaction in COUNTDOWN_REACTIONS:
                await prompt_message.add_reaction(reaction)
                await asyncio.sleep(1)

            await self.decrement_life(member_id, channel, "timeout")
            return False

    async def start_match(self, guild_id: int):
        """
        Starts a new match, ensuring no existing match is in progress.
        """
        async with self.lock:
            if guild_id in self.match_started:
                raise ValueError("A BlackTea match is already in progress.")

            guild_data = GuildData()
            guild_data.lives = {}
            self.guild_data[guild_id] = guild_data
            self.match_started.add(guild_id)

    def reset_guild_data(self, guild_id: int):
        """
        Resets guild-specific game data and cancels any running task.
        """
        if guild_id in self.tasks:
            self.tasks[guild_id].cancel()
            self.tasks.pop(guild_id)
        self.guild_data.pop(guild_id, None)
        self.match_started.discard(guild_id)

    async def run_game(self, ctx: Context, guild_id: int):
        """
        Handles the main game loop as a task.
        """
        try:
            message = await ctx.send(
                embed=Embed(
                    color=self.color,
                    title="BlackTea Matchmaking",
                    description=(
                        "React to join the game!\n"
                        "Each player will take turns guessing words containing specific letters.\n"
                        "Run out of time or make incorrect guesses, and you lose lives. "
                        "The last player standing wins!"
                    ),
                )
            )

            await message.add_reaction("☕")
            await asyncio.sleep(10)

            try:
                message = await ctx.channel.fetch_message(message.id)
                if not message.reactions:
                    raise ValueError("No players joined the game!")
            
            except discord.NotFound:
                raise ValueError("The game message was deleted!")

            users = [u.id async for u in message.reactions[0].users() if not u.bot]

            if len(users) < 2:
                raise ValueError("Not enough players to start!")

            guild_data = self.guild_data[guild_id]
            guild_data.players = users
            guild_data.lives = {str(user): self.LIFE_LIMIT for user in users}
            guild_data.guessed_words = set()

            while len(guild_data.players) > 1:
                for user in list(guild_data.players):
                    prefix = self.pick_random_prefix()
                    correct = await self.handle_guess(
                        user=user,
                        channel=ctx.channel,
                        prefix=prefix,
                        session=guild_data,
                    )
                    if not correct and user not in guild_data.players:
                        continue

            if guild_data.players:
                winner = guild_data.players[0]
                await ctx.embed(
                    message=f"👑 <@{winner}> won the game!",
                    message_type="neutral")

        except asyncio.CancelledError:
            await ctx.embed(
                message="Game cancelled!",
                message_type="neutral"
            )
            raise
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
        finally:
            self.reset_guild_data(guild_id)


@offloaded
async def fetch_avatar(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.read()


@offloaded
def ship_img(avatar1_bytes, avatar2_bytes, compatibility):
    width = 1200
    height = 650
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    avatar1 = Image.open(io.BytesIO(avatar1_bytes)).convert("RGBA")
    avatar2 = Image.open(io.BytesIO(avatar2_bytes)).convert("RGBA")

    avatar1 = avatar1.resize((250, 250))
    avatar2 = avatar2.resize((250, 250))

    def create_circle_mask(size):
        circle_mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(circle_mask)
        draw.ellipse((0, 0, size[0], size[1]), fill=255)
        return circle_mask

    avatar1_mask = create_circle_mask(avatar1.size)
    avatar2_mask = create_circle_mask(avatar2.size)

    avatar1.putalpha(avatar1_mask)
    avatar2.putalpha(avatar2_mask)

    image.paste(avatar1, (150, 200), avatar1)
    image.paste(avatar2, (width - 150 - 250, 200), avatar2)

    corner_radius = 25
    progress_bar_width = 800
    progress_bar_height = 70
    progress_bar_x = (width - progress_bar_width) // 2
    progress_bar_y = 40

    gradient = Image.new(
        "RGBA", (progress_bar_width, progress_bar_height), (255, 255, 255, 255)
    )
    gradient_draw = ImageDraw.Draw(gradient)

    for x in range(progress_bar_width):
        r = int((x / progress_bar_width) * 255)
        g = int((x / progress_bar_width) * 105)
        b = int((x / progress_bar_width) * 180)
        gradient_draw.line((x, 0, x, progress_bar_height), fill=(r, g, b))

    mask = Image.new("L", (progress_bar_width, progress_bar_height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        [0, 0, progress_bar_width, progress_bar_height], radius=corner_radius, fill=255
    )

    gradient.putalpha(mask)

    fill_width = int((compatibility / 100) * progress_bar_width)
    visible_gradient = gradient.crop((0, 0, fill_width, progress_bar_height))

    image.paste(visible_gradient, (progress_bar_x, progress_bar_y), visible_gradient)

    heart_path = "heart.png"
    heart = Image.open(heart_path).convert("RGBA")
    heart = heart.resize((120, 120))

    image.paste(heart, (width // 2 - 60, height // 2 - 60), heart)

    image = image.filter(ImageFilter.SMOOTH)

    with io.BytesIO() as image_binary:
        image.save(image_binary, "PNG")
        image_binary.seek(0)
        return image_binary.read()

from typing import Dict, List, Optional, Any, Self
from pydantic import BaseModel
from xxhash import xxh64_hexdigest
from redis.asyncio import Redis
from typing import cast

class Flags(BaseModel):
    message_id: int
    channel_id: int
    waiting: bool = True
    players: Dict[int, int] = {}
    current_difficulty: str = "easy"
    used_flags: List[str] = []

    @staticmethod
    def key(channel_id: int) -> str:
        return xxh64_hexdigest(f"flags:{channel_id}")

    @classmethod
    async def get(cls, redis: Redis, channel_id: int) -> Optional[Self]:
        data = await redis.get(cls.key(channel_id))
        if not data:
            return None
        return cls.model_validate_json(data)

    async def save(self, redis: Redis, **kwargs) -> None:
        await redis.set(self.key(self.channel_id), self.model_dump_json(), **kwargs)

    async def delete(self, redis: Redis) -> None:
        await redis.delete(self.key(self.channel_id))


class Fun(Cog):
    def __init__(self, bot: Greed):
        self.bot = bot
        self.book = "📖"
        self.pen = "📖"
        self.blacktea = BlackTea(self.bot)
        # self.bing = BingService(self.bot.redis, None)
        self.flavors = [
            "Strawberry",
            "Mango",
            "Blueberry",
            "Watermelon",
            "Grape",
            "Pineapple",
            "Vanilla",
            "Chocolate",
            "Caramel",
            "Mint",
            "Coffee",
            "Cinnamon",
            "Bubblegum",
            "Peach",
            "Apple",
            "Lemon",
            "Cherry",
            "Raspberry",
        ]
        self.flag_difficulties = {
            "easy": [
                "us", "gb", "ca", "fr", "de", "it", "es", "jp", "br", "au", 
                "cn", "in", "ru", "kr", "mx", "za", "tr", "ar", "se", "no",
                "dk", "fi", "pt", "gr", "ie", "ch", "be", "nl"
            ],
            "medium": [
                "eg", "sa", "ae", "pl", "ua", "ro", "at", "hu", "cz", "il",
                "th", "vn", "ph", "my", "id", "sg", "nz", "cl", "co", "ve",
                "ma", "ng", "dz", "ke", "pk", "ir", "iq", "kz", "af", "is"
            ],
            "hard": [
                "al", "am", "az", "ba", "bg", "by", "cy", "ee", "ge", "hr",
                "lt", "lv", "md", "me", "mk", "mt", "rs", "si", "sk", "tn",
                "lb", "jo", "kw", "qa", "om", "uz", "tm", "kg", "tj", "mn",
                "np", "bd", "lk", "mm", "kh", "la", "bn", "pg", "uy", "py",
                "bo", "ec", "pe", "cr", "pa", "do", "ht", "tt", "bs", "bb",
                "bh", "ye", "sy", "sd", "er", "et", "ug", "tz", "mz", "zm",
                "na", "bw", "zw", "gh", "ci", "cm", "ga", "cg", "ao"
            ]
        }

    @Cog.listener()
    async def on_message(self, message):
        """
        Listener that checks for offensive words and updates the count.
        """
        if message.author.bot:
            return

        user_id = message.author.id
        content = message.content.lower()

        general_word = r"\bnigga\b"
        hard_r_word = r"\bnigger\b"

        try:
            if re.search(general_word, content, re.IGNORECASE):
                await self.increment_offensive_count(user_id, "general_count")

            if re.search(hard_r_word, content, re.IGNORECASE):
                await self.increment_offensive_count(user_id, "hard_r_count")

        except Exception as e:
            logger.error(f"Error processing message from {message.author}: {e}")

    async def increment_offensive_count(self, user_id, column):
        """
        Increments the offensive word count for a user in the database.
        """
        try:
            query = f"""
                INSERT INTO offensive (user_id, {column}) 
                VALUES ($1, 1)
                ON CONFLICT (user_id) 
                DO UPDATE SET {column} = offensive.{column} + 1
            """
            await self.bot.db.execute(query, user_id)

        except Exception as e:
            logger.error(f"Error incrementing count for user {user_id}: {e}")

    async def get_caption(
        self, ctx: Context, message: Optional[Message] = None
    ) -> Optional[Message]:

        if message is None:
            msg = ctx.message.reference
            if msg is None:
                return await ctx.embed(
                    message="no **message** or **reference** provided", 
                    message_type="warned"
                )
            id = msg.message_id
            message = await ctx.fetch_message(id)

        image = BytesIO(await message.author.display_avatar.read())
        image.seek(0)
        if message.content.replace("\n", "").isascii():
            para = textwrap.wrap(message.clean_content, width=26)
        else:
            para = textwrap.wrap(message.clean_content, width=13)

        output = await do_caption(
            para,
            image,
            message_data={"author": message.author.name, "content": message.content},
        )
        buffer = BytesIO(output)
        buffer.seek(0)
        file = discord.File(fp=buffer, filename="quote.png")
        return await ctx.send(file=file)

    @command(name="uwuify", aliases=["uwu"])
    async def uwuify(self, ctx: Context, *, message: str):
        """
        Make a message uwuified.
        """
        try:
            text = await self.bot.rival.uwuify(message)
            return await ctx.send(text)
        
        except Exception:
            return await ctx.embed(message="couldn't uwuify that message", message_type="fail")

    @group(name="blacktea", invoke_without_command=True)
    async def blacktea(self, ctx: Context):
        """
        Starts a BlackTea game with server members.
        """
        guild_id = ctx.guild.id

        try:
            await self.blacktea.start_match(guild_id)
        
        except ValueError as e:
            return await ctx.send(str(e))

        if not self.blacktea.words:
            try:
                await self.blacktea.fetch_word_list()
            except Exception as e:
                self.blacktea.reset_guild_data(guild_id)
                return await ctx.embed(
                    message=f"Failed to load word list: {e}",
                    message_type="warned"
                )

        task = asyncio.create_task(self.blacktea.run_game(ctx, guild_id))
        self.blacktea.tasks[guild_id] = task

        try:
            await task
        except asyncio.CancelledError:
            pass

    @blacktea.command(name="end")
    async def blacktea_end(self, ctx: Context):
        """
        Ends an ongoing BlackTea match.
        """
        if ctx.guild.id in self.blacktea.tasks:
            self.blacktea.reset_guild_data(ctx.guild.id)
            await ctx.embed(
                message="BlackTea match ended!", 
                message_type="neutral"
            )
        else:
            await ctx.embed(
                message="No active BlackTea game to end!", 
                message_type="warned"
            )

    @command()
    async def spark(self, ctx: Context):
        """
        Light the blunt.
        """
        user_id = ctx.author.id
        row = await self.bot.db.fetchrow(
            """
            SELECT sparked, last_sparked 
            FROM blunt_hits 
            WHERE user_id = $1
            """, 
            user_id
        )

        if row:
            sparked, last_sparked = row
            if not sparked or (datetime.now() - last_sparked).total_seconds() > 300:
                await self.bot.db.execute(
                    """
                    INSERT INTO blunt_hits (user_id, sparked, last_sparked)
                    VALUES ($1, TRUE, $2)
                    ON CONFLICT (user_id)
                    DO UPDATE SET sparked = TRUE, last_sparked = $2
                    """,
                    user_id,
                    datetime.now(),
                )
                return await ctx.embed(
                    message="You sparked the blunt!", 
                    message_type="neutral"
                )
            elif sparked:
                return await ctx.embed(
                    message="You already sparked the blunt!", 
                    message_type="warned"
                )
            else:
                remaining_time = timedelta(seconds=300) - (
                    datetime.now() - last_sparked
                )
                remaining_minutes, remaining_seconds = divmod(
                    int(remaining_time.total_seconds()), 60
                )
                return await ctx.embed(
                    message=f"You need to wait `{remaining_minutes}m {remaining_seconds}s` before sparking again!", 
                    message_type="warned"
                )
        else:
            await self.bot.db.execute(
                """
                INSERT INTO blunt_hits (user_id, sparked, last_sparked)
                VALUES ($1, TRUE, $2)
                """,
                user_id,
                datetime.now(),
            )
            await ctx.embed(
                message="You sparked the blunt!", 
                message_type="neutral"
            )

    @command()
    @cooldown(1, 10, BucketType.user)
    async def smoke(self, ctx: Context):
        """
        Smoke the blunt.
        """
        record = await self.bot.db.fetchrow(
            """
            SELECT sparked, taps 
            FROM blunt_hits 
            WHERE user_id = $1
            """, 
            ctx.author.id
        )

        if record and record[0]:
            taps = record[1]
            if taps < 100000000:
                await self.bot.db.execute(
                    """
                    UPDATE blunt_hits SET taps = taps + 1 
                    WHERE user_id = $1
                    """, 
                    ctx.author.id
                )
                await ctx.embed(
                    message=f"{ctx.author.mention} smoked the blunt {taps + 1} times!", 
                    message_type="neutral"
                )
            else:
                await ctx.embed(
                    message="Your blunt has gone out!", 
                    message_type="warned"
                )
        else:
            await ctx.embed(
                message="You need to spark the blunt first!", 
                message_type="warned"
            )

    @command()
    async def taps(self, ctx: Context, user: Member = Author):
        """
        Check how many times you've hit the blunt.
        """
        record = (
            await self.bot.db.fetchval(
                """
                SELECT taps 
                FROM blunt_hits 
                WHERE user_id = $1
                """, 
                user.id
            )
            or 0
        )
        await ctx.embed(
            message=f"{user.mention if user is not ctx.author else 'Your'} blunt has {'not been smoked yet!' if record == 0 else f'been smoked {record} time!' if record == 1 else f'been smoked `{record}` times!'}",
            message_type="neutral"
        )

    @command(help="shows how gay you are", description="fun", usage="<member>")
    async def howgay(self, ctx: Context, user: Member = Author):
        """
        Check how gay you are.
        """
        await ctx.embed(
            message=f"{user.mention if user is not ctx.author else 'Your'} gay percentage is `{random.randrange(101)}%`", 
            message_type="neutral"
        )

    @command(description="fun", usage="<member>")
    async def iq(self, ctx: Context, user: Member = Author):
        """
        Check how smart you or another member is.
        """
        await ctx.embed(
            message=f"{user.mention if user is not ctx.author else 'Your'} iq is `{random.randrange(101)}`", 
            message_type="neutral"
        )

    @command(description="fun", usage="<member>")
    async def bitches(self, ctx: Context, user: Member = Author):
        """
        Check how many bitches you or another member has.
        """
        await ctx.embed(
            message=f"{user.mention if user is not ctx.author else 'You'} {'has' if user is not ctx.author else 'have'} `{random.randrange(101)}` bitches", 
            message_type="neutral"
        )

    @group(
        name="vape", 
        invoke_without_command=True, 
        aliases=["hit"]
    )
    @cooldown(1, 3, BucketType.user)
    async def vape(self, ctx: Context):
        has_vape = await self.bot.db.fetchrow(
            """
            SELECT holder, guild_hits 
            FROM vape 
            WHERE guild_id = $1
            """, 
            ctx.guild.id
        )

        if not has_vape:
            return await ctx.embed(
                message="There is no vape in this server!", 
                message_type="warned"
            )

        holder_id = has_vape["holder"]
        if holder_id is None:
            return await ctx.embed(
                message="There is no vape in this server!", 
                message_type="warned"
            )

        if holder_id != ctx.author.id:
            holder = ctx.guild.get_member(holder_id)
            holder_message = (
                f"You don't have the vape! Steal it from **{holder.display_name}**."
                if holder
                else "The vape holder is no longer in this server. Someone else can claim it!"
            )
            return await ctx.embed(
                message=holder_message, 
                message_type="warned"
            )

        message = await ctx.embed(
            message=f"Took a hit of the vape!", 
            message_type="neutral"
        )

        guild_hits = has_vape["guild_hits"] + 1
        await self.bot.db.execute(
            """
            UPDATE vape SET guild_hits = $1 
            WHERE guild_id = $2
            """,
            guild_hits,
            ctx.guild.id,
        )
        await asyncio.sleep(2.3)
        return await ctx.embed(
            message=f"Hit the vape ``{guild_hits}`` times", 
            message_type="neutral",
            edit=message
        )
    
    @vape.command(name="steal", aliases=["claim"])
    @cooldown(1, 7, BucketType.guild)
    async def vape_steal(self, ctx: Context):
        """
        Steal the vape from the current holder.
        """
        record = await self.bot.db.fetchrow(
            """
            SELECT holder 
            FROM vape 
            WHERE guild_id = $1
            """, 
            ctx.guild.id
        )

        if not record:
            await self.bot.db.execute(
                """
                INSERT INTO vape (holder, guild_id, guild_hits) 
                VALUES ($1, $2, 0)
                """,
                ctx.author.id,
                ctx.guild.id,
            )
            return await ctx.embed(
                message="You have claimed the vape",
                message_type="neutral"
            )

        current_holder = ctx.guild.get_member(record["holder"])
        if current_holder == ctx.author:
            return await ctx.embed(
                message="You already have the vape!",
                message_type="warned"
            )

        await self.bot.db.execute(
            """
            UPDATE vape SET holder = $1 
            WHERE guild_id = $2
            """,
            ctx.author.id,
            ctx.guild.id,
        )
        description = (
            f"You have successfully stolen the vape from {current_holder.mention}"
            if current_holder
            else f"You have claimed the vape"
        )
        await ctx.embed(
            message=description,
            message_type="neutral"
        )

    @vape.command(name="flavor", aliases=["taste"])
    async def vape_flavor(self, ctx: Context, flavor: str):
        """
        Choose the flavor of the vape.
        """
        if flavor.capitalize() not in self.flavors:
            return await ctx.embed(
                message=f"Invalid flavor, choose one of {', '.join(self.flavors)}", 
                message_type="warned"
            )

        await self.bot.db.execute(
            """
            INSERT INTO vape_flavors (flavor, user_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET flavor = $1
            """,
            flavor,
            ctx.author.id,
        )
        await ctx.embed(
            message=f"You have chosen the flavor **{flavor}**",
            message_type="neutral"
        )

    @vape.command(name="hits", aliases=["h"])
    async def vape_hits(self, ctx: Context):
        """
        Show how many hits the vape has taken.
        """
        hits = await self.bot.db.fetchval(
            """
            SELECT guild_hits 
            FROM vape 
            WHERE guild_id = $1
            """, 
            ctx.guild.id
        )
        await ctx.embed(
            message=f"The vape has taken **{hits}** hits", 
            message_type="neutral"
        )

    @command(name="caption", aliases=["quote"])
    async def caption(
        self, 
        ctx: Context, 
        message: Optional[Message] = None
    ) -> Message:
        return await self.get_caption(ctx, message)

    @command(aliases=["dih"], usage="pp [user]")
    @cooldown(1, 4, BucketType.guild)
    async def pp(self, ctx: Context, *, user: Member = None):
        """
        Checks how big your or another member's dih is.
        """
        await ctx.embed(
            message=f"{user.mention if user is not ctx.author else 'Your'} dih is `{random.randrange(12)} inches`", 
            message_type="neutral"
        )

    @hybrid_command(description="fun")
    @cooldown(1, 3, BucketType.user)
    async def roast(self, ctx: Context, *, user: Member = Author):
        """
        Roast another member or yourself.
        """
        embed = Embed(description=f"{user.mention}: {random.choice(roasts)}")
        await ctx.send(embed=embed)

    @hybrid_command(aliases=["8ball"], description="fun", usage="<member>")
    @cooldown(1, 3, BucketType.user)
    async def eightball(self, ctx: Context, *, question: str):
        """
        Ask the eightball a question.
        """
        embed = Embed(description=f"**Question:** {question}\n**Answer:** {random.choice(eightball)}")
        await ctx.send(embed=embed)

    @command(aliases=["dom"])
    async def dominant(self, ctx: Context, user: Member = Author):
        """
        Get the dominant color of a user's avatar.
        """
        avatar = user.avatar.with_format("png")
        async with self.bot.session.get(str(avatar)) as resp:
            image = await resp.read()
        
        result = await get_dominant_color(image)
        dominant_color = result["dominant_color"]
        hex_color = "#{:02x}{:02x}{:02x}".format(*dominant_color)
        
        embed = Embed(
            color=discord.Color.from_rgb(*dominant_color),
            description=f"{user.mention}'s dominant color is ``{hex_color}``",
        )
        
        embed.set_thumbnail(url=str(avatar))
        await ctx.send(embed=embed)

    @command()
    async def rotate(self, ctx: Context, angle: int, message: Optional[Message] = None):
        """
        Rotate an image by a specified angle.
        """
        if not message:
            msg = ctx.message.reference
            if not msg:
                return await ctx.embed(
                    message="No message or reference provided!", 
                    message_type="warned"
                )
            
            message = await ctx.fetch_message(msg.message_id)

        if not message.attachments:
            return await ctx.embed(
                message="No media found in the message!", 
                message_type="warned"
            )

        url = message.attachments[0].url
        async with self.bot.session.get(url) as resp:
            image = await resp.read()

        rotated_image_bytes = await rotate_image(image, angle)
        buffer = BytesIO(rotated_image_bytes)
        buffer.seek(0)
        await ctx.send(file=discord.File(buffer, filename="rotated.png"))
        buffer.close()

    @command()
    async def compress(self, ctx: Context, message: Optional[Message] = None, quality: int = 10):
        """
        Compress an image to reduce its size.
        """
        if not message:
            msg = ctx.message.reference
            if not msg:
                return await ctx.send("No message or reference provided")
            message = await ctx.fetch_message(msg.message_id)

        if not message.attachments:
            return await ctx.send("No media found in the message")

        url = message.attachments[0].url
        async with self.bot.session.get(url) as resp:
            image = await resp.read()

        compressed_image = await compress_image(image, quality)
        buffer = BytesIO(compressed_image)
        buffer.seek(0)
        await ctx.send(file=discord.File(buffer, filename="compressed.jpg"))
        buffer.close()

    @command()
    async def quickpoll(self, ctx: Context, *, question: str):
        """
        Create a quick poll with a question.
        """
        embed = Embed(description=question)
        embed.set_footer(text=f"Poll created by {ctx.author}")
        message = await ctx.send(embed=embed)
        await message.add_reaction(f"{EMOJIS['UB_Check_Icon']}")
        await message.add_reaction(f"{EMOJIS['UB_X_Icon']}")

    @command(liases=["rhex"])
    async def randomhex(self, ctx: Context):
        """
        Get a random hex color.
        """
        color = random.randint(0, 0xFFFFFF)
        hex_color = f"#{color:06x}"
        return await ColorInfo().convert(ctx, hex_color)

    @command()
    async def rps(self, ctx: Context, choice: Literal["rock", "paper", "scissors"]):
        """
        Play rock, paper, scissors against the bot.
        """
        if choice not in ["rock", "paper", "scissors"]:
            return await ctx.embed(
                message="Invalid choice! Please choose rock, paper, or scissors.",
                message_type="warned",
            )
        
        bot_choice = random.choice(["rock", "paper", "scissors"])
        if choice == bot_choice:
            return await ctx.embed(
                message=f"You chose ``{choice}`` and I chose ``{bot_choice}``. **It's a tie!**",
                message_type="neutral",
            )
        
        if (
            (choice == "rock" and bot_choice == "scissors")
            or (choice == "paper" and bot_choice == "rock")
            or (choice == "scissors" and bot_choice == "paper")
        ):
            return await ctx.embed(
                message=f"You chose ``{choice}`` and I chose ``{bot_choice}``. **You win!**",
                message_type="neutral",
            )

        return await ctx.embed(
            message=f"You chose ``{choice}`` and I chose ``{bot_choice}``. **I win!**",
            message_type="neutral",
        )

    @command(aliases=["pick"])
    async def choose(self, ctx: Context, *, options: str):
        """
        Choose between multiple options.
        """
        choices = options.split(",")
        choice = random.choice(choices)
        return await ctx.embed(
            message=f"I choose: ``{choice.strip()}``",
            message_type="neutral",
        )

    @command(
        name="wyr",
        brief="Play a game of Would You Rather",
        aliases=["wouldyourather"],
    )
    async def wyr(self, ctx: Context):
        url = "https://would-you-rather.p.rapidapi.com/wyr/random"
        headers = {
            "x-rapidapi-key": "dd42e94a21msh04bda572c6da553p127a95jsnf367d0e280bb",
            "x-rapidapi-host": "would-you-rather.p.rapidapi.com",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    question = data[0].get("question", "No question available.")
                else:
                    question = "Sorry, couldn't fetch a question at the moment."

        embed = Embed(
            description=question,
            color=Colors().information,
        )
        await ctx.send(embed=embed)

    @command(
        name="nword",
        aliases=["nw"],
        help="Shows how many times you've said the n-word and hard r",
    )
    async def nword_count(self, ctx: Context, member: Member = Author):
        """
        Show how many times the user has said the n-word.
        """
        result = await self.bot.db.fetchrow(
                """
                SELECT general_count, hard_r_count 
                FROM offensive 
                WHERE user_id = $1
                """,
                member.id,
            )

        general_count = result["general_count"] if result else 0
        hard_r_count = result["hard_r_count"] if result else 0
        leaderboard = await self.bot.db.fetch(
                """
                SELECT user_id, general_count 
                FROM offensive ORDER BY general_count DESC
                """,
                member.id
            )

        sorted_leaderboard = sorted(leaderboard, key=lambda x: x["general_count"], reverse=True)

        user_position = None
        for index, entry in enumerate(sorted_leaderboard):
                if entry["user_id"] == member.id:
                    user_position = index + 1
                    break

        if user_position is None:
                user_position = "N/A"

        random_message = f"-# {random.choice(nword)}"

        embed = Embed(
                description=(
                    f"{ctx.author.mention} has said the n-word **{general_count}** times\n"
                    f"{ctx.author.mention} has also said the forbidden word **{hard_r_count}** times\n"
                    f"{random_message}"
                ),
            )

        embed.set_author(
                name=f"{ctx.author.name} - is not black",
                icon_url=ctx.author.display_avatar.url
            )
        embed.set_footer(
            text=f"You are #{user_position} on the leaderboard"
            if member == ctx.author
            else f"{member.name} is #{user_position} on the leaderboard"
        )
        await ctx.send(embed=embed)

    @command(
        name="nwordlb",
        aliases=["nwlb"],
        help="Shows the leaderboard of how many times users have said the n-word",
    )
    async def nword_leaderboard(self, ctx: Context):
        """
        Display a paginated leaderboard for users' n-word counts.
        """
        record = await self.bot.db.fetch(
            """
            SELECT user_id, general_count 
            FROM offensive ORDER BY general_count DESC
            """
        )
        if not record:
            return await ctx.embed(
                message="Leaderboard is empty!", 
                message_type="warned"
            )

        sorted_record = sorted(record, key=lambda x: x["general_count"], reverse=True)

        embed = Embed(title="N-Word Leaderboard")

        for index, entry in enumerate(sorted_record, start=1):
            user = await self.bot.fetch_user(entry["user_id"])
            embed.add_field(
                name=f"#{index}",
                value=f"{user.mention} - {entry['general_count']}",
                inline=False,
            )

        return await ctx.paginate(entries=record, embed=embed)

    @command(aliases=["ttt"])
    async def tictactoe(self, ctx: Context, opponent: Member):
        """
        Play Tic Tac Toe against another member.
        """
        if opponent.bot or opponent == ctx.author:
            return await ctx.embed(message="You can't play against a bot!", message_type="warned")

        view = TicTacToe(ctx.author, opponent)
        await ctx.send(
            f"Tic Tac Toe: {ctx.author.mention} vs {opponent.mention}", view=view
        )

    @command(name="image", aliases=["img"])
    @cooldown(1, 5, BucketType.user)
    async def image(self, ctx: Context, *, query: str):
        """
        Search for images using Bing's Custom Search API with button-based navigation.
        """

        try:
            results = await self.bing.image_search(
                query=query, safe=not ctx.channel.is_nsfw(), pages=2
            )
            embeds = []
            for i, result in enumerate(results.results, start=1):
                embed = Embed(
                    title=f"Image Results for {query}", color=Colors().information
                )
                embed.set_image(url=result.image or result.thumbnail)
                embed.set_footer(text=f"Page {i}/{len(results.results)}")
                embeds.append(embed)

            return await ctx.alternative_paginate(embeds)

        except Exception as e:
            if ctx.author.name == "aiohttp":
                raise e
            return await ctx.embed(message=f"No results found for query `{query[:50]}`", message_type="warned")

    # @command(name="image")
    # @cooldown(1, 5, BucketType.user)
    async def old_image(self, ctx: Context, *, query: str):
        """Search for images using Google's Custom Search JSON API with button-based navigation."""

        try:
            is_donator = await self.bot.db.fetchrow(
                """SELECT * FROM boosters WHERE user_id = $1""", ctx.author.id
            )
        except Exception as e:
            return await ctx.embed(
                message=f"An error occurred while checking donator status: {e}",
                message_type="warned"
            )

        try:
            service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)

            embeds = []
            items_collected = 0
            start_index = 1

            while items_collected < 100:
                result = (
                    service.cse()
                    .list(
                        q=query,
                        cx=SEARCH_ENGINE_ID,
                        searchType="image",
                        safe="active",
                        num=10,
                        start=start_index,
                    )
                    .execute()
                )

                items = result.get("items", [])
                if not items:
                    break

                for index, item in enumerate(items, start=items_collected + 1):
                    image_url = item.get("link")
                    embed = Embed(color=Colors().information)
                    embed.set_image(url=image_url)
                    embed.set_footer(text="Images provided by Greed")
                    embeds.append(embed)

                items_collected += len(items)
                start_index += 10

                if len(items) < 10:
                    break

            if not embeds:
                return await ctx.embed(message="No images found for your query.", message_type="warned")

            for idx, embed in enumerate(embeds):
                embed.description = f"<:Google:1315861928538800189> **Search results for: {query}**\nPage {idx + 1}/{len(embeds)}"

            view = ImagePaginationView(ctx.author, embeds)
            await ctx.send(embed=embeds[0], view=view)

        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @group(invoke_without_command=True)
    async def diary(self, ctx: Context):
        """Show diary commands."""
        return await ctx.send_help(ctx.command)

    @diary.command(
        name="create", aliases=["add"], description="Create a diary entry for today."
    )
    async def diary_create(self, ctx: Context):
        now = datetime.now()
        date = f"{now.month}/{now.day}/{str(now.year)[2:]}"

        check = await self.bot.db.fetchrow(
            "SELECT * FROM diary WHERE user_id = $1 AND date = $2", ctx.author.id, date
        )
        if check:
            return await ctx.send(
                "You already have a diary page for today! Please come back tomorrow or delete the existing entry."
            )

        embed = Embed(
            color=Colors().information,
            description=f"{self.book} Press the button below to create your diary entry.",
        )
        button = Button(
            emoji=self.pen, label="Create Entry", style=ButtonStyle.grey
        )

        async def button_callback(interaction: Interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message(
                    "You are not the author of this command!", ephemeral=True
                )
            modal = DiaryModal()
            await interaction.response.send_modal(modal)

        button.callback = button_callback
        view = View()
        view.add_item(button)
        await ctx.send(embed=embed, view=view)

    @diary.command(name="view", description="View your diary entries.")
    async def diary_view(self, ctx: Context):
        results = await self.bot.db.fetch(
            "SELECT * FROM diary WHERE user_id = $1", ctx.author.id
        )
        if not results:
            return await ctx.embed(message="You don't have any diary entries!", message_type="warned")

        embeds = [
            Embed(
                color=Colors().information, title=entry["title"], description=entry["text"]
            )
            .set_author(name=f"Diary for {entry['date']}")
            .set_footer(text=f"{i + 1}/{len(results)}")
            for i, entry in enumerate(results)
        ]
        return await ctx.paginate(embeds)

    @diary.command(name="delete", description="Delete a diary entry.")
    async def diary_delete(self, ctx: Context):
        results = await self.bot.db.fetch(
            "SELECT * FROM diary WHERE user_id = $1", ctx.author.id
        )
        if not results:
            return await ctx.embed(message="You don't have any diary entries to delete!", message_type="warned")

        options = [
            discord.SelectOption(
                label=f"Diary {i + 1} - {entry['date']}", value=entry["date"]
            )
            for i, entry in enumerate(results)
        ]
        embed = Embed(
            color=Colors().information,
            description="Select a diary entry to delete from the dropdown menu below.",
        )
        select = Select(placeholder="Select a diary entry to delete", options=options)

        async def select_callback(interaction: Interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message(
                    "You are not the author of this command!", ephemeral=True
                )

            selected_date = select.values[0]
            await self.bot.db.execute(
                "DELETE FROM diary WHERE user_id = $1 AND date = $2",
                ctx.author.id,
                selected_date,
            )
            await interaction.response.send_message(
                "Diary entry deleted!", ephemeral=True
            )

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await ctx.send(embed=embed, view=view)

    @command()
    @cooldown(1, 5, BucketType.user)
    async def ship(self, ctx: Context, user1: User = None, user2: User = None):
        """
        Ship two users (or the author and another user if only one is provided).
        """
        if user1 is None and user2 is None:
            await ctx.embed(message="Please mention at least one user to ship!", message_type="warned")
            return

        if user1 and not user2:
            user2 = user1
            user1 = ctx.author
        elif not user1 and user2:
            user1 = ctx.author

        avatar1_url = user1.avatar.url if user1.avatar else user1.default_avatar.url
        avatar2_url = user2.avatar.url if user2.avatar else user2.default_avatar.url

        avatar1, avatar2 = await asyncio.gather(
            fetch_avatar(avatar1_url), fetch_avatar(avatar2_url)
        )

        compatibility = random.randint(1, 100)
        if compatibility <= 24:
            compatibility_message = "Looks like these two aren't compatible."
        elif 25 <= compatibility <= 49:
            compatibility_message = "These two might work something out..."
        elif 50 <= compatibility <= 74:
            compatibility_message = "These two might just be compatible!"
        else:
            compatibility_message = "These two are a perfect match!"

        image_bytes = await ship_img(avatar1, avatar2, compatibility)

        file = File(io.BytesIO(image_bytes), filename="ship.png")
        await ctx.send(
            content=f"{compatibility_message} **(Compatibility: {compatibility}%)**",
            file=file,
        )

    @command(name="poll", brief="Create a poll with multiple options")
    async def poll(self, ctx: Context, time: str, *, question: str):
        """
        Create a poll with multiple options.
        """
        from humanfriendly import parse_timespan

        t = parse_timespan(time)
        if t is None:
            return await ctx.embed(message="Invalid time format. Example: `1h`, `30m`, `1d`", message_type="warned")

        embed = Embed(
            title=f"{ctx.author} asked",
            description=question,
            color=Colors().information,
        )
        embed.set_footer(text=f"Poll created by {ctx.author}")
        message = await ctx.send(embed=embed)

        emojis = ["👍", "👎"]
        await asyncio.gather(*[message.add_reaction(emoji) for emoji in emojis])

        votes = {}

        def check(reaction, user):
            return (
                user != self.bot.user
                and reaction.message.id == message.id
                and user != user.bot
            )

        try:
            while True:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=t, check=check
                )
                if user.id not in votes:
                    votes[user.id] = reaction.emoji
                else:
                    await reaction.remove(user)

        except asyncio.TimeoutError:
            message = await ctx.channel.fetch_message(message.id)
            if not message:
                return

            final_counts = {emoji: 0 for emoji in emojis}
            for user_id, emoji in votes.items():
                final_counts[emoji] += 1

            embed = Embed(
                title=f"Poll Results: {question}",
                color=Colors().information,
            )
            for emoji, count in final_counts.items():
                embed.add_field(name=emoji, value=count)
            await message.reply(embed=embed)

    @hybrid_group(name="modify")
    async def modify(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @modify.command(name="bayer", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_bayer(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a Bayer matrix dithering effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.bayer(url)
                await ctx.send(file=File(BytesIO(buffer), "bayer.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @modify.command(name="emojify", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_emojify(self, ctx: Context, attachment: Optional[str] = None):
        """
        Convert image into emoji pixels
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.emojify(url)
                await ctx.send(file=File(BytesIO(buffer), "emojify.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="gameboy", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_gameboy(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a Gameboy-style effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.gameboy(url)
                await ctx.send(file=File(BytesIO(buffer), "gameboy.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="half_invert", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_half_invert(self, ctx: Context, attachment: Optional[str] = None):
        """
        Invert half of the image
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.half_invert(url)
                await ctx.send(file=File(BytesIO(buffer), "half_invert.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="letters", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_letters(self, ctx: Context, attachment: Optional[str] = None):
        """
        Convert image into ASCII letters
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.letters(url)
                await ctx.send(file=File(BytesIO(buffer), "letters.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="lines", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_lines(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a lined pattern effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.lines(url)
                await ctx.send(file=File(BytesIO(buffer), "lines.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="lsd", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_lsd(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a psychedelic color effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.lsd(url)
                await ctx.send(file=File(BytesIO(buffer), "lsd.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="matrix", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_matrix(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a Matrix-style effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.matrix(url)
                await ctx.send(file=File(BytesIO(buffer), "matrix.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="minecraft", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_minecraft(self, ctx: Context, attachment: Optional[str] = None):
        """
        Convert image into Minecraft blocks
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.minecraft(url)
                await ctx.send(file=File(BytesIO(buffer), "minecraft.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="neon", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_neon(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add neon glow effects
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.neon(url)
                await ctx.send(file=File(BytesIO(buffer), "neon.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="optics", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_optics(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply an optical distortion effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.optics(url)
                await ctx.send(file=File(BytesIO(buffer), "optics.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="pattern", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_pattern(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a repeating pattern from the image
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.pattern(url)
                await ctx.send(file=File(BytesIO(buffer), "pattern.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="sensitive", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_sensitive(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a sensitive content warning overlay
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.sensitive(url)
                await ctx.send(file=File(BytesIO(buffer), "sensitive.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="stereo", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def modify_stereo(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a stereoscopic 3D effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.stereo(url)
                await ctx.send(file=File(BytesIO(buffer), "stereo.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @hybrid_group(name="animate")
    async def animate(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @animate.command(name="shine", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_shine(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a shining animation effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.shine(url)
                await ctx.send(file=File(BytesIO(buffer), "shine.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="shock", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_shock(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add an electric shock effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.shock(url)
                await ctx.send(file=File(BytesIO(buffer), "shock.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="shoot", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_shoot(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add shooting star effects
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.shoot(url)
                await ctx.send(file=File(BytesIO(buffer), "shoot.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="ripple", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_ripple(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a ripple animation effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.ripple(url)
                await ctx.send(file=File(BytesIO(buffer), "ripple.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="roll", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_roll(self, ctx: Context, attachment: Optional[str] = None):
        """
        Make the image roll like a barrel
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.roll(url)
                await ctx.send(file=File(BytesIO(buffer), "roll.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="fan", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_fan(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a fan blade spinning effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.fan(url)
                await ctx.send(file=File(BytesIO(buffer), "fan.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="fire", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_fire(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add animated fire effects
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.fire(url)
                await ctx.send(file=File(BytesIO(buffer), "fire.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="hearts", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_hearts(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add floating heart animations
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.hearts(url)
                await ctx.send(file=File(BytesIO(buffer), "hearts.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="boil", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_boil(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a boiling/bubbling effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.boil(url)
                await ctx.send(file=File(BytesIO(buffer), "boil.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="bomb", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_bomb(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add an explosion animation
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.bomb(url)
                await ctx.send(file=File(BytesIO(buffer), "bomb.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="3d", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_3d(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a 3D depth animation
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.three_d(url)
                await ctx.send(file=File(BytesIO(buffer), "3d.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="earthquake", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_earthquake(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a shaking earthquake effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.earthquake(url)
                await ctx.send(file=File(BytesIO(buffer), "earthquake.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="glitch", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_glitch(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add glitch/corruption effects
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.glitch(url)
                await ctx.send(file=File(BytesIO(buffer), "glitch.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="heart", example="https://example.com/image.jpg https://example.com/image2.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_heart(self, ctx: Context, url1: Optional[str] = None, url2: Optional[str] = None):
        """
        Create a heart locket animation with two images
        """
        async with ctx.typing():
            image1 = url1 or await self._get_media_url(ctx, None, accept_image=True) or ctx.author.display_avatar.url
            image2 = url2 or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.heart_locket(image1, image2)
                await ctx.send(file=File(BytesIO(buffer), "heart.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="magik", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_magik(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a liquid distortion animation
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.liquefy(url)
                await ctx.send(file=File(BytesIO(buffer), "magik.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="patpat", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_patpat(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a headpat animation
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.patpat(url)
                await ctx.send(file=File(BytesIO(buffer), "patpat.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="rain", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_rain(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add falling rain effects
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.rain(url)
                await ctx.send(file=File(BytesIO(buffer), "rain.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="triggered", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_triggered(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a triggered meme effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.earthquake(url)
                await ctx.send(file=File(BytesIO(buffer), "triggered.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="wasted", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_wasted(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a GTA wasted screen effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.explicit(url)
                await ctx.send(file=File(BytesIO(buffer), "wasted.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="spin", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_spin(self, ctx: Context, attachment: Optional[str] = None):
        """
        Make the image spin in circles
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.spin(url)
                await ctx.send(file=File(BytesIO(buffer), "spin.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="wave", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_wave(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a waving animation effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.wave(url)
                await ctx.send(file=File(BytesIO(buffer), "wave.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @animate.command(name="wiggle", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def animate_wiggle(self, ctx: Context, attachment: Optional[str] = None):
        """
        Make the image wiggle back and forth
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.wiggle(url)
                await ctx.send(file=File(BytesIO(buffer), "wiggle.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @hybrid_group(name="distort")
    async def distort(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @distort.command(name="burn", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def distort_burn(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a burning distortion effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.burn(url)
                await ctx.send(file=File(BytesIO(buffer), "burn.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="dizzy", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def distort_dizzy(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a dizzying spiral distortion effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.dizzy(url)
                await ctx.send(file=File(BytesIO(buffer), "dizzy.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="endless", example="https://example.com/image.jpg")
    @max_concurrency(1, BucketType.member)
    async def distort_endless(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create an endless looping distortion
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.endless(url)
                await ctx.send(file=File(BytesIO(buffer), "endless.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="infinity")
    @max_concurrency(1, BucketType.member)
    async def distort_infinity(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply an infinity mirror effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.infinity(url)
                await ctx.send(file=File(BytesIO(buffer), "infinity.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="melt")
    @max_concurrency(1, BucketType.member)
    async def distort_melt(self, ctx: Context, attachment: Optional[str] = None):
        """
        Make the image appear to melt
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.melt(url)
                await ctx.send(file=File(BytesIO(buffer), "melt.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="phase")
    @max_concurrency(1, BucketType.member)
    async def distort_phase(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a phasing distortion effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.phase(url)
                await ctx.send(file=File(BytesIO(buffer), "phase.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="poly")
    @max_concurrency(1, BucketType.member)
    async def distort_poly(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a polygonal distortion pattern
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.poly(url)
                await ctx.send(file=File(BytesIO(buffer), "poly.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="pyramid")
    @max_concurrency(1, BucketType.member)
    async def distort_pyramid(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a pyramid-like distortion effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.pyramid(url)
                await ctx.send(file=File(BytesIO(buffer), "pyramid.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="shear")
    @max_concurrency(1, BucketType.member)
    async def distort_shear(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a shearing distortion effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.shear(url)
                await ctx.send(file=File(BytesIO(buffer), "shear.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="shred")
    @max_concurrency(1, BucketType.member)
    async def distort_shred(self, ctx: Context, attachment: Optional[str] = None):
        """
        Shred the image into strips
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.shred(url)
                await ctx.send(file=File(BytesIO(buffer), "shred.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="slice")
    @max_concurrency(1, BucketType.member)
    async def distort_slice(self, ctx: Context, attachment: Optional[str] = None):
        """
        Slice the image into segments
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.slice(url)
                await ctx.send(file=File(BytesIO(buffer), "slice.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @distort.command(name="stretch")
    @max_concurrency(1, BucketType.member)
    async def distort_stretch(self, ctx: Context, attachment: Optional[str] = None):
        """
        Apply a stretching distortion effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.stretch(url)
                await ctx.send(file=File(BytesIO(buffer), "stretch.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @group(name="modify")
    async def modify(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @modify.command(name="ads")
    @max_concurrency(1, BucketType.member)
    async def modify_ads(self, ctx: Context, attachment: Optional[str] = None):
        """
        modify image into an advertisement style
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.ads(url)
                await ctx.send(file=File(BytesIO(buffer), "ads.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="bevel")
    @max_concurrency(1, BucketType.member)
    async def modify_bevel(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a beveled edge effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.bevel(url)
                await ctx.send(file=File(BytesIO(buffer), "bevel.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="billboard")
    @max_concurrency(1, BucketType.member)
    async def modify_billboard(self, ctx: Context, attachment: Optional[str] = None):
        """
        Display image on a billboard
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.billboard(url)
                await ctx.send(file=File(BytesIO(buffer), "billboard.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="cube")
    @max_concurrency(1, BucketType.member)
    async def modify_cube(self, ctx: Context, attachment: Optional[str] = None):
        """
        Wrap image around a 3D cube
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.cube(url)
                await ctx.send(file=File(BytesIO(buffer), "cube.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="flag2")
    @max_concurrency(1, BucketType.member)
    async def modify_flag2(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create a waving flag effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.flag(url)
                await ctx.send(file=File(BytesIO(buffer), "flag.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="soap")
    @max_concurrency(1, BucketType.member)
    async def modify_soap(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a soap bubble effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.soap(url)
                await ctx.send(file=File(BytesIO(buffer), "soap.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="tiles")
    @max_concurrency(1, BucketType.member)
    async def modify_tiles(self, ctx: Context, attachment: Optional[str] = None):
        """
        Split image into rotating tiles
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.tiles(url)
                await ctx.send(file=File(BytesIO(buffer), "tiles.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="tv")
    @max_concurrency(1, BucketType.member)
    async def modify_tv(self, ctx: Context, attachment: Optional[str] = None):
        """
        Display image on a TV screen
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.tv(url)
                await ctx.send(file=File(BytesIO(buffer), "tv.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @modify.command(name="wall")
    @max_concurrency(1, BucketType.member)
    async def modify_wall(self, ctx: Context, attachment: Optional[str] = None):
        """
        Project image onto a wall
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.wall(url)
                await ctx.send(file=File(BytesIO(buffer), "wall.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @hybrid_group(name="scene")
    async def scene(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @scene.command(name="ace")
    @max_concurrency(1, BucketType.member)
    async def scene_ace(
        self, 
        ctx: Context,
        side: str,
        *, 
        text: str
    ):
        """
        Create an Ace Attorney text bubble.
        """
        
        side = side.lower()
        if side not in ["attorney", "prosecutor"]:
            return await ctx.embed("Side must be either `attorney` or `prosecutor`", "warned")

        async with ctx.typing():
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.ace(ctx.author.name, side, text)
                await ctx.send(file=File(BytesIO(buffer), "ace.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @scene.command(name="scrapbook")
    @max_concurrency(1, BucketType.member)
    async def scene_scrapbook(self, ctx: Context, *, text: str):
        async with ctx.typing():
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.scrapbook(text)
                await ctx.send(file=File(BytesIO(buffer), "scrapbook.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @group(name="render")
    async def render(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @render.command(name="cartoon")
    @max_concurrency(1, BucketType.member)
    async def render_cartoon(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a cartoon style effect.
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.cartoon(url)
                await ctx.send(file=File(BytesIO(buffer), "cartoon.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="cinema")
    @max_concurrency(1, BucketType.member)
    async def render_cinema(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a cinema style effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.cinema(url)
                await ctx.send(file=File(BytesIO(buffer), "cinema.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="console")
    @max_concurrency(1, BucketType.member)
    async def render_console(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a console style effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.console(url)
                await ctx.send(file=File(BytesIO(buffer), "console.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="contour")
    @max_concurrency(1, BucketType.member)
    async def render_contour(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a contour effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.contour(url)
                await ctx.send(file=File(BytesIO(buffer), "contour.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="dither")
    @max_concurrency(1, BucketType.member)
    async def render_dither(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a dither effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.dither(url)
                await ctx.send(file=File(BytesIO(buffer), "dither.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="emojify")
    @max_concurrency(1, BucketType.member)
    async def render_emojify(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add an emojify effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.emojify(url)
                await ctx.send(file=File(BytesIO(buffer), "emojify.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="gameboy")
    @max_concurrency(1, BucketType.member)
    async def render_gameboy(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a Gameboy style effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.gameboy(url)
                await ctx.send(file=File(BytesIO(buffer), "gameboy.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="halfinvert")
    @max_concurrency(1, BucketType.member)
    async def render_halfinvert(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a half invert effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.half_invert(url)
                await ctx.send(file=File(BytesIO(buffer), "halfinvert.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="knit")
    @max_concurrency(1, BucketType.member)
    async def render_knit(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a knit effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.knit(url)
                await ctx.send(file=File(BytesIO(buffer), "knit.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="letters")
    @max_concurrency(1, BucketType.member)
    async def render_letters(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a letters effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.letters(url)
                await ctx.send(file=File(BytesIO(buffer), "letters.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="lines")
    @max_concurrency(1, BucketType.member)
    async def render_lines(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a lines effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.lines(url)
                await ctx.send(file=File(BytesIO(buffer), "lines.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="lsd")
    @max_concurrency(1, BucketType.member)
    async def render_lsd(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a LSD effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.lsd(url)
                await ctx.send(file=File(BytesIO(buffer), "lsd.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="matrix")
    @max_concurrency(1, BucketType.member)
    async def render_matrix(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a matrix effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.matrix(url)
                await ctx.send(file=File(BytesIO(buffer), "matrix.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="minecraft")
    @max_concurrency(1, BucketType.member)
    async def render_minecraft(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a Minecraft style effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.minecraft(url)
                await ctx.send(file=File(BytesIO(buffer), "minecraft.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="neon")
    @max_concurrency(1, BucketType.member)
    async def render_neon(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a neon effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.neon(url)
                await ctx.send(file=File(BytesIO(buffer), "neon.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="optics")
    @max_concurrency(1, BucketType.member)
    async def render_optics(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add an optics effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.optics(url)
                await ctx.send(file=File(BytesIO(buffer), "optics.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="painting")
    @max_concurrency(1, BucketType.member)
    async def render_painting(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a painting effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.painting(url)
                await ctx.send(file=File(BytesIO(buffer), "painting.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="pattern")
    @max_concurrency(1, BucketType.member)
    async def render_pattern(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a pattern effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.pattern(url)
                await ctx.send(file=File(BytesIO(buffer), "pattern.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @render.command(name="poly")
    @max_concurrency(1, BucketType.member)
    async def render_poly(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add a poly effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.poly(url)
                await ctx.send(file=File(BytesIO(buffer), "poly.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @hybrid_group(name="overlay")
    async def overlay(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @overlay.command(name="blocks")
    @max_concurrency(1, BucketType.member)
    async def overlay_blocks(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add floating blocks overlay
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.blocks(url)
                await ctx.send(file=File(BytesIO(buffer), "blocks.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="cow")
    @max_concurrency(1, BucketType.member)
    async def overlay_cow(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add cow pattern overlay
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.cow(url)
                await ctx.send(file=File(BytesIO(buffer), "cow.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="equations")
    @max_concurrency(1, BucketType.member)
    async def overlay_equations(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add mathematical equations overlay
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.equations(url)
                await ctx.send(file=File(BytesIO(buffer), "equations.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="flush")
    @max_concurrency(1, BucketType.member)
    async def overlay_flush(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add toilet flush effect overlay
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.flush(url)
                await ctx.send(file=File(BytesIO(buffer), "flush.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="gallery")
    @max_concurrency(1, BucketType.member)
    async def overlay_gallery(self, ctx: Context, attachment: Optional[str] = None):
        """
        Display image in an art gallery setting
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.gallery(url)
                await ctx.send(file=File(BytesIO(buffer), "gallery.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="globe")
    @max_concurrency(1, BucketType.member)
    async def overlay_globe(self, ctx: Context, attachment: Optional[str] = None):
        """
        Place image on a rotating globe
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.globe(url)
                await ctx.send(file=File(BytesIO(buffer), "globe.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="ipcam")
    @max_concurrency(1, BucketType.member)
    async def overlay_ipcam(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add security camera overlay effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.ipcam(url)
                await ctx.send(file=File(BytesIO(buffer), "ipcam.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="kanye")
    @max_concurrency(1, BucketType.member)
    async def overlay_kanye(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add Kanye West album cover style
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.kanye(url)
                await ctx.send(file=File(BytesIO(buffer), "kanye.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="lamp")
    @max_concurrency(1, BucketType.member)
    async def overlay_lamp(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add glowing lamp lighting effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.lamp(url)
                await ctx.send(file=File(BytesIO(buffer), "lamp.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="laundry")
    @max_concurrency(1, BucketType.member)
    async def overlay_laundry(self, ctx: Context, attachment: Optional[str] = None):
        """
        Place image in washing machine animation
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.laundry(url)
                await ctx.send(file=File(BytesIO(buffer), "laundry.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="layers")
    @max_concurrency(1, BucketType.member)
    async def overlay_layers(self, ctx: Context, attachment: Optional[str] = None):
        """
        Create layered depth effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.layers(url)
                await ctx.send(file=File(BytesIO(buffer), "layers.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="logoff")
    @max_concurrency(1, BucketType.member)
    async def overlay_logoff(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add Windows logoff screen effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.logoff(url)
                await ctx.send(file=File(BytesIO(buffer), "logoff.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="magnify")
    @max_concurrency(1, BucketType.member)
    async def overlay_magnify(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add magnifying glass effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.magnify(url)
                await ctx.send(file=File(BytesIO(buffer), "magnify.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="paparazzi")
    @max_concurrency(1, BucketType.member)
    async def overlay_paparazzi(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add paparazzi camera effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.paparazzi(url)
                await ctx.send(file=File(BytesIO(buffer), "paparazzi.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="phase")
    @max_concurrency(1, BucketType.member)
    async def overlay_phase(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add phase effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.phase(url)
                await ctx.send(file=File(BytesIO(buffer), "phase.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e, "warned")}")

    @overlay.command(name="phone")
    @max_concurrency(1, BucketType.member)
    async def overlay_phone(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add phone camera effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.phone(url)
                await ctx.send(file=File(BytesIO(buffer), "phone.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @overlay.command(name="plank")
    @max_concurrency(1, BucketType.member)
    async def overlay_plank(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add plank effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.plank(url)
                await ctx.send(file=File(BytesIO(buffer), "plank.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @overlay.command(name="plates")
    @max_concurrency(1, BucketType.member)
    async def overlay_plates(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add plates effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.plates(url)
                await ctx.send(file=File(BytesIO(buffer), "plates.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @overlay.command(name="pyramid")
    @max_concurrency(1, BucketType.member)
    async def overlay_pyramid(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add pyramid effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.pyramid(url)
                await ctx.send(file=File(BytesIO(buffer), "pyramid.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @overlay.command(name="radiate")
    @max_concurrency(1, BucketType.member)
    async def overlay_radiate(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add radiate effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.radiate(url)
                await ctx.send(file=File(BytesIO(buffer), "radiate.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @overlay.command(name="reflection")
    @max_concurrency(1, BucketType.member)
    async def overlay_reflection(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add reflection effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.reflection(url)
                await ctx.send(file=File(BytesIO(buffer), "reflection.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @overlay.command(name="ripped")
    @max_concurrency(1, BucketType.member)
    async def overlay_ripped(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add ripped effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.ripped(url)
                await ctx.send(file=File(BytesIO(buffer), "ripped.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @overlay.command(name="shear")
    @max_concurrency(1, BucketType.member)
    async def overlay_shear(self, ctx: Context, attachment: Optional[str] = None):
        """
        Add shear effect
        """
        async with ctx.typing():
            url = await self._get_media_url(ctx, attachment, accept_image=True) or ctx.author.display_avatar.url
            try:
                jeyy_api = JeyyAPI()
                buffer = await jeyy_api.shear(url)
                await ctx.send(file=File(BytesIO(buffer), "shear.gif"))
            except CommandOnCooldown as e:
                await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")
            except Exception as e:
                await ctx.embed(f"An error occurred: {str(e)}", "warned")

    @command()
    async def achievement(self, ctx: Context, *, text: str):
        """Generate a Minecraft achievement with custom text"""
        if len(text) > 50:
            return await ctx.embed("Text must be 50 characters or less", "warned")

        try:
            buffer = await alexflipnote_api.achievement(text)
            await ctx.send(file=File(BytesIO(buffer), "achievement.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def calling(self, ctx: Context, *, text: str):
        """Generate a 'mom come pick me up im scared' meme"""
        if len(text) > 50:
            return await ctx.embed("Text must be 50 characters or less", "warned")

        try:
            buffer = await alexflipnote_api.calling(text)
            await ctx.send(file=File(BytesIO(buffer), "calling.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def captcha(self, ctx: Context, *, text: str):
        """Generate a custom captcha image"""
        if len(text) > 50:
            return await ctx.embed("Text must be 50 characters or less", "warned")

        try:
            buffer = await alexflipnote_api.captcha(text)
            await ctx.send(file=File(BytesIO(buffer), "captcha.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command(
        name="didyoumean",
        parameters={
            "first": {
                "converter": str,
                "description": "The first text to display",
            },
            "second": {
                "converter": str,
                "description": "The second text to display",
            }
        }
    )
    async def didyoumean(self, ctx: Context, first: str, second: str) -> None:
        """Generate a Google 'did you mean' image
        
        Flags:
        --text: The searched text
        --text2: The 'did you mean' suggestion"""
        try:
            buffer = await alexflipnote_api.didyoumean(first, second)
            await ctx.send(file=File(BytesIO(buffer), "didyoumean.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def supreme(self, ctx: Context, *, text: str):
        """Generate a supreme logo with custom text"""
        if len(text) > 50:
            return await ctx.embed("Text must be 50 characters or less", "warned")

        try:
            buffer = await alexflipnote_api.supreme(text)
            await ctx.send(file=File(BytesIO(buffer), "supreme.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def facts(self, ctx: Context, *, text: str):
        """Generate a 'facts book' meme"""
        if len(text) > 100:
            return await ctx.embed("Text must be 100 characters or less", "warned")

        try:
            buffer = await alexflipnote_api.facts(text)
            await ctx.send(file=File(BytesIO(buffer), "facts.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def drip(self, ctx: Context, member: Member = None):
        """Give someone the drip"""
        member = member or ctx.author
        try:
            buffer = await popcat_api.drip(member.display_avatar.url)
            await ctx.send(file=File(BytesIO(buffer), "drip.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def gun(self, ctx: Context, member: Member = None):
        """Point a gun at someone"""
        member = member or ctx.author
        try:
            buffer = await popcat_api.gun(member.display_avatar.url)
            await ctx.send(file=File(BytesIO(buffer), "gun.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def wanted(self, ctx: Context, member: Member = None):
        """Generate a wanted poster"""
        member = member or ctx.author
        try:
            buffer = await popcat_api.wanted(member.display_avatar.url)
            await ctx.send(file=File(BytesIO(buffer), "wanted.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def alert(self, ctx: Context, *, text: str):
        """Generate an iPhone alert"""
        if len(text) > 100:
            return await ctx.embed("Text must be 100 characters or less", "warned")

        try:
            buffer = await popcat_api.alert(text)
            await ctx.send(file=File(BytesIO(buffer), "alert.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command(
        name="pooh",
        parameters={
            "first": {
                "converter": str,
                "description": "The regular text for normal Pooh",
            },
            "second": {
                "converter": str,
                "description": "The fancy text for fancy Pooh",
            }
        }
    )
    async def pooh(self, ctx: Context, first: str, second: str) -> None:
        """Generate a Tuxedo Pooh meme"""
        try:
            buffer = await popcat_api.pooh(first, second)
            await ctx.send(file=File(BytesIO(buffer), "pooh.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command(
        name="drake",
        parameters={
            "first": {
                "converter": str,
                "description": "The text Drake is rejecting",
            },
            "second": {
                "converter": str,
                "description": "The text Drake is approving",
            }
        }
    )
    async def drake(self, ctx: Context, first: str, second: str) -> None:
        """Generate a Drake meme"""
        try:
            buffer = await popcat_api.drake(first, second)
            await ctx.send(file=File(BytesIO(buffer), "drake.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def oogway(self, ctx: Context, *, text: str):
        """Generate an Oogway quote meme"""
        if len(text) > 100:
            return await ctx.embed("Text must be 100 characters or less", "warned")

        try:
            buffer = await popcat_api.oogway(text)
            await ctx.send(file=File(BytesIO(buffer), "oogway.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command()
    async def sadcat(self, ctx: Context, *, text: str):
        """Generate a sad cat meme"""
        if len(text) > 100:
            return await ctx.embed("Text must be 100 characters or less", "warned")

        try:
            buffer = await popcat_api.sadcat(text)
            await ctx.send(file=File(BytesIO(buffer), "sadcat.png"))
        except CommandOnCooldown as e:
            await ctx.embed(f"This command is on cooldown. Try again in {e.retry_after:.1f}s", "warned")

    @command(aliases=["guessflag", "flagguess"])
    @cooldown(1, 5, BucketType.user)
    async def flag(self, ctx: Context, difficulty: str = "medium") -> Message:
        """
        Play a flag guessing game.
        Difficulty options: easy, medium, hard
        """
        difficulty = difficulty.lower()
        if difficulty not in self.flag_difficulties:
            return await ctx.embed("Invalid difficulty! Choose: `easy`, `medium`, or `hard`", "warned")

        country_code = random.choice(self.flag_difficulties[difficulty])
        flag_path = f"greed/plugins/fun/assets/flags/{country_code}.png"

        country_names = {
            "ad": "Andorra", "ae": "United Arab Emirates", "af": "Afghanistan",
            "ag": "Antigua and Barbuda", "ai": "Anguilla", "al": "Albania",
            "am": "Armenia", "ao": "Angola", "aq": "Antarctica",
            "ar": "Argentina", "as": "American Samoa", "at": "Austria",
            "au": "Australia", "aw": "Aruba", "ax": "Åland Islands",
            "az": "Azerbaijan",
            "ba": "Bosnia and Herzegovina", "bb": "Barbados",
            "bd": "Bangladesh", "be": "Belgium", "bf": "Burkina Faso",
            "bg": "Bulgaria", "bh": "Bahrain", "bi": "Burundi",
            "bj": "Benin", "bl": "Saint Barthélemy", "bm": "Bermuda",
            "bn": "Brunei", "bo": "Bolivia", "bq": "Caribbean Netherlands",
            "br": "Brazil", "bs": "Bahamas", "bt": "Bhutan",
            "bw": "Botswana", "by": "Belarus", "bz": "Belize",
            "ca": "Canada", "cc": "Cocos Islands", "cd": "DR Congo",
            "cf": "Central African Republic", "cg": "Republic of the Congo",
            "ch": "Switzerland", "ci": "Ivory Coast", "ck": "Cook Islands",
            "cl": "Chile", "cm": "Cameroon", "cn": "China",
            "co": "Colombia", "cr": "Costa Rica", "cu": "Cuba",
            "cv": "Cape Verde", "cw": "Curaçao", "cx": "Christmas Island",
            "cy": "Cyprus", "cz": "Czech Republic",
            "de": "Germany", "dj": "Djibouti", "dk": "Denmark",
            "dm": "Dominica", "do": "Dominican Republic", "dz": "Algeria",
            "ec": "Ecuador", "ee": "Estonia", "eg": "Egypt",
            "eh": "Western Sahara", "er": "Eritrea", "es": "Spain",
            "et": "Ethiopia",
            "fi": "Finland", "fj": "Fiji", "fk": "Falkland Islands",
            "fm": "Micronesia", "fo": "Faroe Islands", "fr": "France",
            "ga": "Gabon", "gb": "United Kingdom", "gd": "Grenada",
            "ge": "Georgia", "gf": "French Guiana", "gg": "Guernsey",
            "gh": "Ghana", "gi": "Gibraltar", "gl": "Greenland",
            "gm": "Gambia", "gn": "Guinea", "gp": "Guadeloupe",
            "gq": "Equatorial Guinea", "gr": "Greece",
            "gs": "South Georgia", "gt": "Guatemala", "gu": "Guam",
            "gw": "Guinea-Bissau", "gy": "Guyana",
            "hk": "Hong Kong", "hm": "Heard Island",
            "hn": "Honduras", "hr": "Croatia", "ht": "Haiti",
            "hu": "Hungary",
            "id": "Indonesia", "ie": "Ireland", "il": "Israel",
            "im": "Isle of Man", "in": "India", "io": "British Indian Ocean Territory",
            "iq": "Iraq", "ir": "Iran", "is": "Iceland", "it": "Italy",
            "je": "Jersey", "jm": "Jamaica", "jo": "Jordan", "jp": "Japan",
            "ke": "Kenya", "kg": "Kyrgyzstan", "kh": "Cambodia",
            "ki": "Kiribati", "km": "Comoros", "kn": "Saint Kitts and Nevis",
            "kp": "North Korea", "kr": "South Korea", "kw": "Kuwait",
            "ky": "Cayman Islands", "kz": "Kazakhstan",
            "la": "Laos", "lb": "Lebanon", "lc": "Saint Lucia",
            "li": "Liechtenstein", "lk": "Sri Lanka", "lr": "Liberia",
            "ls": "Lesotho", "lt": "Lithuania", "lu": "Luxembourg",
            "lv": "Latvia", "ly": "Libya",
            "ma": "Morocco", "mc": "Monaco", "md": "Moldova",
            "me": "Montenegro", "mf": "Saint Martin", "mg": "Madagascar",
            "mh": "Marshall Islands", "mk": "North Macedonia",
            "ml": "Mali", "mm": "Myanmar", "mn": "Mongolia",
            "mo": "Macau", "mp": "Northern Mariana Islands",
            "mq": "Martinique", "mr": "Mauritania", "ms": "Montserrat",
            "mt": "Malta", "mu": "Mauritius", "mv": "Maldives",
            "mw": "Malawi", "mx": "Mexico", "my": "Malaysia",
            "mz": "Mozambique",
            "na": "Namibia", "nc": "New Caledonia", "ne": "Niger",
            "nf": "Norfolk Island", "ng": "Nigeria", "ni": "Nicaragua",
            "nl": "Netherlands", "no": "Norway", "np": "Nepal",
            "nr": "Nauru", "nu": "Niue", "nz": "New Zealand",
            "om": "Oman",
            "pa": "Panama", "pe": "Peru", "pf": "French Polynesia",
            "pg": "Papua New Guinea", "ph": "Philippines", "pk": "Pakistan",
            "pl": "Poland", "pm": "Saint Pierre and Miquelon",
            "pn": "Pitcairn Islands", "pr": "Puerto Rico",
            "ps": "Palestine", "pt": "Portugal", "pw": "Palau",
            "py": "Paraguay",
            "qa": "Qatar",
            "re": "Réunion", "ro": "Romania", "rs": "Serbia",
            "ru": "Russia", "rw": "Rwanda",
            "sa": "Saudi Arabia", "sb": "Solomon Islands",
            "sc": "Seychelles", "sd": "Sudan", "se": "Sweden",
            "sg": "Singapore", "sh": "Saint Helena",
            "si": "Slovenia", "sj": "Svalbard and Jan Mayen",
            "sk": "Slovakia", "sl": "Sierra Leone",
            "sm": "San Marino", "sn": "Senegal", "so": "Somalia",
            "sr": "Suriname", "ss": "South Sudan",
            "st": "São Tomé and Príncipe", "sv": "El Salvador",
            "sx": "Sint Maarten", "sy": "Syria", "sz": "Eswatini",
            "tc": "Turks and Caicos Islands", "td": "Chad",
            "tf": "French Southern Territories", "tg": "Togo",
            "th": "Thailand", "tj": "Tajikistan", "tk": "Tokelau",
            "tl": "East Timor", "tm": "Turkmenistan", "tn": "Tunisia",
            "to": "Tonga", "tr": "Turkey", "tt": "Trinidad and Tobago",
            "tv": "Tuvalu", "tw": "Taiwan", "tz": "Tanzania",
            "ua": "Ukraine", "ug": "Uganda", "um": "U.S. Minor Outlying Islands",
            "us": "United States", "uy": "Uruguay", "uz": "Uzbekistan",
            "va": "Vatican City", "vc": "Saint Vincent and the Grenadines",
            "ve": "Venezuela", "vg": "British Virgin Islands",
            "vi": "U.S. Virgin Islands", "vn": "Vietnam", "vu": "Vanuatu",
            "wf": "Wallis and Futuna", "ws": "Samoa",
            "xk": "Kosovo",
            "ye": "Yemen", "yt": "Mayotte",
            "za": "South Africa", "zm": "Zambia", "zw": "Zimbabwe"
        }

        embed = Embed(
            title="Guess the Flag!",
            description=(
                f"**Difficulty**: {difficulty.title()}\n"
                "You have 30 seconds to guess the country.\n"
                "*Type your answer in the chat.*"
            ),
            color=ctx.color
        )
        
        file = File(flag_path, filename="flag.png")
        embed.set_thumbnail(url="attachment://flag.png")
        
        message = await ctx.send(file=file, embed=embed)

        try:
            _ = await self.bot.wait_for(
                "message",
                timeout=30.0,
                check=lambda m: (
                    m.author == ctx.author
                    and m.channel == ctx.channel
                    and (
                        unidecode(m.content.lower().strip()) in [
                            unidecode(country_names[country_code].lower()),
                            country_code.lower()
                        ]
                    )
                )
            )
        except asyncio.TimeoutError:
            embed.description = f"Time's up! The answer was **{country_names[country_code]}**"
            embed.color = discord.Color.red()
            await message.edit(embed=embed)
        else:
            embed.description = f"Correct! The answer was **{country_names[country_code]}**"
            embed.color = discord.Color.green()
            await message.edit(embed=embed)

    @command(aliases=['flaggame'])
    async def flags(self, ctx: Context) -> Optional[Message]:
        """Start a game of Flags."""

        country_names = {
            "ad": "Andorra", "ae": "United Arab Emirates", "af": "Afghanistan",
            "ag": "Antigua and Barbuda", "ai": "Anguilla", "al": "Albania",
            "am": "Armenia", "ao": "Angola", "aq": "Antarctica",
            "ar": "Argentina", "as": "American Samoa", "at": "Austria",
            "au": "Australia", "aw": "Aruba", "ax": "Åland Islands",
            "az": "Azerbaijan",
            "ba": "Bosnia and Herzegovina", "bb": "Barbados",
            "bd": "Bangladesh", "be": "Belgium", "bf": "Burkina Faso",
            "bg": "Bulgaria", "bh": "Bahrain", "bi": "Burundi",
            "bj": "Benin", "bl": "Saint Barthélemy", "bm": "Bermuda",
            "bn": "Brunei", "bo": "Bolivia", "bq": "Caribbean Netherlands",
            "br": "Brazil", "bs": "Bahamas", "bt": "Bhutan",
            "bw": "Botswana", "by": "Belarus", "bz": "Belize",
            "ca": "Canada", "cc": "Cocos Islands", "cd": "DR Congo",
            "cf": "Central African Republic", "cg": "Republic of the Congo",
            "ch": "Switzerland", "ci": "Ivory Coast", "ck": "Cook Islands",
            "cl": "Chile", "cm": "Cameroon", "cn": "China",
            "co": "Colombia", "cr": "Costa Rica", "cu": "Cuba",
            "cv": "Cape Verde", "cw": "Curaçao", "cx": "Christmas Island",
            "cy": "Cyprus", "cz": "Czech Republic",
            "de": "Germany", "dj": "Djibouti", "dk": "Denmark",
            "dm": "Dominica", "do": "Dominican Republic", "dz": "Algeria",
            "ec": "Ecuador", "ee": "Estonia", "eg": "Egypt",
            "eh": "Western Sahara", "er": "Eritrea", "es": "Spain",
            "et": "Ethiopia",
            "fi": "Finland", "fj": "Fiji", "fk": "Falkland Islands",
            "fm": "Micronesia", "fo": "Faroe Islands", "fr": "France",
            "ga": "Gabon", "gb": "United Kingdom", "gd": "Grenada",
            "ge": "Georgia", "gf": "French Guiana", "gg": "Guernsey",
            "gh": "Ghana", "gi": "Gibraltar", "gl": "Greenland",
            "gm": "Gambia", "gn": "Guinea", "gp": "Guadeloupe",
            "gq": "Equatorial Guinea", "gr": "Greece",
            "gs": "South Georgia", "gt": "Guatemala", "gu": "Guam",
            "gw": "Guinea-Bissau", "gy": "Guyana",
            "hk": "Hong Kong", "hm": "Heard Island",
            "hn": "Honduras", "hr": "Croatia", "ht": "Haiti",
            "hu": "Hungary",
            "id": "Indonesia", "ie": "Ireland", "il": "Israel",
            "im": "Isle of Man", "in": "India", "io": "British Indian Ocean Territory",
            "iq": "Iraq", "ir": "Iran", "is": "Iceland", "it": "Italy",
            "je": "Jersey", "jm": "Jamaica", "jo": "Jordan", "jp": "Japan",
            "ke": "Kenya", "kg": "Kyrgyzstan", "kh": "Cambodia",
            "ki": "Kiribati", "km": "Comoros", "kn": "Saint Kitts and Nevis",
            "kp": "North Korea", "kr": "South Korea", "kw": "Kuwait",
            "ky": "Cayman Islands", "kz": "Kazakhstan",
            "la": "Laos", "lb": "Lebanon", "lc": "Saint Lucia",
            "li": "Liechtenstein", "lk": "Sri Lanka", "lr": "Liberia",
            "ls": "Lesotho", "lt": "Lithuania", "lu": "Luxembourg",
            "lv": "Latvia", "ly": "Libya",
            "ma": "Morocco", "mc": "Monaco", "md": "Moldova",
            "me": "Montenegro", "mf": "Saint Martin", "mg": "Madagascar",
            "mh": "Marshall Islands", "mk": "North Macedonia",
            "ml": "Mali", "mm": "Myanmar", "mn": "Mongolia",
            "mo": "Macau", "mp": "Northern Mariana Islands",
            "mq": "Martinique", "mr": "Mauritania", "ms": "Montserrat",
            "mt": "Malta", "mu": "Mauritius", "mv": "Maldives",
            "mw": "Malawi", "mx": "Mexico", "my": "Malaysia",
            "mz": "Mozambique",
            "na": "Namibia", "nc": "New Caledonia", "ne": "Niger",
            "nf": "Norfolk Island", "ng": "Nigeria", "ni": "Nicaragua",
            "nl": "Netherlands", "no": "Norway", "np": "Nepal",
            "nr": "Nauru", "nu": "Niue", "nz": "New Zealand",
            "om": "Oman",
            "pa": "Panama", "pe": "Peru", "pf": "French Polynesia",
            "pg": "Papua New Guinea", "ph": "Philippines", "pk": "Pakistan",
            "pl": "Poland", "pm": "Saint Pierre and Miquelon",
            "pn": "Pitcairn Islands", "pr": "Puerto Rico",
            "ps": "Palestine", "pt": "Portugal", "pw": "Palau",
            "py": "Paraguay",
            "qa": "Qatar",
            "re": "Réunion", "ro": "Romania", "rs": "Serbia",
            "ru": "Russia", "rw": "Rwanda",
            "sa": "Saudi Arabia", "sb": "Solomon Islands",
            "sc": "Seychelles", "sd": "Sudan", "se": "Sweden",
            "sg": "Singapore", "sh": "Saint Helena",
            "si": "Slovenia", "sj": "Svalbard and Jan Mayen",
            "sk": "Slovakia", "sl": "Sierra Leone",
            "sm": "San Marino", "sn": "Senegal", "so": "Somalia",
            "sr": "Suriname", "ss": "South Sudan",
            "st": "São Tomé and Príncipe", "sv": "El Salvador",
            "sx": "Sint Maarten", "sy": "Syria", "sz": "Eswatini",
            "tc": "Turks and Caicos Islands", "td": "Chad",
            "tf": "French Southern Territories", "tg": "Togo",
            "th": "Thailand", "tj": "Tajikistan", "tk": "Tokelau",
            "tl": "East Timor", "tm": "Turkmenistan", "tn": "Tunisia",
            "to": "Tonga", "tr": "Turkey", "tt": "Trinidad and Tobago",
            "tv": "Tuvalu", "tw": "Taiwan", "tz": "Tanzania",
            "ua": "Ukraine", "ug": "Uganda", "um": "U.S. Minor Outlying Islands",
            "us": "United States", "uy": "Uruguay", "uz": "Uzbekistan",
            "va": "Vatican City", "vc": "Saint Vincent and the Grenadines",
            "ve": "Venezuela", "vg": "British Virgin Islands",
            "vi": "U.S. Virgin Islands", "vn": "Vietnam", "vu": "Vanuatu",
            "wf": "Wallis and Futuna", "ws": "Samoa",
            "xk": "Kosovo",
            "ye": "Yemen", "yt": "Mayotte",
            "za": "South Africa", "zm": "Zambia", "zw": "Zimbabwe"
        }
        
        session = await Flags.get(self.bot.redis, ctx.channel.id)
        if session:
            return await ctx.embed("There is already a game in progress.", "warned")

        embed = Embed(
            title="Flags Game",
            description="\n> ".join(
                [
                    "React with `✅` to join the game. The game will start in **30 seconds**",
                    "You'll have **15 seconds** to guess each flag",
                    "Game starts with **easy** flags and gets progressively harder",
                    "Each player has **3 lives**"
                ]
            ),
        )
        message = await ctx.channel.send(embed=embed)

        session = Flags(message_id=message.id, channel_id=ctx.channel.id)
        await session.save(self.bot.redis)
        await message.add_reaction("✅")

        def check(reaction, user):
            return (
                reaction.message.id == message.id 
                and str(reaction.emoji) == "✅"
                and not user.bot
            )

        try:
            while True:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                session = await Flags.get(self.bot.redis, ctx.channel.id)
                if session:
                    session.players[user.id] = 3 
                    await session.save(self.bot.redis)
        except asyncio.TimeoutError:
            pass

        session = await Flags.get(self.bot.redis, ctx.channel.id)
        if not session or len(session.players) < 2:
            await self.bot.redis.delete(Flags.key(ctx.channel.id))
            return await ctx.embed("Not enough players to start the game!", "warned")

        session.waiting = False
        await session.save(self.bot.redis, ex=1800)

        while True:
            for member_id, lives in list(session.players.items()):
                member = ctx.guild.get_member(member_id)
                if not member:
                    if len(session.players) == 1:
                        await session.delete(self.bot.redis)
                        return await ctx.embed("The winner left the server!", "warned")
                    continue

                if len(session.players) == 1:
                    await session.delete(self.bot.redis)
                    return await ctx.embed(f"**{member}** has won the game!", "approved")

                available_flags = [
                    flag for flag in self.flag_difficulties[session.current_difficulty]
                    if flag not in session.used_flags
                ]
                
                if not available_flags:
                    if session.current_difficulty == "easy":
                        session.current_difficulty = "medium"
                    elif session.current_difficulty == "medium":
                        session.current_difficulty = "hard"
                    else:
                        session.used_flags = []  
                    available_flags = self.flag_difficulties[session.current_difficulty]
                
                country_code = choice(available_flags)
                session.used_flags.append(country_code)
                
                if session.current_difficulty == "easy":
                    timeout = 10.0
                elif session.current_difficulty == "medium":
                    timeout = 8.0
                else:
                    timeout = 7.0

                file = File(f"assets/flags/{country_code}.png", filename="flag.png")
                embed = Embed(
                    title=f"Guess the Flag ({session.current_difficulty.title()})",
                    description=f"You have **{int(timeout)} seconds** to guess this flag"
                )
                embed.set_thumbnail(url="attachment://flag.png")
                message = await ctx.send(content=member.mention, file=file, embed=embed)

                start_time = time.time()
                
                while True:
                    remaining_time = timeout - (time.time() - start_time)
                    if remaining_time <= 0:
                        await message.add_reaction("❌")
                        lives = session.players[member_id] - 1
                        if not lives:
                            del session.players[member_id]
                            embed = Embed(description=f"**{member}** has been **eliminated**!\nThe flag was **{country_names[country_code]}**")
                        else:
                            session.players[member_id] = lives
                            embed = Embed(
                                description="\n> ".join([
                                    f"Time's up! The flag was **{country_names[country_code]}**",
                                    f"You have {plural(lives, md='**'):life|lives} remaining"
                                ])
                            )
                        await ctx.send(embed=embed)
                        break

                    try:
                        message_response = await self.bot.wait_for(
                            "message",
                            timeout=remaining_time,
                            check=lambda m: (
                                m.author == member
                                and m.channel == ctx.channel
                            )
                        )
                        
                        if unidecode(message_response.content.lower().strip()) in [
                            unidecode(country_names[country_code].lower()),
                            country_code.lower()
                        ]:
                            await message_response.add_reaction("✅")
                            await session.save(self.bot.redis)
                            break  
                        else:
                            await message_response.add_reaction("❌")
                            continue

                    except asyncio.TimeoutError:
                        continue

                await session.save(self.bot.redis)

    async def _get_media_url(
        self,
        ctx: Context,
        attachment: Optional[str],
        accept_image: bool = False,
        accept_gif: bool = False,
        accept_video: bool = False,
    ) -> Optional[str]:
        """Helper method to get media URL from various sources"""
        if attachment:
            return attachment

        if ctx.message.attachments:
            file = ctx.message.attachments[0]
            if accept_image and file.content_type.startswith("image/"):
                return file.url
            if accept_gif and file.filename.endswith(".gif"):
                return file.url
            if accept_video and file.content_type.startswith("video/"):
                return file.url
            return None

        if ctx.message.reference:
            referenced = await ctx.channel.fetch_message(
                ctx.message.reference.message_id
            )
            if referenced.attachments:
                file = referenced.attachments[0]
                if accept_image and file.content_type.startswith("image/"):
                    return file.url
                if accept_gif and file.filename.endswith(".gif"):
                    return file.url
                if accept_video and file.content_type.startswith("video/"):
                    return file.url
            elif referenced.embeds:
                embed = referenced.embeds[0]
                if embed.image:
                    return embed.image.url
                elif embed.thumbnail:
                    return embed.thumbnail.url

        return None
    
class ImagePaginationView(View):
    def __init__(self, user: Member, embeds: list[Embed]):
        super().__init__(timeout=60)
        self.user = user
        self.embeds = embeds
        self.current_page = 0

    @button(
        label="Previous", style=ButtonStyle.secondary, disabled=True
    )
    async def previous_button(
        self, interaction: Interaction, button: Button
    ):
        """Handles the Previous button click."""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "You cannot control this interaction.", ephemeral=True
            )
            return

        self.current_page -= 1
        self.update_buttons()
        embed = self.embeds[self.current_page]
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="Next", style=ButtonStyle.success)
    async def next_button(
        self, interaction: Interaction, button: Button
    ):
        """
        Handles the Next button click.
        """
        if interaction.user != self.user:
            await interaction.response.send_message(
                "You cannot control this interaction.", 
                ephemeral=True
            )
            return

        self.current_page += 1
        self.update_buttons()
        embed = self.embeds[self.current_page]
        await interaction.response.edit_message(embed=embed, view=self)

    def update_buttons(self):
        """
        Enable or disable buttons based on the current page.
        """
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.embeds) - 1


async def setup(bot: Greed):
    await bot.add_cog(Fun(bot))
