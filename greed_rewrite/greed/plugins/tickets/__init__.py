import asyncio
import re

from typing import Optional

from discord.abc import GuildChannel
from discord.ui import View, Button, Select, Modal, TextInput, DynamicItem
from discord.ext import commands
from discord.ext.commands import (
    PartialEmojiConverter,
    group,
    Cog,
    Context,
    has_permissions,
    check,
    bot_has_permissions,
    CommandError,
)
from discord import (
    PermissionOverwrite,
    Member,
    Embed,
    Role,
    CategoryChannel,
    TextChannel,
    Interaction,
    ButtonStyle,
    SelectOption,
    TextStyle,
)

from greed.framework import Context, Greed
from greed.framework.discord.parser import EmbedConverter
from greed.shared.config import Colors

EMOJI_REGEX = re.compile(
    r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>"
)

DEFAULT_EMOJIS = re.compile(
    r"[\U0001F300-\U0001F5FF]|[\U0001F600-\U0001F64F]|[\U0001F680-\U0001F6FF]|[\U0001F700-\U0001F77F]|[\U0001F780-\U0001F7FF]|[\U0001F800-\U0001F8FF]|[\U0001F900-\U0001F9FF]|[\U0001FA00-\U0001FA6F]|[\U0001FA70-\U0001FAFF]|[\U00002702-\U000027B0]|[\U000024C2-\U0001F251]|[\U0001F910-\U0001F9C0]|[\U0001F3A0-\U0001F3FF]"
)


class Emojis(commands.Converter):
    async def convert(self, ctx: Context, argument: str):
        emojis = []
        matches = EMOJI_REGEX.finditer(argument)
        for emoji in matches:
            e = emoji.groupdict()
            emojis.append(
                await PartialEmojiConverter().convert(
                    ctx, f"<{e['animated']}:{e['name']}:{e['id']}>"
                )
            )
        defaults = DEFAULT_EMOJIS.findall(argument)
        if len(defaults) > 0:
            emojis.extend(defaults)
        return emojis


def get_ticket():
    async def predicate(ctx: Context):
        check = await ctx.bot.db.fetchrow(
            "SELECT * FROM opened_tickets WHERE guild_id = $1 AND channel_id = $2",
            ctx.guild.id,
            ctx.channel.id,
        )
        if check is None:
            await ctx.embed("This message has to be used in an opened ticket", "warned")
            return False
        return True

    return check(predicate)


def manage_ticket():
    async def predicate(ctx: Context):
        guild_id = ctx.guild.id
        author = ctx.author
        guild_permissions = author.guild_permissions

        ticket_data = await ctx.bot.db.fetchrow(
            "SELECT support_id FROM tickets WHERE guild_id = $1", guild_id
        )
        fake_permissions = await ctx.bot.db.fetchrow(
            "SELECT role_id, perms FROM fakeperms WHERE guild_id = $1", guild_id
        )

        if ticket_data:
            support_role_id = ticket_data.get("support_id")
            support_role = ctx.guild.get_role(support_role_id)
            if support_role and support_role not in author.roles:
                if not guild_permissions.manage_channels:
                    raise CommandError(
                        f"Only members with {support_role.mention} role or those with the "
                        f"**Manage Channels** permission can manage the ticket."
                    )

        elif not guild_permissions.manage_channels:
            if fake_permissions:
                if (
                    fake_permissions["role_id"] == author.id
                    and "manage_channels" not in fake_permissions["perms"]
                ):
                    raise CommandError(
                        "You need the **Manage Channels** permission to manage the ticket."
                    )
            else:
                raise CommandError(
                    "Only members with the **Manage Channels** permission can manage the ticket."
                )

        return True

    return check(predicate)


