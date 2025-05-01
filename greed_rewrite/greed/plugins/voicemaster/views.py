import discord
from discord.ui import View
from typing import Union
from greed.shared.config import Colors

# class PlayModal(discord.ui.Modal, title="Play"):
#     def __init__(self, bot):
#         super().__init__()
#         self.bot = bot

#     firstfield = discord.ui.TextInput(
#         label="Play a song through Greed",
#         placeholder="e.g., Ram Ranch",
#         min_length=1,
#         max_length=500,
#         style=discord.TextStyle.short,
#     )

#     async def interaction_check(self, interaction: discord.Interaction):
#         song_name = self.firstfield.value
#         if song_name:
#             logger.info(f"Play Modal received query: {song_name}")
#             from greed.plugins.music import enqueue

#             await enqueue(self.bot, interaction, song_name)
#             return True
#         return False

class RenameModal(discord.ui.Modal, title="Rename"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    firstfield = discord.ui.TextInput(
        label="Rename your voice channel",
        placeholder="example: Movie night",
        min_length=1,
        max_length=32,
        style=discord.TextStyle.short,
    )

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.data["components"][0]["components"][0]["value"]:
            name = interaction.data["components"][0]["components"][0]["value"]
            if name is None:
                name = f"{interaction.author}'s channel"
            if interaction.user.voice.channel:
                data = await self.bot.db.fetchval(
                    """
                    SELECT channel_id
                    FROM voicemaster_data
                    WHERE channel_id = $1
                    AND owner_id = $2
                    """,
                    interaction.user.voice.channel.id,
                    interaction.user.id,
                )
                if data:
                    vc = interaction.guild.get_channel(data)
                    await vc.edit(name=name)
                    embed = discord.Embed(
                        description=f"> Your **voice channel** has been **renamed** to **{name}**",
                        color=0x2D2B31,
                    )
                    return await interaction.response.send_message(
                        embed=embed, ephemeral=True
                    )
                else:
                    embed = discord.Embed(
                        description="> You **don't** own this **voice channel**",
                        color=0x2D2B31,
                    )
                    return await interaction.response.send_message(
                        embed=embed, ephemeral=True
                    )
            else:
                embed = discord.Embed(
                    description="> You **aren't** connected to a **voicemaster channel**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )


async def reclaim(
    channel: discord.VoiceChannel,
    old_owner: Union[discord.Member, discord.User],
    new_owner: discord.Member,
):
    o = channel.overwrites
    o[new_owner] = o[old_owner]
    o.pop(old_owner)
    await channel.edit(overwrites=o)


# Label, Description, Value

OPTIONS = [
    ["Lock Channel", "Lock your voice channel from non admins joining", "lock"],
    ["Unlock Channel", "Unlock your channel so anyone can join", "unlock"],
    ["Hide Channel", "Hide your channel from users seeing it", "hide"],
    ["Reveal Channel", "Allow users to see your channel", "reveal"],
    ["Rename Channel", "Rename your channel", "rename"],
    ["Claim Ownership", "Claim ownership of the current voice channel", "claim"],
    ["Increase User Limit", "Increase the user limit of your channel", "increase"],
    ["Decrease User Limit", "Decrease the user limit of your channel", "decrease"],
    ["Delete Channel", "Delete your channel", "delete"],
    [
        "Show Information",
        "Show information regarding your voice channel",
        "information",
    ],
    ["Play", "Play a song thru greed", "play"],
]


class VoicemasterInterface(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.options = [
            discord.SelectOption(label=_[0], description=_[1], value=_[2])
            for _ in OPTIONS
        ]

        self.add_item(VmSelectMenu(self.bot))


class VmSelectMenu(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label=_[0], description=_[1], value=_[2])
            for _ in OPTIONS
        ]
        super().__init__(
            custom_id="VM:Select",
            placeholder="Voicemaster options...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def lock(self, interaction: discord.Interaction):
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

    async def unlock(self, interaction: discord.Interaction):
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

    async def hide(self, interaction: discord.Interaction):
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

    # async def play(self, interaction: discord.Interaction):
    #     return await interaction.response.send_modal(PlayModal(self.bot))

    async def reveal(self, interaction: discord.Interaction):
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

    async def rename(self, interaction: discord.Interaction):
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

    async def claim(self, interaction: discord.Interaction):
        try:
            # Check if the user is not connected to a voice channel
            if not interaction.user.voice:
                embed = discord.Embed(
                    description="> You **aren't** connected to a **Voicemaster channel**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )

            # Check if the user is not the owner of the current voice channel
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

            # Check if the owner is not in the voice channel
            owner = interaction.guild.get_member(owner_id)
            if owner and owner in interaction.user.voice.channel.members:
                embed = discord.Embed(
                    description="> The owner is **still** in the **voice channel**",
                    color=0x2D2B31,
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
            await reclaim(interaction.user.voice.channel, owner, interaction.user)
            # Update the owner in the database
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

    async def increase(self, interaction: discord.Interaction):
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

    async def decrease(self, interaction: discord.Interaction):
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
            await vc.edit(user_limit=vc.user_limit - 1)
            embed = discord.Embed(
                description=f"> Your **voice channel's user limit** has been **decreased** to `{vc.user_limit}`"
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    async def delete(self, interaction: discord.Interaction):
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

    async def information(self, interaction: discord.Interaction):
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
                color=Colors().information,
                description=f""">>> **Bitrate:** {vc.bitrate/1000} KBPS
**Members:** {len(vc.members)}
**Created:** <t:{round(vc.created_at.timestamp())}:D>
**Owner:** {owner.mention}""",
            )
            embed.set_author(name=vc.name, icon_url=owner.display_avatar)
            embed.set_thumbnail(url=owner.display_avatar)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        await getattr(self, value)(interaction)
        self.values.clear()
        return await interaction.message.edit(view=self.view)