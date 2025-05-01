import asyncio

from discord import Client
from discord.embeds import Embed
from discord.ext.commands import Cog
from system.classes.github import GithubPushEvent

class GitEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @Cog.listener("github_commit")
    async def github_commit(self, data: GithubPushEvent) -> None:
        """
        Event triggered when a new commit is pushed to GitHub. This function pulls the latest commit and announces the update in the #auto-updates channel.

        Args:
            data (GithubPushEvent): The commit data
        """
        process = await asyncio.create_subprocess_shell(
            "git pull"
        )
        stdout, stderr = await process.communicate()

        # Check the return code
        if process.returncode == 0:
            channel = self.bot.get_channel(1362574627246837801)
            if channel != None:
                embed1 = Embed(
                    title="Auto Update",
                    description=f"Successfully updated from commit {data.head_commit.sha}!\nOutput:\n{stdout}",
                    color=0x00ff1f
                )
                await channel.send(embed=embed1)
        else:
            embed2 = Embed(
                title="Auto Update",
                description=f"Failed to update from commit {data.head_commit.sha}, manual update required.\nError:\n{stderr}",
                color=0xff0000
            )
            channel = self.bot.get_channel(1362574627246837801)
            if channel != None:
                await channel.send(embed=embed2)

async def setup(bot: Client):
    await bot.add_cog(GitEvents(bot))
