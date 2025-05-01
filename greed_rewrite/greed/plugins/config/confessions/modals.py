import discord
import datetime

from discord.ui import Modal
from discord import Embed, Interaction


class ReplyModal(Modal, title="Reply to Confession"):
    reply = discord.ui.TextInput(
        label="Reply",
        placeholder="Your reply will be anonymous.",
        style=discord.TextStyle.long,
        max_length=2000,
    )

    async def on_submit(self, interaction: Interaction):
        try:
            if not interaction.message.thread:
                thread = await interaction.message.create_thread(
                    name="Confession Replies"
                )
            else:
                thread = interaction.message.thread

            e = Embed(
                description=f"{self.reply.value}",
                timestamp=datetime.datetime.now(),
            )
            e.set_author(name="anonymous reply")

            reply_message = await thread.send(embed=e)

            print(f"Reply message ID: {reply_message.id}")
            print(f"User ID: {interaction.user.id}")
            print(f"Guild ID: {interaction.guild.id}")

            try:
                await interaction.client.db.execute(
                    """
                    INSERT INTO confess_replies (message_id, user_id, guild_id)
                    VALUES ($1, $2, $3)
                    """,
                    reply_message.id,
                    interaction.user.id,
                    interaction.guild.id,
                )
                print("Successfully stored reply in database")
            except Exception as db_error:
                print(f"Database error: {db_error}")

            e.set_footer(
                text=f"Report this reply with ,confessions report {reply_message.id}"
            )
            await reply_message.edit(embed=e)

            await interaction.response.send_message("Reply sent!", ephemeral=True)
        except Exception as e:
            print(f"Error in ReplyModal: {e}")
            return await interaction.warn(f"Couldn't send your reply - {e}")


class ReplyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Reply", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.message.thread:
            thread = await interaction.message.create_thread(name="Confession Replies")
        else:
            thread = interaction.message.thread
        await interaction.response.send_modal(ReplyModal())


class ConfessModal(Modal, title="Confess Here"):
    name = discord.ui.TextInput(
        label="Confession",
        placeholder="The confession is anonymous.",
        style=discord.TextStyle.long,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            key = f"confess_cooldown:{interaction.user.id}"
            if await interaction.client.redis.exists(key):
                return await interaction.warn(
                    "Please wait before sending another confession!"
                )

            blacklist = await interaction.client.db.fetch(
                """
                SELECT word FROM confess_blacklist 
                WHERE guild_id = $1
                """,
                interaction.guild.id,
            )

            if blacklist:
                for record in blacklist:
                    if record["word"].lower() in self.children[0].value.lower():
                        return await interaction.warn(
                            "Your confession contains blacklisted words!"
                        )

            check = await interaction.client.db.fetchrow(
                """
                SELECT * FROM confess 
                WHERE guild_id = $1
                """,
                interaction.guild.id,
            )

            if check:
                channel = interaction.guild.get_channel(check["channel_id"])
                if not channel:
                    await interaction.client.db.execute(
                        """
                        UPDATE confess 
                        SET channel_id = NULL 
                        WHERE guild_id = $1
                        """,
                        interaction.guild.id,
                    )
                    return await interaction.warn(
                        "The confession channel no longer exists. Please set a new confession channel."
                    )

                count = check["confession"] + 1
                links = [
                    "https://",
                    "http://",
                    ".com",
                    ".ro",
                    ".gg",
                    ".xyz",
                    ".cf",
                    ".org",
                    ".ru",
                    ".it",
                    ".de",
                ]

                if any(link in self.children[0].value for link in links):
                    return await interaction.warn(
                        "I can't send links, those things can be dangerous!!"
                    )

                embed = Embed(
                    description=f"{interaction.user.mention}: Sent your confession in {channel.mention}",
                )

                await interaction.response.send_message(embed=embed, ephemeral=True)

                e = Embed(
                    description=f"{self.name.value}",
                    timestamp=datetime.datetime.now(),
                )

                icon_url = (
                    interaction.guild.icon.url if interaction.guild.icon else None
                )
                e.set_author(
                    name=f"anonymous confession #{count}",
                    url="https://discord.gg/greedbot",
                    icon_url=icon_url,
                )

                e.set_footer(
                    text=f"Type /confess to send a confession • Report this confession with ,confessions report {count}"
                )

                view = discord.ui.View()
                view.add_item(ReplyButton())
                message = await channel.send(embed=e, view=view)

                await interaction.client.db.execute(
                    """
                    UPDATE confess SET confession = $1 
                    WHERE guild_id = $2
                    """,
                    count,
                    interaction.guild.id,
                )

                await interaction.client.db.execute(
                    """
                    INSERT INTO confess_members 
                    VALUES ($1,$2,$3)
                    """,
                    interaction.guild.id,
                    interaction.user.id,
                    count,
                )

                await interaction.client.redis.set(key, "1", ex=60)

                reactions = await interaction.client.db.fetchrow(
                    """
                    SELECT upvote, downvote 
                    FROM confess 
                    WHERE guild_id = $1
                    """,
                    interaction.guild.id,
                )

                if reactions["upvote"]:
                    await message.add_reaction(reactions["upvote"])
                if reactions["downvote"]:
                    await message.add_reaction(reactions["downvote"])

        except Exception as e:
            return await interaction.warn(f"Couldn't send your confession - {e}")