def ticket_exists():
    async def predicate(ctx: Context):
        check = await ctx.bot.db.fetchrow(
            "SELECT * FROM tickets WHERE guild_id = $1", ctx.guild.id
        )
        if not check:
            await ctx.bot.db.execute(
                """INSERT INTO tickets (
                    guild_id, 
                    channel_id,
                    category_id,
                    support_id,
                    open_embed,
                    message_id,
                    delete_emoji,
                    open_emoji
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                ctx.guild.id,
                ctx.channel.id,
                None,
                None,
                None,
                None,
                None,
                None,
            )
        return True

    return check(predicate)


class TicketCategory(Modal, title="Add a ticket category"):
    name = TextInput(
        label="category name",
        placeholder="the ticket category's name..",
        required=True,
        style=TextStyle.short,
    )

    description = TextInput(
        label="category description",
        placeholder="the description of the ticket category...",
        required=False,
        max_length=100,
        style=TextStyle.long,
    )

    async def on_submit(self, interaction: Interaction):
        check = await interaction.client.db.fetchrow(
            "SELECT * FROM ticket_topics WHERE guild_id = $1 AND name = $2",
            interaction.guild.id,
            self.name.value,
        )

        if check:
            return await interaction.response.send_message(
                f"A topic with the name **{self.name.value}** already exists",
                ephemeral=True,
            )

        await interaction.client.db.execute(
            """INSERT INTO ticket_topics (guild_id, name, description) 
            VALUES ($1, $2, $3)""",
            interaction.guild.id,
            self.name.value,
            self.description.value,
        )
        return await interaction.response.send_message(
            f"Added new ticket topic **{self.name.value}**", ephemeral=True
        )


class OpenTicket(
    DynamicItem[Button],
    template=r"button:open:(?P<guild_id>[0-9]+)",
):
    def __init__(self, guild_id: int, emoji: str = "🎫"):
        super().__init__(
            Button(
                label="Create",
                emoji=emoji,
                custom_id=f"button:open:{guild_id}",
                style=ButtonStyle.primary,
            )
        )
        self.guild_id = guild_id

    @classmethod
    async def from_custom_id(
        cls, interaction: Interaction, item: Button, match: re.Match[str]
    ):
        guild_id = int(match["guild_id"])
        return cls(guild_id)

    async def create_channel(
        self,
        interaction: Interaction,
        category: Optional[CategoryChannel],
        title: Optional[str] = None,
        topic: Optional[str] = None,
        embed: Optional[str] = None,
    ):
        view = TicketView(interaction.client, guild_id=self.guild_id)
        await view.setup()
        view.delete_ticket()

        if topic:
            topic_category = await interaction.client.db.fetchrow(
                "SELECT category_id FROM ticket_topic_categories WHERE guild_id = $1 AND topic_name = $2",
                interaction.guild.id,
                topic,
            )
            if topic_category and topic_category["category_id"]:
                category = interaction.guild.get_channel(topic_category["category_id"])

        overwrites = {}
        overwrites[interaction.guild.default_role] = PermissionOverwrite(
            read_messages=False,
            view_channel=False,
            send_messages=False,
            attach_files=False,
            embed_links=False,
        )

        overwrites[interaction.user] = PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
        )

        overwrites[interaction.guild.me] = PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            manage_channels=True,
            manage_messages=True,
            manage_permissions=True,
        )

        che = await interaction.client.db.fetchrow(
            "SELECT support_id FROM tickets WHERE guild_id = $1", interaction.guild.id
        )
        if che and che["support_id"]:
            role = interaction.guild.get_role(che["support_id"])
            if role:
                overwrites[role] = PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True,
                    manage_permissions=True,
                )

        if topic:
            topic_roles = await interaction.client.db.fetch(
                "SELECT role_id FROM ticket_topic_roles WHERE guild_id = $1 AND topic_name = $2",
                interaction.guild.id,
                topic,
            )

            for record in topic_roles:
                role_id = record["role_id"]
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        manage_messages=True,
                        manage_permissions=True,
                    )

            if not topic_roles and che and che["support_id"]:
                role = interaction.guild.get_role(che["support_id"])
                if role:
                    overwrites[role] = PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        manage_messages=True,
                        manage_permissions=True,
                    )

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            topic=f"A ticket opened by {interaction.user.name} ({interaction.user.id})"
            + (f" | Topic: {topic}" if topic else ""),
            reason=f"Ticket opened by {interaction.user.name}",
            overwrites=overwrites,
        )

        await interaction.client.db.execute(
            """INSERT INTO opened_tickets (guild_id, channel_id, user_id) 
            VALUES ($1, $2, $3)""",
            interaction.guild.id,
            channel.id,
            interaction.user.id,
        )

        if topic:
            await interaction.client.db.execute(
                """INSERT INTO opened_ticket_topics (guild_id, channel_id, topic_name) 
                VALUES ($1, $2, $3)""",
                interaction.guild.id,
                channel.id,
                topic,
            )

        if not embed:
            embed = "{embed}{author: {user.name} && {user.avatar}}$v{title: {title}}$v{content: {user.mention}}$v{description: A **ticket master** will be avaliable to you shortly. **To close the ticket** Press the button below.}$v{color: #2b2d31}".replace(
                "{title}", title or "Ticket Opened"
            )

        mes = await interaction.client.send_embed(
            channel,
            embed.replace("{topic}", topic or "none"),
            user=interaction.user,
            view=view,
        )
        await mes.pin(reason="pinned the ticket message")
        return channel

    async def callback(self, interaction: Interaction) -> None:
        check = await interaction.client.db.fetchrow(
            "SELECT * FROM tickets WHERE guild_id = $1", interaction.guild.id
        )
        if not check:
            await interaction.client.db.execute(
                """INSERT INTO tickets (
                    guild_id,
                    channel_id,
                    category_id,
                    support_id,
                    open_embed,
                    message_id,
                    delete_emoji,
                    open_emoji
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                interaction.guild.id,
                interaction.channel.id,
                None,
                None,
                None,
                None,
                None,
                None,
            )
            check = await interaction.client.db.fetchrow(
                "SELECT * FROM tickets WHERE guild_id = $1", interaction.guild.id
            )

        results = await interaction.client.db.fetch(
            "SELECT * FROM ticket_topics WHERE guild_id = $1", interaction.guild.id
        )
        category = (
            interaction.guild.get_channel(check["category_id"])
            if check["category_id"]
            else None
        )
        open_embed = check["open_embed"]

        if len(results) == 0:
            channel = await self.create_channel(
                interaction, category, title=None, topic=None, embed=open_embed
            )
            await interaction.response.send_message(
                f"**Opened a ticket** for you in {channel.mention}", ephemeral=True
            )
        else:
            options = [
                SelectOption(label=result["name"], description=result["description"])
                for result in results
            ]
            select = Select(options=options, placeholder="Topic menu")
            view = View(timeout=None)

            async def select_callback(inter: Interaction) -> None:
                if not inter.user == interaction.user:
                    return await inter.response.send_message(
                        "You cannot use this selection menu.", ephemeral=True
                    )

                topic = select.values[0]
                topic_exists = await interaction.client.db.fetchrow(
                    "SELECT * FROM ticket_topics WHERE guild_id = $1 AND name = $2",
                    interaction.guild.id,
                    topic,
                )

                if not topic_exists:
                    return await inter.response.send_message(
                        "This topic no longer exists.", ephemeral=True
                    )

                channel = await self.create_channel(
                    inter,
                    category,
                    title=f"Category: {topic}",
                    topic=topic,
                    embed=open_embed,
                )
                await inter.response.send_message(
                    f"**Opened a ticket** for you in {channel.mention}", ephemeral=True
                )

            select.callback = select_callback
            view.add_item(select)
            embed = Embed(
                color=interaction.client.color, description="🔍 Select a topic"
            )
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )


