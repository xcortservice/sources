from discord import Embed, Interaction, Member
from discord.ui import Button, View


class DefaultBanner(Button):
    def __init__(self):
        super().__init__(label="View default banner")

    async def callback(self, interaction: Interaction):
        self.view.clear_items()
        self.view.add_item(UserBanner())
        await interaction.response.edit_message(embed=self.view.embed, view=self.view)


class UserBanner(Button):
    def __init__(self):
        super().__init__(label="View guild banner")

    async def callback(self, interaction: Interaction):
        embed = interaction.message.embeds[0]
        embed.title = f">>> {self.view.member}'s guild banner"
        embed.set_image(url=self.view.member.display_banner.url)
        self.view.clear_items()
        self.view.add_item(DefaultBanner())
        return await interaction.response.edit_message(embed=embed, view=self.view)


class Banners(View):
    def __init__(self, embed: Embed, author: int, member: Member):
        self.embed = embed
        self.member = member
        self.author = author
        super().__init__()

    async def interaction_check(self, interaction: Interaction):
        if interaction.user.id != self.author:
            await interaction.response.defer(ephemeral=True)

        return interaction.user.id == self.author

    def stop(self):
        try:
            self.children[0].disabled = True
        except IndexError:
            pass
        return super().stop()

    async def on_timeout(self):
        self.stop()
        return await self.message.edit(view=self)
