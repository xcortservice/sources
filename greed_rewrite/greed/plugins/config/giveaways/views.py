from discord import Button, ButtonStyle, Interaction, Embed
from discord.ui import View, button
from dataclasses import dataclass

class GiveawayView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(emoji="🎉", style=ButtonStyle.blurple, custom_id="persistent:join_gw")
    async def join_gw(self, interaction: Interaction, button: Button):
        if not await interaction.client.db.fetchrow(
            """SELECT * FROM gw WHERE guild_id = $1 AND message_id = $2""",
            interaction.guild.id,
            interaction.message.id,
        ):
            return await interaction.response.send_message(
                "this giveaway has ended", ephemeral=True
            )

        giveaway = await interaction.client.db.fetchrow(
            """SELECT * FROM gw WHERE guild_id = $1 AND message_id = $2""",
            interaction.guild.id,
            interaction.message.id,
        )

        if giveaway["required_role"]:
            if not any(role.id == giveaway["required_role"] for role in interaction.user.roles):
                return await interaction.response.send_message(
                    f"You need the {interaction.guild.get_role(giveaway['required_role']).mention} role to enter this giveaway!",
                    ephemeral=True
                )

        count = (
            await interaction.client.db.fetchval(
                """SELECT entry_count FROM giveaway_entries WHERE guild_id = $1 AND message_id = $2 AND user_id = $3""",
                interaction.guild.id,
                interaction.message.id,
                interaction.user.id,
            )
            or 0
        )
        max_count = await interaction.client.db.fetch(
            """
            SELECT *
            FROM giveaway_settings
            WHERE guild_id = $1
            AND role_id = ANY ($2)
        """,
            interaction.guild.id,
            [r.id for r in interaction.user.roles],
        )
        if max_count:
            max_count = max([i["entries"] for i in max_count])
        else:
            max_count = 1
        if count >= max_count:
            return await interaction.response.send_message(
                "You have reached the maximum number of entries for this giveaway",
                ephemeral=True,
            )
        await interaction.client.db.execute(
            """
            INSERT INTO giveaway_entries (guild_id, message_id, user_id, entry_count)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id, message_id, user_id)
            DO UPDATE SET entry_count = giveaway_entries.entry_count + 1
        """,
            interaction.guild.id,
            interaction.message.id,
            interaction.user.id,
            count + 1,
        )
        return await interaction.response.send_message(
            "You have joined the giveaway", ephemeral=True
        )

    @button(
        emoji=None,
        style=ButtonStyle.gray,
        custom_id="persistent:participants",
        label="Participants",
    )
    async def paricipants(self, interaction: Interaction, button: Button):
        if not await interaction.client.db.fetchrow(
            """SELECT * FROM gw WHERE guild_id = $1 AND message_id = $2""",
            interaction.guild.id,
            interaction.message.id,
        ):
            return await interaction.response.send_message(
                "this giveaway has ended", ephemeral=True
            )
        participants = await interaction.client.db.fetch(
            """SELECT user_id, entry_count FROM giveaway_entries WHERE guild_id = $1 AND message_id = $2""",
            interaction.guild.id,
            interaction.message.id,
        )
        if not participants:
            return await interaction.response.send_message(
                "There are no participants in this giveaway", ephemeral=True
            )
        embed = Embed(
            description=f"These are the members that have participated in the giveaway of **{interaction.message.embeds[0].title}**"
        )
        embed.description += "\n"
        p = [
            participant
            for participant in participants
            if interaction.guild.get_member(participant["user_id"])
        ]

        if len(p) > 10:
            t = f"+ {len(participants) - 10} more"
        else:
            t = None
        for i, participant in enumerate(p[:10], start=1):
            embed.description += f"`{i}` **{interaction.guild.get_member(participant['user_id']).name}** - `{participant['entry_count']}`\n"
        embed.set_footer(text=f"Total: {len(participants)}")
        if t:
            embed.description += f"{t}"
        return await interaction.response.send_message(embed=embed, ephemeral=True)


@dataclass
class EmojiEntry:
    name: str
    id: int
    url: str
    animated: bool
