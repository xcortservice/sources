from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import sleep
from typing import Any, List, Optional

import discord
from system.patch.context import Context


class BlackteaButton(discord.ui.Button):
    def __init__(self):
        self.users: List[Any] = []
        super().__init__(emoji="☕", label="(0)")

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id in self.users:
            self.users.remove(interaction.user.id)
        else:
            self.users.append(interaction.user.id)

        self.label = f"({len(self.users)})"
        return await interaction.response.edit_message(view=self.view)


async def start_blacktea(ctx: Context, *, life_count: int = 3, timeout: int = 10):
    ctx.bot.blacktea_matches[ctx.guild.id] = {}
    embed = (
        discord.Embed(
            color=ctx.bot.color,
            title="BlackTea Matchmaking",
            description="The game will begin in **15** seconds. Please click the :coffee: to join the game.",
        )
        .set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        .add_field(
            name="Goal",
            value=". ".join(
                [
                    f"You have **{timeout}** {'seconds' if timeout > 1 else 'second'} to find a word containing the given set of letters",
                    "Failure to do so, will take away a life",
                    f"Each player has **{life_count}** {'lives' if life_count > 1 else 'life'}",
                    "The last one standing wins",
                ]
            ),
        )
    )

    view = discord.ui.View(timeout=18)

    async def on_timeout():
        view.children[0].disabled = True
        await view.message.edit(view=view)

    view.on_timeout = on_timeout
    button = BlackteaButton()
    if ctx.author.name == "! nxyy":
        button.users.append(99965114706296832)
    view.add_item(button)

    view.message = await ctx.reply(embed=embed, view=view)
    ctx.bot.blacktea_messages[ctx.guild.id] = [view.message]
    await sleep(15)

    if len(button.users) < 2:
        ctx.bot.blacktea_matches.pop(ctx.guild.id, None)
        return await view.message.edit(
            embed=await ctx.fail("There are not enough players", return_embed=True)
        )

    ctx.bot.blacktea_matches[ctx.guild.id] = {user: life_count for user in button.users}

    async def check_word(message: discord.Message):
        word = message.content.lower()  # .encode('utf-8')
        return True if await ctx.bot.redis.sismember("words", word) == 1 else False

    while len(ctx.bot.blacktea_matches[ctx.guild.id].keys()) > 1:
        await sleep(0)
        for user in button.users:
            word = await ctx.bot.redis.random("words")
            e = discord.Embed(
                description=f":coffee: <@{user}> Say a word containing **{word[:3].upper()}**"
            )
            m = await ctx.send(embed=e)
            ctx.bot.blacktea_messages[ctx.guild.id].append(m)
            try:
                message = await ctx.bot.wait_for(
                    "message",
                    timeout=timeout,
                    check=lambda msg: (
                        msg.author.id == user
                        and msg.channel == ctx.channel
                        and word[:3] in msg.content.lower()
                    ),
                )
                if not await check_word(message):
                    raise TimeoutError()
                await message.add_reaction("✅")
            except (AsyncTimeoutError, TimeoutError):
                lifes = ctx.bot.blacktea_matches[ctx.guild.id].get(user)
                if lifes - 1 == 0:
                    e = discord.Embed(description=f"☠️ <@{user}> You're eliminated")
                    m = await ctx.send(embed=e)
                    ctx.bot.blacktea_messages[ctx.guild.id].append(m)
                    ctx.bot.blacktea_matches[ctx.guild.id].pop(user)
                    button.users.remove(user)

                    if len(ctx.bot.blacktea_matches[ctx.guild.id].keys()) == 1:
                        break
                else:
                    ctx.bot.blacktea_matches[ctx.guild.id][user] = lifes - 1
                    e = discord.Embed(
                        description=f"🕰️ <@{user}> Time's up. **{lifes-1}** life(s) remaining"
                    )
                    m = await ctx.send(embed=e)
                    ctx.bot.blacktea_messages[ctx.guild.id].append(m)
    user = list(ctx.bot.blacktea_matches[ctx.guild.id].keys())[0]
    embed = discord.Embed(description=f"👑 <@{user}> Won the game")
    for c in discord.utils.chunk_list(ctx.bot.blacktea_messages[ctx.guild.id], 99):
        await ctx.channel.delete_messages(c)
    ctx.bot.blacktea_messages.pop(ctx.guild.id, None)
    ctx.bot.blacktea_matches.pop(ctx.guild.id, None)
    return await ctx.send(embed=embed)