class DeleteTicket(
    DynamicItem[Button],
    template=r"button:close:(?P<guild_id>[0-9]+)",
):
    def __init__(self, guild_id: int, emoji: str = "🗑️"):
        super().__init__(
            Button(
                emoji=emoji,
                custom_id=f"button:close:{guild_id}",
                style=ButtonStyle.primary,
            )
        )
        self.guild_id = guild_id

    @classmethod
    async def from_custom_id(
        cls, interaction: Interaction, item: Button, match: re.Match[str], /
    ):
        guild_id = int(match["guild_id"])
        return cls(guild_id)

    async def callback(self, interaction: Interaction) -> None:
        ticket_data = await interaction.client.db.fetchrow(
            "SELECT support_id FROM tickets WHERE guild_id = $1", interaction.guild.id
        )
        fake_permissions = await interaction.client.db.fetchrow(
            "SELECT role_id, perms FROM fakeperms WHERE guild_id = $1",
            interaction.guild.id,
        )

        has_permission = False
        error_message = "You need the **Manage Channels** permission or the support role to close tickets."

        if interaction.user.guild_permissions.manage_channels:
            has_permission = True
        elif ticket_data and ticket_data["support_id"]:
            support_role = interaction.guild.get_role(ticket_data["support_id"])
            if support_role and support_role in interaction.user.roles:
                has_permission = True
        elif fake_permissions:
            if (
                fake_permissions["role_id"] == interaction.user.id
                and "manage_channels" in fake_permissions["perms"]
            ):
                has_permission = True

        if not has_permission:
            return await interaction.response.send_message(
                error_message, ephemeral=True
            )

        view = View(timeout=None)
        yes = Button(label="Yes", style=ButtonStyle.success)
        no = Button(label="No", style=ButtonStyle.danger)

        async def button_check(inter: Interaction) -> bool:
            if inter.user != interaction.user:
                await inter.response.send_message(
                    "You cannot use these buttons.", ephemeral=True
                )
                return False
            return True

        async def yes_callback(inter: Interaction) -> None:
            if not await button_check(inter):
                return

            await inter.response.edit_message(
                content="**Channel will be deleted** in a moment.", view=None
            )

            try:
                await interaction.client.db.execute(
                    "DELETE FROM opened_tickets WHERE guild_id = $1 AND channel_id = $2",
                    interaction.guild.id,
                    interaction.channel.id,
                )
                await asyncio.sleep(5)
                await inter.channel.delete(
                    reason=f"Ticket closed by {interaction.user}"
                )
            except Exception as e:
                await inter.followup.send(
                    f"Failed to delete the ticket: {str(e)}", ephemeral=True
                )

        async def no_callback(inter: Interaction) -> None:
            if not await button_check(inter):
                return

            await inter.response.edit_message(
                content="Channel will **not be deleted**", view=None
            )

        yes.callback = yes_callback
        no.callback = no_callback
        view.add_item(yes)
        view.add_item(no)

        await interaction.response.send_message(
            "**Close this ticket?**", view=view, ephemeral=True
        )


