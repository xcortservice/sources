import subprocess
from discord import (Client, Embed, File, Interaction, Member, SelectOption, User, ui)
from discord.ext.commands import (Cog, CommandError, Converter, GuildID, group, is_owner)
from jishaku.codeblocks import Codeblock, codeblock_converter
from system.patch.context import Context
from async_timeout import timeout


class Git(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @group(
        name="github",
        description="commands to update bot code",
        aliases=["git", "repo"],
    )
    @is_owner()
    async def github(self, ctx: Context):
        self.hidden = True
        return await ctx.send_help(ctx.command)
    
    @github.command(
        name="pull",
        description="pull latest commits",
        example=",github pull",
        aliases=["pull"],
        hidden=True
    )
    @is_owner()
    async def pull(self, ctx: Context):
        try:
            output = subprocess.check_output(["git", "pull", "origin", "main"])
            await ctx.send(f"output:\n```{output.decode('utf-8')}```")
        except subprocess.CalledProcessError as e:
            await ctx.send(f"Error: {e.output.decode('utf-8')}")

    @github.command(
        name="restart",
        description="restart the bot",
        example=",github restart",
        aliases=["restart"],
        hidden=True
    )
    @is_owner()
    async def restart(self, ctx: Context):
        embed1 = Embed(title="[Manual] Updating...", color=0x797979)
        embed11 = Embed(title="[Manual] Updated!", color=0x00ff41)
        embed2 = Embed(title="[Manual] Restarting...", color=0x797979)
        message = await ctx.send(embed=embed1)
        try: 
            subprocess.check_call(["git", "pull"])
            await message.edit(embed=embed11)
            timeout(3)
            await message.edit(embed=embed2)
            subprocess.check_call(["pm2", "restart", "bot"])
        except subprocess.CalledProcessError:
            await message.edit(embed=Embed(title="[Manual] Failed to update!", color=0xff0000))

    @github.command(
        name="stash",
        description="stash old changes before pulling",
        example=",github stash",
        aliases=["stash"],
        hidden=True
    )
    @is_owner()
    async def stash(self, ctx: Context) -> None:
        embed1 = Embed(title="https://github.com/HonestServices", description="Stashing commits...")
        embed2 = Embed(title="https://github.com/HonestServices", description="Commits stashed!")
        message = await ctx.send(embed=embed1)
        try:
            subprocess.check_call(["git", "stash"])
            await message.edit(embed=embed2)
        except subprocess.CalledProcessError:
            await message.edit(embed=Embed(title="https://github.com/HonestServices", description="Failed to stash commits!"))

async def setup(bot: Client):
    await bot.add_cog(Git(bot))
