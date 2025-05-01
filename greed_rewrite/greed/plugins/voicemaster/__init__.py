import discord 
from discord.ui import View  
from discord.ext import commands 
from .views import RenameModal, reclaim
from greed.framework import Greed
from discord.ext import tasks
import asyncio
from greed.shared.config import Colors

class VmButtons(View):
    def __init__(self, bot: Greed):
        super().__init__(timeout=None)
        self.bot = bot
        self.value = None

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_lock:1207661056554700810>",
        custom_id="lock_button",
    )
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            embed = discord.Embed(
                description="> You **aren't** connected to a **Voicemaster channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not interaction.user.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            interaction.user.voice.channel.id,
            interaction.guild.id,
        ):
            embed = discord.Embed(
                description="> You **don't own** this **voice channel**", color=0x2D2B31
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.voice.channel.id,
        )
        if channel_id:
            vc = interaction.guild.get_channel(channel_id)
            if vc.overwrites_for(interaction.guild.default_role).connect is False:
                embed = discord.Embed(
                    description="> Your **voice channel** is already **locked**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
            await vc.set_permissions(interaction.guild.default_role, connect=False)
            embed = discord.Embed(
                description="> Your **voice channel** has been **locked**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_unlock:1207661072086073344>",
        custom_id="unlock_button",
    )
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            embed = discord.Embed(
                description="> You **aren't** connected to a **voicemaster channel**"
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not interaction.user.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            interaction.user.voice.channel.id,
            interaction.guild.id,
        ):
            embed = discord.Embed(
                description="> You **don't own** this **voice channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.voice.channel.id,
        )
        if channel_id:
            vc = interaction.guild.get_channel(channel_id)
            if vc.overwrites_for(interaction.guild.default_role).connect is True:
                embed = discord.Embed(
                    description="> Your **voice channel** isn't **locked**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
            await vc.set_permissions(interaction.guild.default_role, connect=True)
            embed = discord.Embed(
                description="> Your **voice channel** has been **unlocked**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_hide:1207661052288827393>",
        custom_id="hide_button",
    )
    async def hide(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.user.voice:
                embed = discord.Embed(
                    description="> You **aren't** connected to a **voicemaster channel**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )

            if not interaction.user.id == await self.bot.db.fetchval(
                """
                SELECT owner_id
                FROM voicemaster_data
                WHERE channel_id = $1
                AND guild_id = $2
                """,
                interaction.user.voice.channel.id,
                interaction.guild.id,
            ):
                embed = discord.Embed(
                    description="> You **don't own** this **voice channel**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )

            channel_id = await self.bot.db.fetchval(
                """
                SELECT channel_id
                FROM voicemaster_data
                WHERE guild_id = $1
                AND owner_id = $2
                AND channel_id = $3
                """,
                interaction.guild.id,
                interaction.user.id,
                interaction.user.voice.channel.id,
            )
            if channel_id:
                vc = interaction.guild.get_channel(channel_id)
                if (
                    vc.overwrites_for(interaction.guild.default_role).view_channel
                    is False
                ):
                    embed = discord.Embed(
                        description="> Your **voice channel** is **already hidden**",
                        color=0x2D2B31,
                    )
                    return await interaction.response.send_message(
                        embed=embed, ephemeral=True
                    )
                await vc.set_permissions(
                    interaction.guild.default_role, view_channel=False
                )
                embed = discord.Embed(
                    description="> Your **voice channel** has been **hidden**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(e)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_view:1207661072929132645>",
        custom_id="reveal_button",
    )
    async def reveal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            embed = discord.Embed(
                description="> You **aren't** connected to a **Voicemaster channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not interaction.user.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            interaction.user.voice.channel.id,
            interaction.guild.id,
        ):
            embed = discord.Embed(
                description="> You **don't own** this **voice channel**", color=0x2D2B31
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.voice.channel.id,
        )
        if channel_id:
            vc = interaction.guild.get_channel(channel_id)
            if vc.overwrites_for(interaction.guild.default_role).view_channel is True:
                embed = discord.Embed(
                    description="> Your **voice channel** isn't **hidden**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
            await vc.set_permissions(interaction.guild.default_role, view_channel=True)
            embed = discord.Embed(
                description="> Your **voice channel** is **no longer hidden**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_rename:1207661067707093003>",
        custom_id="rename_button",
    )
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            embed = discord.Embed(
                description="> You **aren't** connected to a **Voicemaster channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not interaction.user.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            interaction.user.voice.channel.id,
            interaction.guild.id,
        ):
            embed = discord.Embed(
                description="> You **don't own** this **voice channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.voice.channel.id,
        )
        if channel_id:
            await interaction.response.send_modal(RenameModal(self.bot))

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_owner:1207661061264904222>",
        custom_id="claim_button",
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.user.voice:
                embed = discord.Embed(
                    description="> You **aren't** connected to a **Voicemaster channel**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )

            channel_data = await self.bot.db.fetchrow(
                """
                SELECT channel_id, owner_id
                FROM voicemaster_data
                WHERE guild_id = $1
                AND channel_id = $2
                """,
                interaction.guild.id,
                interaction.user.voice.channel.id,
            )

            if not channel_data:
                embed = discord.Embed(
                    description="> You do not **own** the current **voice channel**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )

            channel_id, owner_id = channel_data

            owner = interaction.guild.get_member(owner_id)
            if owner and owner in interaction.user.voice.channel.members:
                embed = discord.Embed(
                    description="> The owner is **still** in the **voice channel**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )

            if owner:
                await reclaim(interaction.user.voice.channel, owner, interaction.user)
            else:
                overwrites = interaction.user.voice.channel.overwrites
                overwrites[interaction.user] = discord.PermissionOverwrite(
                    connect=True,
                    speak=True,
                    stream=True,
                    priority_speaker=True,
                    manage_channels=True,
                )
                await interaction.user.voice.channel.edit(overwrites=overwrites)

            await self.bot.db.execute(
                """
                UPDATE voicemaster_data
                SET owner_id = $1
                WHERE guild_id = $2
                AND channel_id = $3
                """,
                interaction.user.id,
                interaction.guild.id,
                channel_id,
            )
            embed = discord.Embed(
                description="> You are now the **owner** of the **voice channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_add:1207661050951106580>",
        custom_id="increase_button",
    )
    async def increase(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not interaction.user.voice:
            embed = discord.Embed(
                description="> You **aren't** connected to a **voicemaster channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not interaction.user.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            interaction.user.voice.channel.id,
            interaction.guild.id,
        ):
            embed = discord.Embed(
                description="> You **don't own** this **voice channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.voice.channel.id,
        )
        if channel_id:
            vc = interaction.guild.get_channel(channel_id)
            await vc.edit(user_limit=vc.user_limit + 1)
            embed = discord.Embed(
                description=f"> Your **voice channel's user limit** has been **increased** to `{vc.user_limit}`",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_minus:1207661058114715698>",
        custom_id="decrease_button",
    )
    async def decrease(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not interaction.user.voice:
            embed = discord.Embed(
                description="> You **aren't** connected to a **voicemaster channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not interaction.user.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            interaction.user.voice.channel.id,
            interaction.guild.id,
        ):
            embed = discord.Embed(
                description="> You **don't own** this **voice channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.voice.channel.id,
        )
        if channel_id:
            vc = interaction.guild.get_channel(channel_id)
            if vc.user_limit <= 0:
                embed = discord.Embed(
                    description="> Your **voice channel's user limit** is already at its **minimum**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            await vc.edit(user_limit=vc.user_limit - 1)
            embed = discord.Embed(
                description=f"> Your **voice channel's user limit** has been **decreased** to `{vc.user_limit}`",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_trash:1207661070936703007>",
        custom_id="delete_button",
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            embed = discord.Embed(
                description="> You **aren't** connected to a **voicemaster channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not interaction.user.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            interaction.user.voice.channel.id,
            interaction.guild.id,
        ):
            embed = discord.Embed(
                description="> You **don't own** this **voice channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.voice.channel.id,
        )
        if channel_id:
            vc = interaction.guild.get_channel(channel_id)
            await self.bot.db.execute(
                """
                DELETE FROM voicemaster_data
                WHERE channel_id = $1
                """,
                vc.id,
            )
            await vc.delete()
            embed = discord.Embed(
                description="> Your **voice channel** has been **deleted**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        style=discord.ButtonStyle.grey,
        emoji="<:greed_list:1207661055338086440>",
        custom_id="information_button",
    )
    async def information(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not interaction.user.voice:
            embed = discord.Embed(
                description="> You **aren't** connected to a **Voicemaster channel**",
                color=0x2D2B31,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.voice.channel.id,
        )
        if channel_id:
            vc = interaction.guild.get_channel(channel_id)
            owner = await self.bot.db.fetchval(
                """
                SELECT owner_id
                FROM voicemaster_data
                WHERE channel_id = $1
                AND guild_id = $2
                """,
                interaction.user.voice.channel.id,
                interaction.guild.id,
            )
            owner = interaction.guild.get_member(owner)
            embed = discord.Embed(
                description=f""">>> **Bitrate:** {vc.bitrate/1000} KBPS
**Members:** {len(vc.members)}
**Created:** <t:{round(vc.created_at.timestamp())}:D>
**Owner:** {owner.mention}""",
            )
            embed.set_author(name=vc.name, icon_url=owner.display_avatar)
            embed.set_thumbnail(url=owner.display_avatar)
            return await interaction.response.send_message(embed=embed, ephemeral=True)


class Voicemaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vm_cache = {}
        self.inactive_check.start() 

    def cog_unload(self):
        self.inactive_check.cancel()

    async def get_vm_settings(self, guild_id: int):
        """Get cached voicemaster settings for a guild"""
        if guild_id not in self.vm_cache:
            data = await self.bot.db.fetchrow(
                "SELECT * FROM voicemaster WHERE guild_id = $1", guild_id
            )
            self.vm_cache[guild_id] = data
        return self.vm_cache[guild_id]

    @tasks.loop(minutes=5)
    async def inactive_check(self):
        """Check for and clean up inactive voice channels"""
        try:
            channels = await self.bot.db.fetch(
                """
                SELECT channel_id, guild_id, owner_id 
                FROM voicemaster_data
                WHERE temporary = true
                """
            )

            for record in channels:
                channel = self.bot.get_channel(record["channel_id"])
                if channel and len(channel.members) == 0:
                    await self.bot.db.execute(
                        """
                        DELETE FROM voicemaster_data
                        WHERE channel_id = $1
                        """,
                        channel.id,
                    )
                    await channel.delete()
        except Exception as e:
            print(f"Error in inactive check: {e}")

    @commands.group(
        name="voicemaster", aliases=["vm", "vc"], invoke_without_command=True
    )
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def voicemaster(self, ctx):
        """Manage the voicemaster interface configuration"""

        if ctx.subcommand_passed is not None:  
            return
        return await ctx.send_help(ctx.command.qualified_name)

    @voicemaster.command(
        name="setup",
        aliases=["create", "start", "configure"],
        brief="setup a voicemaster configuration",
    )
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def setup(self, ctx, category: discord.CategoryChannel = None):
        data = await self.bot.db.fetch(
            """
            SELECT *
            FROM voicemaster
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )
        if not data:
            category = await ctx.guild.create_category_channel("vm")
            text = await ctx.guild.create_text_channel("menu", category=category)
            await text.set_permissions(
                ctx.guild.default_role,
                overwrite=discord.PermissionOverwrite(
                    send_messages=False, add_reactions=False
                ),
            )
            voice = await ctx.guild.create_voice_channel("create", category=category)

            guild_name = ctx.guild.name
            guild_icon = ctx.guild.icon.url if ctx.guild.icon else None

            embed = discord.Embed(
                title="**Voicemaster Menu**",
                description="""Welcome to the Voicemaster interface! Here you can manage your voice channels with ease. Below are the available options\n\n> **Lock** - Lock your voice channel
> **Unlock** - Unlock your voice channel
> **Hide** - Hide your voice channel
> **Reveal** - Reveal your hidden voice channel
> **Rename** - Rename your voice channel
> **Claim** - Claim an unclaimed voice channel
> **Increase** - Increase the user limit of your voice channel
> **Decrease** - Decrease the user limit of your voice channel
> **Delete** - Delete your voice channel
> **Information** - View information on the current voice channel""",
            )
            embed.set_author(name=guild_name, icon_url=guild_icon)
            embed.set_thumbnail(url=self.bot.user.avatar if ctx.guild.icon else None)

            message = await text.send(embed=embed, view=VmButtons(self.bot))
            await self.bot.db.execute(
                """INSERT INTO voicemaster
                (guild_id, category_id, voicechannel_id, channel_id, message_id)
                VALUES ($1, $2, $3, $4, $5)
                """,
                ctx.guild.id,
                category.id,
                voice.id,
                text.id,
                message.id,
            )
            await ctx.embed("**Voicemaster interface** has been **setup.**", "approved")
        else:
            await ctx.embed(
                "**Voicemaster interface** has already been **setup**", "denied"
            )

    @voicemaster.command(
        name="reset", aliases=["remove"], brief="reset the voicemaster configuration"
    )
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def reset(self, ctx):
        if data := await self.bot.db.fetch(
            """
            SELECT voicechannel_id,
            channel_id, category_id
            FROM voicemaster
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        ):
            for voice, text, category in data:
                try:
                    vc = ctx.guild.get_channel(voice)
                    txt = ctx.guild.get_channel(text)
                    if vc:
                        await vc.delete()
                    if txt:
                        if category := ctx.guild.get_channel(category):
                            await category.delete()
                        await txt.delete()
                    await self.bot.db.execute(
                        """
                        DELETE FROM voicemaster
                        WHERE guild_id = $1
                        AND voicechannel_id = $2
                        AND channel_id = $3
                        """,
                        ctx.guild.id,
                        voice,
                        text,
                    )
                except discord.errors.NotFound:
                    pass

            active_vcs = []
            if active_vc := await self.bot.db.fetch(
                """
                SELECT channel_id
                FROM voicemaster_data
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            ):
                for vc in active_vc:
                    if vc := ctx.guild.get_channel(vc["channel_id"]):
                        active_vcs.append(vc)

            if active_vcs:
                for vc in active_vcs:
                    try:
                        try:
                            await vc.delete()
                        except Exception:
                            pass
                        await self.bot.db.execute(
                            """
                            DELETE FROM voicemaster_data
                            WHERE guild_id = $1
                            AND channel_id = $2
                            """,
                            ctx.guild.id,
                            vc.id,
                        )
                    except discord.errors.NotFound:
                        pass

            return await ctx.embed(
                "**Voicemaster interface** has been **reset**", "approved"
            )

        return await ctx.embed(
            "**Voicemaster interface** hasn't been **set up**", "denied"
        )

    @voicemaster.command(name="lock", brief="lock your voice channel")
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(self, ctx):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            if vc.overwrites_for(ctx.guild.default_role).connect is False:
                return await ctx.embed(
                    "Your **voice channel** is already **locked**", "denied"
                )

            await vc.set_permissions(ctx.guild.default_role, connect=False)
            return await ctx.embed(
                "Your **voice channel** has been **locked**", "approved"
            )

    @voicemaster.command(name="unlock", brief="unlock your voice channel")
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            if vc.overwrites_for(ctx.guild.default_role).connect is True:
                return await ctx.embed(
                    "Your **voice channel** isn't **locked**", "denied"
                )

            await vc.set_permissions(ctx.guild.default_role, connect=True)
            return await ctx.embed(
                "Your **voice channel** has been **unlocked**", "approved"
            )

    @voicemaster.command(
        name="hide", aliases=["ghost"], brief="hide your voice channel"
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def hide(self, ctx):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            if vc.overwrites_for(ctx.guild.default_role).view_channel is False:
                return await ctx.embed(
                    "Your **voice channel** is already **hidden**", "denied"
                )
            await vc.set_permissions(ctx.guild.default_role, view_channel=False)
            return await ctx.embed(
                "Your **voice channel** is now **hidden**", "approved"
            )

    @voicemaster.command(
        name="reveal",
        aliases=["show", "unhide"],
        brief="reveal your hidden voice channel",
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def reveal(self, ctx):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            if vc.overwrites_for(ctx.guild.default_role).view_channel is True:
                return await ctx.embed(
                    "Your **voice channel** isn't **hidden**", "denied"
                )
            await vc.set_permissions(ctx.guild.default_role, view_channel=True)
            return await ctx.embed(
                "Your **voice channel** is no longer **hidden**", "approved"
            )

    @voicemaster.command(
        name="rename", aliases=["name"], brief="rename your voice channel"
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def rename(self, ctx, *, name):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            await vc.edit(name=name)
            return await ctx.embed(
                f"""Your **voice channel** has been renamed to **{name}**""",
                message_type="approved"
            )

    @voicemaster.command(
        name="status", brief="set the status of all of your voice master channels"
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def voicemaster_status(self, ctx: commands.Context, *, status: str):
        await self.bot.db.execute(
            """INSERT INTO vm_status (user_id, status) VALUES($1, $2) ON CONFLICT(user_id) DO UPDATE SET status = excluded.status""",
            ctx.author.id,
            status[:499],
        )
        if ctx.author.voice:
            await ctx.author.voice.channel.edit(status=status[:499])
        return await ctx.embed(
            f"**voicemaster status** has been set to `{status[:499]}`",
            message_type="approved"
        )

    @voicemaster.command(
        name="claim", aliases=["own"], brief="claim an unclaimed voice channel"
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def voicemaster_claim(self, ctx):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        channel_data = await self.bot.db.fetchrow(
            """
            SELECT channel_id, owner_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND channel_id = $2
            """,
            ctx.guild.id,
            ctx.author.voice.channel.id,
        )

        if not channel_data:
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id, owner_id = channel_data

        owner = ctx.guild.get_member(owner_id)
        if owner and owner in ctx.author.voice.channel.members:
            return await ctx.embed(
                "The **owner** is still in the **voice channel**", "denied"
            )

        if owner:
            await reclaim(ctx.author.voice.channel, owner, ctx.author)
        else:
            overwrites = ctx.author.voice.channel.overwrites
            overwrites[ctx.author] = discord.PermissionOverwrite(
                connect=True,
                speak=True,
                stream=True,
                priority_speaker=True,
                manage_channels=True,
            )
            await ctx.author.voice.channel.edit(overwrites=overwrites)

        await self.bot.db.execute(
            """
            UPDATE voicemaster_data
            SET owner_id = $1
            WHERE guild_id = $2
            AND channel_id = $3
            """,
            ctx.author.id,
            ctx.guild.id,
            channel_id,
        )

        return await ctx.embed(
            "You are now the **owner** of this **voice channel**", "approved"
        )

    @voicemaster.command(
        name="information", brief="view information on the current voice channel"
    )
    async def voicemaster_information(self, ctx):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            owner = await self.bot.db.fetchval(
                """
                SELECT owner_id
                FROM voicemaster_data
                WHERE channel_id = $1
                AND guild_id = $2
                """,
                ctx.author.voice.channel.id,
                ctx.guild.id,
            )
            owner = ctx.guild.get_member(owner)
            embed = discord.Embed(
                description=f""">>> **Bitrate:** {vc.bitrate/1000} KBPS
**Members:** {len(vc.members)}
**Created:** <t:{round(vc.created_at.timestamp())}:D>
**Owner:** {owner.mention}""",
            )
            embed.set_author(name=vc.name, icon_url=owner.display_avatar)
            embed.set_thumbnail(url=owner.display_avatar)
            return await ctx.send(embed=embed)

    @voicemaster.command(
        name="limit", brief="limit the amount of users that can join your voice channel"
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def limit(self, ctx, limit: int):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if limit > 99:
            return await ctx.embed(
                "User limit **cannot** be higher than `99`", "denied"
            )

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            await vc.edit(user_limit=limit)
            return await ctx.embed(
                f"""Your **voice channel's user limit** has been set to `{limit}`""",
                message_type="approved"
            )

    @voicemaster.command(name="delete", brief="delete your voice channel")
    @commands.bot_has_permissions(manage_channels=True)
    async def delete(self, ctx):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            await self.bot.db.execute(
                """
                DELETE FROM voicemaster_data
                WHERE channel_id = $1
                """,
                channel_id,
            )
            await vc.delete()
            return await ctx.embed(
                """Your **voice channel** has been **deleted**""", "approved"
            )

    @voicemaster.command(
        name="reject",
        aliases=["kick"],
        brief="reject and kick a user out of your voice channel",
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def reject(self, ctx, *, member: discord.Member):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            overwrite = vc.overwrites_for(member)
            overwrite.connect = False
            overwrite.view_channel = False
            await vc.set_permissions(member, overwrite=overwrite)

            if member.voice and member.voice.channel == vc:
                await member.move_to(None)
                await ctx.embed(
                    f"**Kicked** {member.mention} and **revoked access** to your **voice channel**",
                    message_type="approved"
                )
            else:
                await ctx.embed(
                    f"**Revoked** {member.mention}'s access to your **voice channel**",
                    message_type="approved"
                )

    @voicemaster.command(
        name="permit",
        aliases=["allow"],
        brief="permit a user to join your voice channel",
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def permit(self, ctx, *, member: discord.Member):
        if not ctx.author.voice:
            return await ctx.embed("You **are not** in a **voice channel**", "denied")

        if not ctx.author.id == await self.bot.db.fetchval(
            """
            SELECT owner_id
            FROM voicemaster_data
            WHERE channel_id = $1
            AND guild_id = $2
            """,
            ctx.author.voice.channel.id,
            ctx.guild.id,
        ):
            return await ctx.embed("You **don't own** this **voice channel**", "denied")

        channel_id = await self.bot.db.fetchval(
            """
            SELECT channel_id
            FROM voicemaster_data
            WHERE guild_id = $1
            AND owner_id = $2
            AND channel_id = $3
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.author.voice.channel.id,
        )
        if channel_id:
            vc = ctx.guild.get_channel(channel_id)
            overwrite = vc.overwrites_for(member)
            overwrite.connect = True
            overwrite.view_channel = True
            await vc.set_permissions(member, overwrite=overwrite)
            await ctx.embed(
                f"**Permitted** {member.mention} to access your **voice channel**",
                message_type="approved"
            )

    @voicemaster.command(name="drag", brief="drag a user from a voice channel")
    @commands.has_permissions(manage_channels=True)
    async def drag(self, ctx: commands.Context, *, member: discord.Member):
        if not member.voice:
            return await ctx.embed(
                f"{member.mention} is not in a **voice channel**", "denied"
            )
        if not ctx.author.voice:
            return await ctx.embed("You are **not** in a **voice channel**", "denied")
        try:
            await member.move_to(ctx.author.voice.channel)
            return await ctx.embed(
                f"{member.mention} has been **moved** into [{ctx.author.voice.channel.name}]({ctx.author.voice.channel.jump_url})",
                message_type="approved"
            )
        except Exception:
            return await ctx.embed(
                f"I **couldn't move** {member.mention} into your **voice channel**",
                "denied",
            )

    @voicemaster.command(name="template")
    @commands.has_permissions(manage_guild=True)
    async def set_template(self, ctx, *, template: str):
        """Set a template for new voice channels
        Variables: {owner}, {count}
        """
        if len(template) > 32:
            return await ctx.embed("Template must be 32 characters or less", "warned")

        await self.bot.db.execute(
            """
            INSERT INTO voicemaster (guild_id, template) 
            VALUES ($1, $2)
            ON CONFLICT (guild_id) 
            DO UPDATE SET template = $2
            """,
            ctx.guild.id,
            template,
        )
        self.vm_cache.pop(ctx.guild.id, None)  
        return await ctx.embed(f"Voice channel template set to: {template}", "approved")

    @voicemaster.command(name="temporary")
    @commands.has_permissions(manage_guild=True)
    async def toggle_temporary(self, ctx):
        """Toggle temporary voice channels that auto-delete when empty"""
        current = await self.bot.db.fetchval(
            "SELECT temporary FROM voicemaster WHERE guild_id = $1", ctx.guild.id
        )

        new_value = not current if current is not None else True

        await self.bot.db.execute(
            """
            INSERT INTO voicemaster (guild_id, temporary) 
            VALUES ($1, $2)
            ON CONFLICT (guild_id) 
            DO UPDATE SET temporary = $2
            """,
            ctx.guild.id,
            new_value,
        )
        self.vm_cache.pop(ctx.guild.id, None)

        status = "enabled" if new_value else "disabled"
        return await ctx.embed(f"Temporary voice channels {status}", "approved")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Track voice channel activity"""
        if before.channel:
            data = await self.bot.db.fetchrow(
                """
                SELECT * FROM voicemaster_data 
                WHERE channel_id = $1 AND temporary = true
                """,
                before.channel.id,
            )
            if data and len(before.channel.members) == 0:
                await asyncio.sleep(300)  
                channel = self.bot.get_channel(before.channel.id)
                if channel and len(channel.members) == 0:
                    await self.bot.db.execute(
                        "DELETE FROM voicemaster_data WHERE channel_id = $1", channel.id
                    )
                    await channel.delete()


async def setup(bot: Greed) -> None:
    cog = Voicemaster(bot)
    await bot.add_cog(cog)