class TicketView(View):
    def __init__(
        self,
        bot: commands.AutoShardedBot,
        guild_id: int,
        open_ticket_emoji: str = None,
        delete_ticket_emoji: str = None,
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.open_ticket_emoji = open_ticket_emoji
        self.delete_ticket_emoji = delete_ticket_emoji

    async def setup(self, refresh: bool = False):
        emojis = await self.bot.db.fetchrow(
            "SELECT open_emoji, delete_emoji, message_id FROM tickets WHERE guild_id = $1",
            self.guild_id,
        )
        try:
            self.open_ticket_emoji = emojis["open_emoji"] or "📨"
            self.delete_ticket_emoji = emojis["delete_emoji"] or "🗑️"
            if refresh:
                return emojis["message_id"]
        except Exception:
            pass
        return

    def create_ticket(self):
        self.add_item(OpenTicket(guild_id=self.guild_id, emoji=self.open_ticket_emoji))

    def delete_ticket(self):
        self.add_item(
            DeleteTicket(guild_id=self.guild_id, emoji=self.delete_ticket_emoji)
        )


class Tickets(Cog):
    def __init__(self, bot: Greed):
        self.bot = bot
        self.register_views()

    def register_views(self):
        view = TicketView(self.bot, 0)
        view2 = TicketView(self.bot, 0)
        view.create_ticket()
        view2.delete_ticket()
        self.bot.add_view(view2)
        self.bot.add_view(view)

    @commands.command(name="sendmessage", hidden=True)
    @commands.is_owner()
    async def sendmessage(self, ctx: Context, *, code: EmbedConverter):
        code.pop("view", None)
        return await ctx.send(**code)

    @Cog.listener()
    async def on_guild_channel_delete(self, channel: GuildChannel):
        if str(channel.type) == "text":
            await self.bot.db.execute(
                "DELETE FROM opened_tickets WHERE guild_id = $1 AND channel_id = $2",
                channel.guild.id,
                channel.id,
            )

    @group(
        name="ticket",
        brief="Configure the tickets setup for your server",
        example=",ticket",
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def ticket(self, ctx):
        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command.qualified_name)

    @ticket.command(
        name="add", brief="Add a user to the ticket", example=",ticket add @66adam"
    )
    @commands.bot_has_permissions(manage_channels=True)
    @manage_ticket()
    @get_ticket()
    async def ticket_add(self, ctx: Context, *, member: Member):
        """add a person to the ticket"""
        overwrites = PermissionOverwrite()
        overwrites.send_messages = True
        overwrites.view_channel = True
        overwrites.attach_files = True
        overwrites.embed_links = True
        await ctx.channel.set_permissions(
            member, overwrite=overwrites, reason="Added to the ticket"
        )
        return await ctx.embed(f"{member.mention} has been **added to this ticket**", "approved")

    @ticket.command(
        name="remove",
        brief="Remove a ticket that a user has created",
        example=",ticket remove @66adam",
    )
    @commands.bot_has_permissions(manage_channels=True)
    @manage_ticket()
    @get_ticket()
    async def ticket_remove(self, ctx: Context, *, member: Member):
        """remove a member from the ticket"""
        overwrites = PermissionOverwrite()
        overwrites.send_messages = False
        overwrites.view_channel = False
        overwrites.attach_files = False
        overwrites.embed_links = False
        await ctx.channel.set_permissions(
            member, overwrite=overwrites, reason="Removed from the ticket"
        )
        return await ctx.embed(f"{member.mention} has been **removed from this ticket**", "approved")

    @ticket.command(
        name="close",
        extras={"perms": "ticket support / manage channels"},
        brief="Check the server's ticket settings",
    )
    @manage_ticket()
    @get_ticket()
    @commands.bot_has_permissions(manage_channels=True)
    async def ticket_close(self, ctx: Context):
        """close the ticket"""
        await ctx.send(content="Deleting this channel in **5 seconds**")
        await asyncio.sleep(5)
        await ctx.channel.delete(reason="ticket closed")

    @ticket.command(
        name="reset",
        aliases=["disable"],
        extras={"perms": "manage server"},
        brief="Reset the ticket module. Will prevent existing ticket panels from working.",
    )
    @has_permissions(manage_guild=True)
    @ticket_exists()
    @commands.bot_has_permissions(manage_channels=True)
    async def ticket_reset(self, ctx: Context):
        """disable the ticket module in the server"""
        for i in ["tickets", "ticket_topics", "opened_tickets"]:
            await self.bot.db.execute(
                f"DELETE FROM {i} WHERE guild_id = $1", ctx.guild.id
            )

        await ctx.embed("**Tickets** has been `disabled`", "approved")

    @ticket.command(
        name="rename",
        brief="Rename a ticket",
        example=",ticket rename name, new-name",
    )
    @manage_ticket()
    @get_ticket()
    @commands.bot_has_permissions(manage_channels=True)
    @bot_has_permissions(manage_channels=True)
    async def ticket_rename(self, ctx: Context, *, name: str):
        """rename a ticket channel"""
        await ctx.channel.edit(
            name=name, reason=f"Ticket channel renamed by {ctx.author}"
        )
        await ctx.embed(f"**Ticket channel** has been **renamed** to `{name}`", "approved")

    @ticket.command(
        name="support",
        extras={"perms": "manage server"},
        brief="Set a default support role for tickets that have no topic roles assigned",
        example=",ticket support @mod",
    )
    @commands.bot_has_permissions(manage_channels=True)
    @has_permissions(manage_guild=True)
    @ticket_exists()
    async def ticket_support(self, ctx: Context, *, role: Role = None):
        """Configure the default support role for tickets without topic roles.
        This role will only have access to:
        1. Tickets created without a topic
        2. Topic tickets that have no specific roles assigned"""

        if role:
            check = await self.bot.db.fetchrow(
                "SELECT support_id FROM tickets WHERE guild_id = $1 AND support_id = $2",
                ctx.guild.id,
                role.id,
            )

            if check:
                return await ctx.embed(
                    f"{role.mention} is already set as the default support role",
                    message_type="warned"
                )

            await self.bot.db.execute(
                "UPDATE tickets SET support_id = $1 WHERE guild_id = $2",
                role.id,
                ctx.guild.id,
            )

            topics_without_roles = await self.bot.db.fetch(
                """
                SELECT tt.name 
                FROM ticket_topics tt
                LEFT JOIN ticket_topic_roles ttr ON tt.guild_id = ttr.guild_id 
                    AND tt.name = ttr.topic_name
                WHERE tt.guild_id = $1 
                    AND ttr.role_id IS NULL
                """,
                ctx.guild.id,
            )

            topic_list = (
                "\n".join([f"• {topic['name']}" for topic in topics_without_roles])
                if topics_without_roles
                else "None"
            )

            return await ctx.embed(
                f"{role.mention} has been set as the **default support role**\n\n"
                f"This role will have access to:\n"
                f"• Tickets created without a topic\n"
                f"• Topics with no specific roles assigned:\n{topic_list}",
                message_type="approved"
            )
        else:
            await self.bot.db.execute(
                "UPDATE tickets SET support_id = $1 WHERE guild_id = $2",
                None,
                ctx.guild.id,
            )
            return await ctx.embed(
                "**Default support role** has been removed\n"
                "Note: Topic-specific roles will still have access to their designated tickets",
                message_type="approved"
            )

    @ticket.command(
        name="category",
        extras={"perms": "manage server"},
        brief="Set a category where created tickets will be sent to",
        example=",ticket category create-a-ticket",
    )
    @commands.bot_has_permissions(manage_channels=True)
    @has_permissions(manage_guild=True)
    @ticket_exists()
    async def ticket_category(self, ctx: Context, *, category: CategoryChannel = None):
        """configure the category where the tickets should open"""
        if category:
            await self.bot.db.execute(
                "UPDATE tickets SET category_id = $1 WHERE guild_id = $2",
                category.id,
                ctx.guild.id,
            )
            return await ctx.embed(
                f"**Tickets opened will be created** under `#{category.name}`",
                message_type="approved"
            )
        else:
            await self.bot.db.execute(
                "UPDATE tickets SET category_id = $1 WHERE guild_id = $2",
                None,
                ctx.guild.id,
            )
            return await ctx.embed("**Removed** the **ticket creation category**", "approved")

    @ticket.command(
        name="message",
        extras={"perms": "manage server"},
        brief="Set a message to be sent when a ticket is opened",
        example=",ticket opened {embed_code}",
    )
    @commands.bot_has_permissions(manage_channels=True)
    @has_permissions(manage_guild=True)
    @ticket_exists()
    async def ticket_opened(self, ctx: Context, *, code: str = None):
        """set a message to be sent when a member opens a ticket"""
        await self.bot.db.execute(
            "UPDATE tickets SET open_embed = $1 WHERE guild_id = $2", code, ctx.guild.id
        )
        if code:
            return await ctx.embed(
                f"**Custom embed opening messag**e has been **set** to:\n```{code}```",
                message_type="approved"
            )
        else:
            return await ctx.embed(
                "**Custom ticket opening message** has been `reset`",
                message_type="approved"
            )

    @ticket.command(
        name="topics",
        brief="Assign topics to be chosen from before a user creates a ticket",
        example=",ticket topics",
    )
    @has_permissions(manage_guild=True)
    @ticket_exists()
    @commands.bot_has_permissions(manage_channels=True)
    async def ticket_topics(self, ctx: Context):
        """manage the ticket topics"""
        results = await self.bot.db.fetch(
            "SELECT * FROM ticket_topics WHERE guild_id = $1", ctx.guild.id
        )
        embed = Embed(color=Colors().information, description="🔍 Choose a setting")
        button1 = Button(label="add topic", style=ButtonStyle.gray)
        button2 = Button(
            label="remove topic", style=ButtonStyle.red, disabled=len(results) == 0
        )
        button4 = Button(
            label="manage topics", style=ButtonStyle.blurple, disabled=len(results) == 0
        )

        async def interaction_check(interaction: Interaction):
            if interaction.user != ctx.author:
                await interaction.warn(
                    "You are **not** the author of this message", ephemeral=True
                )
            return interaction.user == ctx.author

        async def button1_callback(interaction: Interaction):
            return await interaction.response.send_modal(TicketCategory())

        async def button2_callback(interaction: Interaction):
            e = Embed(
                color=Colors().information, description="🔍 Select a topic to delete"
            )
            options = [
                SelectOption(label=result[1], description=result[2])
                for result in results
            ]

            select = Select(options=options, placeholder="select a topic...")

            async def select_callback(inter: Interaction):
                topic_name = select.values[0]

                await self.bot.db.execute(
                    "DELETE FROM ticket_topics WHERE guild_id = $1 AND name = $2",
                    inter.guild.id,
                    topic_name,
                )
                await self.bot.db.execute(
                    "DELETE FROM ticket_topic_roles WHERE guild_id = $1 AND topic_name = $2",
                    inter.guild.id,
                    topic_name,
                )
                await self.bot.db.execute(
                    "DELETE FROM ticket_topic_categories WHERE guild_id = $1 AND topic_name = $2",
                    inter.guild.id,
                    topic_name,
                )

                await inter.response.edit_message(
                    embed=Embed(
                        color=Colors().information,
                        title="Topic Deleted",
                        description=f"Successfully deleted topic **{topic_name}** and all associated data",
                    ),
                    view=None,
                )

            select.callback = select_callback
            v = View()
            v.add_item(select)
            v.interaction_check = interaction_check
            return await interaction.response.edit_message(embed=e, view=v)

        async def button4_callback(interaction: Interaction):
            e = Embed(
                color=Colors().information, description="🔍 Select a topic to manage"
            )
            options = [
                SelectOption(label=result[1], description=result[2])
                for result in results
            ]

            select = Select(options=options, placeholder="select a topic...")

            async def select_callback(inter: Interaction):
                topic_name = select.values[0]

                topic_roles = await self.bot.db.fetch(
                    "SELECT role_id FROM ticket_topic_roles WHERE guild_id = $1 AND topic_name = $2",
                    inter.guild.id,
                    topic_name,
                )

                topic_category = await self.bot.db.fetchrow(
                    "SELECT category_id FROM ticket_topic_categories WHERE guild_id = $1 AND topic_name = $2",
                    inter.guild.id,
                    topic_name,
                )

                role_ids = [record["role_id"] for record in topic_roles]
                role_mentions = []

                for role_id in role_ids:
                    role = inter.guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)

                role_list = (
                    "\n".join(role_mentions) if role_mentions else "No roles assigned"
                )
                category_name = "None"
                if topic_category and topic_category["category_id"]:
                    category = inter.guild.get_channel(topic_category["category_id"])
                    if category:
                        category_name = category.name

                topic_embed = Embed(
                    color=Colors().information,
                    title=f"Topic Settings: {topic_name}",
                    description=f"Configure the settings for this ticket topic\n\n**Access Roles:**\n{role_list}\n\n**Category Channel:**\n{category_name}",
                )

                add_role = Button(label="Add Role", style=ButtonStyle.green)
                remove_role = Button(
                    label="Remove Role",
                    style=ButtonStyle.red,
                    disabled=len(role_ids) == 0,
                )
                set_category = Button(label="Set Category", style=ButtonStyle.blurple)
                back = Button(label="Back", style=ButtonStyle.gray)

                async def set_category_callback(interaction: Interaction):
                    modal = CategoryInputModal(
                        title=f"Set category for {topic_name}",
                        guild_id=interaction.guild.id,
                        topic_name=topic_name,
                    )
                    await interaction.response.send_modal(modal)

                async def add_role_callback(interaction: Interaction):
                    modal = RoleInputModal(
                        title=f"Add role to {topic_name}",
                        guild_id=interaction.guild.id,
                        topic_name=topic_name,
                    )
                    await interaction.response.send_modal(modal)

                async def remove_role_callback(interaction: Interaction):
                    if not role_ids:
                        return await interaction.response.send_message(
                            "No roles to remove.", ephemeral=True
                        )

                    options = []
                    for role_id in role_ids:
                        role = interaction.guild.get_role(role_id)
                        if role:
                            options.append(
                                SelectOption(
                                    label=role.name,
                                    value=str(role_id),
                                    description=f"Role ID: {role_id}",
                                )
                            )

                    if not options:
                        return await interaction.response.send_message(
                            "No valid roles found to remove.", ephemeral=True
                        )

                    role_select = Select(
                        options=options,
                        placeholder="Select a role to remove...",
                    )

                    async def role_select_callback(select_inter: Interaction):
                        selected_role_id = int(role_select.values[0])
                        role = select_inter.guild.get_role(selected_role_id)

                        await self.bot.db.execute(
                            "DELETE FROM ticket_topic_roles WHERE guild_id = $1 AND topic_name = $2 AND role_id = $3",
                            select_inter.guild.id,
                            topic_name,
                            selected_role_id,
                        )

                        role_name = (
                            role.name if role else f"Role (ID: {selected_role_id})"
                        )
                        await select_inter.response.send_message(
                            embed=Embed(
                                color=Colors().information,
                                title="Role Removed",
                                description=f"Removed **{role_name}** from topic **{topic_name}**",
                            ),
                            ephemeral=True,
                        )

                    role_select.callback = role_select_callback
                    role_view = View()
                    role_view.add_item(role_select)
                    role_view.interaction_check = interaction_check

                    await interaction.response.send_message(
                        embed=Embed(
                            color=Colors().information,
                            description="Select a role to remove from this topic",
                        ),
                        view=role_view,
                        ephemeral=True,
                    )

                async def back_callback(interaction: Interaction):
                    await interaction.response.edit_message(
                        embed=embed, view=original_view
                    )

                add_role.callback = add_role_callback
                remove_role.callback = remove_role_callback
                set_category.callback = set_category_callback
                back.callback = back_callback

                role_view = View()
                role_view.add_item(add_role)
                role_view.add_item(remove_role)
                role_view.add_item(set_category)
                role_view.add_item(back)
                role_view.interaction_check = interaction_check

                await inter.response.edit_message(embed=topic_embed, view=role_view)

            select.callback = select_callback
            v = View()
            v.add_item(select)
            v.interaction_check = interaction_check
            return await interaction.response.edit_message(embed=e, view=v)

        button1.callback = button1_callback
        button2.callback = button2_callback
        button4.callback = button4_callback
        original_view = View()
        original_view.add_item(button1)
        original_view.add_item(button2)
        original_view.add_item(button4)
        original_view.interaction_check = interaction_check
        await ctx.reply(embed=embed, view=original_view)

    @ticket.command(
        name="settings",
        aliases=["config"],
        brief="Check the server's configured ticket settings",
    )
    @commands.bot_has_permissions(manage_channels=True)
    async def ticket_config(self, ctx: Context):
        """check the server's ticket settings"""
        check = await self.bot.db.fetchrow(
            "SELECT * FROM tickets WHERE guild_id = $1", ctx.guild.id
        )

        if not check:
            return await ctx.embed("Ticket module is **not** enabled in this server", "warned")

        results = await self.bot.db.fetch(
            "SELECT * FROM ticket_topics WHERE guild_id = $1", ctx.guild.id
        )

        support = f"<@&{check['support_id']}>" if check["support_id"] else "none"
        embed = Embed(
            color=Colors().information,
            title="Ticket Settings",
            description=f"Support role: {support}",
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon)
        embed.add_field(
            name="Channel Category",
            value=f"<#{check['category_id']}>" if check["category_id"] else "none",
            inline=False,
        )
        embed.add_field(name="Categories", value=str(len(results)), inline=False)
        embed.add_field(
            name="opening ticket embed",
            value=f"```\n{check['open_embed']}```",
            inline=False,
        )
        await ctx.reply(embed=embed)

    @ticket.command(
        name="setup",
        brief="Setup the ticket panel to send to a channel",
        example=",ticket setup #tickets",
        parameters={
            "delete": {
                "converter": Emojis,
                "description": "the delete ticket emoji",
                "default": None,
            },
            "open": {
                "converter": Emojis,
                "description": "the open ticket emoji",
                "default": None,
            },
            "code": {
                "converter": str,
                "description": "the embed code",
                "aliases": ("embed",),
                "default": "{embed}{color: #2b2d31}$v{title: Create a ticket}$v{description: Click on the button below this message to create a ticket}",
            },
        },
    )
    @commands.bot_has_permissions(manage_channels=True)
    @has_permissions(manage_guild=True)
    @ticket_exists()
    async def ticket_setup(
        self,
        ctx: Context,
        channel: TextChannel,
    ):
        """setup and send the ticket panel to a channel"""
        self.bot.cw = ctx
        code = (
            ctx.parameters.get("code")
            or ctx.parameters.get("embed")
            or "{embed}{color: #2b2d31}$v{title: Create a ticket}$v{description: Click on the button below this message to create a ticket}"
        )
        delete_emoji = ctx.parameters.get("delete")
        if delete_emoji:
            delete_emoji = await delete_emoji
        open_emoji = ctx.parameters.get("open")
        if open_emoji:
            open_emoji = await open_emoji
        if delete_emoji and open_emoji:
            await self.bot.db.execute(
                """UPDATE tickets SET delete_emoji = $1, open_emoji = $2 WHERE guild_id = $3""",
                str(delete_emoji[0]),
                str(open_emoji[0]),
                ctx.guild.id,
            )
        elif delete_emoji:
            await self.bot.db.execute(
                """UPDATE tickets SET delete_emoji = $1 WHERE guild_id = $2""",
                str(delete_emoji[0]),
                ctx.guild.id,
            )
        elif open_emoji:
            await self.bot.db.execute(
                """UPDATE tickets SET open_emoji = $1 WHERE guild_id = $2""",
                str(open_emoji[0]),
                ctx.guild.id,
            )

        view = TicketView(self.bot, ctx.guild.id)
        await view.setup()
        view.create_ticket()
        self.bot.view_ = view
        message = await self.bot.send_embed(channel, code, user=ctx.author, view=view)
        await self.bot.db.execute(
            """UPDATE tickets SET message_id = $1 WHERE guild_id = $2""",
            message.id,
            ctx.guild.id,
        )
        return await ctx.embed(
            f"**Ticket channel** has been **set** to {channel.mention}",
            message_type="approved"
        )

    @ticket.command(
        name="send",
        brief="Send the ticket panel to a channel without changing configuration",
        example=",ticket send #tickets",
    )
    @commands.bot_has_permissions(manage_channels=True)
    @has_permissions(manage_guild=True)
    @ticket_exists()
    async def ticket_send(
        self,
        ctx: Context,
        channel: TextChannel,
    ):
        check = await self.bot.db.fetchrow(
            "SELECT * FROM tickets WHERE guild_id = $1", ctx.guild.id
        )

        if not check:
            return await ctx.embed("Please set up tickets first using the setup command", "warned")

        view = TicketView(self.bot, ctx.guild.id)
        await view.setup()
        view.create_ticket()

        embed_code = (
            check.get("open_embed")
            or "{embed}{color: #2b2d31}$v{title: Create a ticket}$v{description: Click on the button below this message to create a ticket}"
        )

        message = await self.bot.send_embed(
            channel, embed_code, user=ctx.author, view=view
        )
        await self.bot.db.execute(
            """UPDATE tickets SET message_id = $1 WHERE guild_id = $2""",
            message.id,
            ctx.guild.id,
        )
        return await ctx.embed(f"**Ticket panel** has been sent to {channel.mention}", "approved")


