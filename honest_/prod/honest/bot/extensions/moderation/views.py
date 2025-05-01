from datetime import datetime
from typing import Literal

from discord import ButtonStyle, Color, Embed, Interaction, Member
from discord.ui import Button, View, button


class Confirm(View):

    def __init__(
        self: "Confirm",
        author: Member,
        victim: Member,
        command: Literal["ban", "kick"],
        reason: str,
    ):
        self.author = author
        self.victim = victim
        self.command_name = command
        self.reason = reason
        super().__init__()

    async def notify(self: "Confirm"):
        action = (
            f"{self.command_name}ned"
            if self.command_name == "ban"
            else f"{self.command_name}ed"
        )
        embed = (
            Embed(
                color=Color.red(),
                title=action.capitalize(),
                description=f"You have been {action} by **{self.author}** in **{self.author.guild}**",
                timestamp=datetime.now(),
            )
            .add_field(name="Reason", value=self.reason.split(" - ")[1])
            .set_thumbnail(url=self.author.guild.icon)
            .set_footer(
                text="for more about this punishment, please contact a staff member"
            )
        )

        try:
            await self.victim.send(embed=embed)
            return None
        except Exception:
            return "Couldn't DM member"

    async def interaction_check(self: "Confirm", interaction: Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "You cannot interact with this message", ephemeral=True
            )

        return interaction.user.id == self.author.id

    @button(label="Yes", style=ButtonStyle.green)
    async def positive(self: "Confirm", interaction: Interaction, button: Button):
        if self.command_name == "ban":
            await self.victim.ban(reason=self.reason)
        else:
            await self.victim.kick(reason=self.reason)

        notify = await self.notify()
        return await interaction.response.edit_message(
            content=f"👍 {f' - {notify}' if notify else ''}", view=None, embed=None
        )

    @button(label="No", style=ButtonStyle.red)
    async def negative(self: "Confirm", interaction: Interaction, button: Button):
        return await interaction.response.edit_message(
            content=f"Cancelled the ban for {self.victim.mention}",
            embed=None,
            view=None,
        )
