import discord
from discord import (app_commands, Embed, ButtonStyle)
from discord.ext.commands import (Cog, hybrid_command)
from discord.ui import (View, Button)
import platform

class Info(Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @hybrid_command(
        name="botinfo",
        aliases=["info", "bi", "about"],
        description="View information about the bot"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
    async def botinfo(self, ctx):
        await ctx.defer()

        total_members = sum(g.member_count for g in self.bot.guilds)
        text_channels = sum(len(g.text_channels) for g in self.bot.guilds)
        voice_channels = sum(len(g.voice_channels) for g in self.bot.guilds)
        category_count = sum(len(g.categories) for g in self.bot.guilds)

        embed = Embed(
            color=self.bot.config['embed_colors']['default'],
        )
        embed.set_author(
            name=f"{self.bot.user.name}",
            icon_url=self.bot.user.display_avatar.url
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        info = f"Premium multi-purpose discord bot made by the [**Honest Team**](https://honest.rocks)\n"
        info += f"Used by **{len([m for m in self.bot.users if not m.bot]):,}** members in **{len(self.bot.guilds):,}** servers on **{self.bot.shard_count or 1}** shards"
        embed.description = info

        members = (
            f"> **Total:** {total_members:,}\n"
            f"> **Human:** {len([m for m in self.bot.users if not m.bot]):,}\n"
            f"> **Bots:** {len([m for m in self.bot.users if m.bot]):,}"
        )
        
        channels = (
            f"> **Text:** {text_channels:,}\n"
            f"> **Voice:** {voice_channels:,}\n"
            f"> **Categories:** {category_count:,}"
        )

        system = (
            f"> **Commands:** {len(self.bot.commands):,}\n"
            f"> **Discord.py:** {discord.__version__}\n"
            f"> **Python:** {platform.python_version()}"
        )

        embed.add_field(name="Members", value=members, inline=True)
        embed.add_field(name="Channels", value=channels, inline=True)
        embed.add_field(name="System", value=system, inline=True)
        view = View()
        view.add_item(Button(
            label="Authorize",
            emoji=await self.bot.emojis.get('pluslogo'),
            url="https://discord.com/oauth2/authorize?client_id=1366081033853862038",
            style=discord.ButtonStyle.link
        ))
        view.add_item(Button(
            label="Support", 
            emoji=await self.bot.emojis.get('blurple_ticket'),
            url="https://honest.rocks/discord",
            style=discord.ButtonStyle.link
        ))
        view.add_item(Button(
            label="Github",
            emoji=await self.bot.emojis.get('github'),
            url="https://github.com/HonestServices",
            style=ButtonStyle.link
        ))

        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Info(bot))