class RoleInputModal(Modal):
    def __init__(self, title: str, guild_id: int, topic_name: str):
        super().__init__(title=title)
        self.guild_id = guild_id
        self.topic_name = topic_name

        self.role_id = TextInput(
            label="Role ID",
            placeholder="Enter the role ID",
            required=True,
            style=TextStyle.short,
        )

        self.add_item(self.role_id)

    async def on_submit(self, interaction: Interaction):
        try:
            role_id = int(self.role_id.value)
            role = interaction.guild.get_role(role_id)

            if not role:
                return await interaction.response.send_message(
                    f"Role with ID {role_id} not found.", ephemeral=True
                )

            existing = await interaction.client.db.fetchrow(
                "SELECT * FROM ticket_topic_roles WHERE guild_id = $1 AND topic_name = $2 AND role_id = $3",
                self.guild_id,
                self.topic_name,
                role_id,
            )

            if existing:
                return await interaction.response.send_message(
                    f"Role {role.mention} is already assigned to this topic.",
                    ephemeral=True,
                )

            await interaction.client.db.execute(
                "INSERT INTO ticket_topic_roles (guild_id, topic_name, role_id) VALUES ($1, $2, $3)",
                self.guild_id,
                self.topic_name,
                role_id,
            )

            await interaction.response.send_message(
                f"Added {role.mention} to topic **{self.topic_name}**", ephemeral=True
            )

        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid role ID.", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True
            )


class CategoryInputModal(Modal):
    def __init__(self, title: str, guild_id: int, topic_name: str):
        super().__init__(title=title)
        self.guild_id = guild_id
        self.topic_name = topic_name

        self.category_id = TextInput(
            label="Category ID",
            placeholder="Enter the category channel ID",
            required=True,
            style=TextStyle.short,
            min_length=16,
            max_length=20,
        )

        self.add_item(self.category_id)

    async def on_submit(self, interaction: Interaction):
        try:
            category_id = int(self.category_id.value)
            category = interaction.guild.get_channel(category_id)

            if not category or not isinstance(category, CategoryChannel):
                return await interaction.response.send_message(
                    f"Category with ID {category_id} not found or is not a category channel.",
                    ephemeral=True,
                )

            bot_member = interaction.guild.get_member(interaction.client.user.id)
            if not category.permissions_for(bot_member).manage_channels:
                return await interaction.response.send_message(
                    f"I don't have permission to manage channels in the category {category.name}.",
                    ephemeral=True,
                )

            await interaction.client.db.execute(
                """
                INSERT INTO ticket_topic_categories (guild_id, topic_name, category_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id, topic_name)
                DO UPDATE SET category_id = $3
                """,
                self.guild_id,
                self.topic_name,
                category_id,
            )

            await interaction.response.send_message(
                f"Set category to **{category.name}** for topic **{self.topic_name}**",
                ephemeral=True,
            )

        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid category ID (numbers only).", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True
            )


async def setup(bot: Greed) -> None:
    await bot.add_cog(Tickets(bot))
