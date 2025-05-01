from io import BytesIO
from typing import List

from discord import (AuditLogEntry, Client, Embed, File, Guild, Interaction,
                     Member, Message, TextChannel, Thread, User, ui, utils)
from discord.ext.commands import (Cog, CommandError, command, group,
                                  has_permissions)


class LogsView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Copy ID", custom_id="id")
    async def obj_id(self, interaction: Interaction, _):
        return await interaction.response.send_message(
            interaction.message.embeds[0].footer.text, ephemeral=True
        )


class LogsEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

        self.bot.add_view(LogsView())

    @Cog.listener("on_audit_log_entry_create")
    async def automod_events(self, entry: AuditLogEntry):
        if entry.action.name in ["automod_rule_create", "automod_rule_delete"]:
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "automod",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            title=entry.action.name.replace("_", " ").title(),
                            description=f"Automod Rule **{entry.target.name}** {entry.action.name.split('_')[-1]}d by **{entry.user}** (`{entry.user.id}`)",
                            timestamp=entry.created_at,
                        )
                        .set_author(
                            name=str(entry.user), icon_url=entry.user.display_avatar.url
                        )
                        .set_footer(text=f"Rule id: {entry.target.id}")
                    )
                    return await channel.send(silent=True, embed=embed, view=LogsView())
        elif entry.action.name == "automod_rule_update":
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "automod",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            description=f"**{entry.target.name}** (`{entry.target.id}`)",
                            timestamp=entry.created_at,
                        )
                        .set_author(
                            name=str(entry.user), icon_url=entry.user.display_avatar.url
                        )
                        .set_footer(text=f"Rule id: {entry.target.id}")
                    )

                    if getattr(entry.changes.before, "name", None):
                        if entry.changes.before.name != entry.changes.after.name:
                            embed.title = "Automod Rule name update"
                            embed.add_field(
                                name="Before",
                                value=entry.changes.before.name,
                                inline=False,
                            ).add_field(
                                name="After",
                                value=entry.changes.after.name,
                                inline=False,
                            )
                            return await channel.send(
                                silent=True, embed=embed, view=LogsView()
                            )
                    elif getattr(entry.changes.before, "enabled", None):
                        if entry.changes.before.enabled != entry.changes.after.enabled:
                            embed.title = (
                                "Automod Rule disabled"
                                if entry.changes.before.enabled
                                else "Automod Rule enabled"
                            )
                            return await channel.send(
                                silent=True, embed=embed, view=LogsView()
                            )

    @Cog.listener("on_audit_log_entry_create")
    async def role_events(self, entry: AuditLogEntry):
        if entry.action.name in ["role_create", "role_delete"]:
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "roles",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            title=entry.action.name.replace("_", " ").title(),
                            description=f"<@&{entry.target.id}> (`{entry.target.id}`) {entry.action.name.split('_')[1]}d by **{entry.user}** (`{entry.user.id}`)",
                            timestamp=entry.created_at,
                        )
                        .set_author(
                            name=str(entry.user), icon_url=entry.user.display_avatar.url
                        )
                        .set_footer(text=f"Role id: {entry.target.id}")
                    )
                    return await channel.send(silent=True, embed=embed, view=LogsView())
        elif entry.action.name == "role_update":
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "roles",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(color=self.bot.color, timestamp=entry.created_at)
                        .set_author(
                            name=str(entry.user), icon_url=entry.user.display_avatar.url
                        )
                        .set_footer(text=f"Role id: {entry.target.id}")
                    )

                    if getattr(entry.changes.before, "name", None):
                        if entry.changes.before.name != entry.changes.after.name:
                            embed.title = "Role name update"
                            embed.add_field(
                                name="Before",
                                value=entry.changes.before.name,
                                inline=False,
                            ).add_field(
                                name="After",
                                value=entry.changes.after.name,
                                inline=False,
                            )
                    elif str(getattr(entry.changes.before, "color", "#000000")) != str(
                        getattr(entry.changes.after, "color", "#000000")
                    ):
                        embed.title = "Role color update"
                        embed.add_field(
                            name="Before",
                            value=str(
                                getattr(entry.changes.before, "color", "#000000")
                            ),
                            inline=False,
                        ).add_field(
                            name="After",
                            value=str(getattr(entry.changes.after, "color", "#000000")),
                            inline=False,
                        )

    @Cog.listener("on_audit_log_entry_create")
    async def thread_events(self, entry: AuditLogEntry):
        if entry.action.name in ["thread_create", "thread_delete"]:
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "channels",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            title=entry.action.name.replace("_", " ").title(),
                            description=f"<#{entry.target.id}> (`{entry.target.id}`) {entry.action.name.split('_')[1]}d by **{entry.user}** (`{entry.user.id}`)",
                            timestamp=entry.created_at,
                        )
                        .set_author(
                            name=str(entry.user), icon_url=entry.user.display_avatar.url
                        )
                        .set_footer(text=f"Thread id: {entry.target.id}")
                    )
                    return await channel.send(silent=True, embed=embed, view=LogsView())
            elif entry.action.name == "thread_update":
                if channel_id := await self.bot.db.fetchval(
                    """
                    SELECT channel_id FROM logs
                    WHERE guild_id = $1 
                    AND log_type = $2
                    """,
                    entry.guild.id,
                    "channels",
                ):
                    if channel := entry.guild.get_channel(channel_id):
                        embed = (
                            Embed(color=self.bot.color, timestamp=entry.created_at)
                            .set_author(
                                name=str(entry.user),
                                icon_url=entry.user.display_avatar.url,
                            )
                            .set_footer(text=f"Thread id: {entry.target.id}")
                        )

                        if getattr(entry.changes.before, "name", None):
                            if entry.changes.before.name != entry.changes.after.name:
                                embed.title = "Thread name update"
                                embed.add_field(
                                    name="Before",
                                    value=entry.changes.before.name,
                                    inline=False,
                                ).add_field(
                                    name="After",
                                    value=entry.changes.after.name,
                                    inline=False,
                                )

                                return await channel.send(
                                    silent=True, embed=embed, view=LogsView()
                                )
                        elif hasattr(entry.changes.before, "locked"):
                            if (
                                entry.changes.before.locked
                                != entry.changes.after.locked
                            ):
                                embed.title = "Thread lock update"
                                embed.add_field(
                                    name="Before",
                                    value=entry.changes.before.locked,
                                    inline=False,
                                ).add_field(
                                    name="After",
                                    value=entry.changes.after.locked,
                                    inline=False,
                                )

                                return await channel.send(
                                    silent=True, embed=embed, view=LogsView()
                                )

    @Cog.listener("on_audit_log_entry_create")
    async def channel_events(self, entry: AuditLogEntry):
        if entry.action.name in ["channel_create", "channel_delete"]:
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "channels",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            title=entry.action.name.replace("_", " ").title(),
                            description=f"<#{entry.target.id}> (`{entry.target.id}`) {entry.action.name.split('_')[1]}d by **{entry.user}** (`{entry.user.id}`)",
                            timestamp=entry.created_at,
                        )
                        .set_author(
                            name=str(entry.user), icon_url=entry.user.display_avatar.url
                        )
                        .set_footer(text=f"Channel id: {entry.target.id}")
                    )
                    return await channel.send(silent=True, embed=embed, view=LogsView())
        elif entry.action.name == "channel_update":
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "channels",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(color=self.bot.color, timestamp=entry.created_at)
                        .set_author(
                            name=str(entry.user), icon_url=entry.user.display_avatar.url
                        )
                        .set_footer(text=f"Channel id: {entry.target.id}")
                    )

                    if getattr(entry.changes.before, "name", None):
                        if entry.changes.before.name != entry.changes.after.name:
                            embed.title = "Channel name update"
                            embed.add_field(
                                name="Before",
                                value=entry.changes.before.name,
                                inline=False,
                            ).add_field(
                                name="After",
                                value=entry.changes.after.name,
                                inline=False,
                            )

                            return await channel.send(
                                silent=True, embed=embed, view=LogsView()
                            )

    @Cog.listener("on_audit_log_entry_create")
    async def member_events(self, entry: AuditLogEntry):
        if entry.action.name == "member_update":
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "members",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            description=f"Moderator: **{entry.user}** (`{entry.user.id}`)",
                            timestamp=entry.created_at,
                        )
                        .set_author(
                            name=str(entry.target),
                            icon_url=entry.target.display_avatar.url,
                        )
                        .set_footer(text=f"User id: {entry.target.id}")
                    )
                    if getattr(
                        entry.changes.before, "timed_out_until", None
                    ) != getattr(entry.changes.after, "timed_out_until", None):
                        if not entry.changes.after.timed_out_until:
                            embed.title = "Removed timeout"
                        else:
                            embed.title = "Timed out Member"
                            embed.add_field(
                                name="Timed out until",
                                value=utils.format_dt(
                                    entry.changes.after.timed_out_until
                                ),
                            )

                        return await channel.send(
                            silent=True, embed=embed, view=LogsView()
                        )

                    elif getattr(entry.changes.before, "nick", None) != getattr(
                        entry.changes.after, "nick", None
                    ):
                        if not entry.changes.before.nick:
                            embed.title = "Configured Nickname"
                            embed.add_field(
                                name="Nickname",
                                value=entry.changes.after.nick,
                                inline=False,
                            )
                        elif not entry.changes.after.nick:
                            embed.title = "Removed nickname"
                            embed.add_field(
                                name="Nickname",
                                value=entry.changes.before.nick,
                                inline=False,
                            )
                        else:
                            embed.title = "Nickname Update"
                            embed.add_field(
                                name="Before",
                                value=entry.changes.before.nick,
                                inline=False,
                            ).add_field(
                                name="After",
                                value=entry.changes.after.nick,
                                inline=False,
                            )

                        return await channel.send(
                            silent=True, embed=embed, view=LogsView()
                        )

        elif entry.action.name == "member_role_update":
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "members",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            title=entry.action.name.replace("_", " ").title(),
                            timestamp=entry.created_at,
                        )
                        .set_author(
                            name=entry.target.__str__(),
                            icon_url=entry.target.display_avatar.url,
                        )
                        .add_field(
                            name="Moderator",
                            value=f"**{entry.user}** (`{entry.user.id}`)",
                            inline=False,
                        )
                        .add_field(
                            name="Victim",
                            value=f"**{entry.target}** (`{entry.target.id}`)",
                            inline=False,
                        )
                        .set_footer(text=f"User id: {entry.target.id}")
                    )

                    removed = [
                        role
                        for role in entry.changes.before.roles
                        if role not in entry.changes.after.roles
                    ]

                    added = [
                        role
                        for role in entry.changes.after.roles
                        if role not in entry.changes.before.roles
                    ]

                    rem = f"... +{len(removed)-5}" if len(removed) > 5 else ""
                    add = f"... +{len(added)-5}" if len(added) > 5 else ""

                    if removed:
                        embed.add_field(
                            name=f"Removed roles ({len(removed)})",
                            value=", ".join(list(map(lambda r: r.mention, removed[:5])))
                            + rem,
                            inline=False,
                        )

                    if added:
                        embed.add_field(
                            name=f"Added roles ({len(added)})",
                            value=", ".join(list(map(lambda r: r.mention, added[:5])))
                            + add,
                            inline=False,
                        )

                    return await channel.send(silent=True, embed=embed, view=LogsView())

    @Cog.listener("on_audit_log_entry_create")
    async def ban_kick(self, entry: AuditLogEntry):
        if entry.action.name in ["ban", "kick", "unban"]:
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "members",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            title=f"Member {entry.action.name.capitalize()}",
                            timestamp=entry.created_at,
                        )
                        .set_author(
                            name=entry.target.__str__(),
                            icon_url=entry.target.display_avatar.url,
                        )
                        .add_field(
                            name="Moderator",
                            value=f"**{entry.user}** (`{entry.user.id}`)",
                            inline=False,
                        )
                        .add_field(
                            name="Victim",
                            value=f"**{entry.target}** (`{entry.target.id}`)",
                            inline=False,
                        )
                        .add_field(
                            name="Reason",
                            value=entry.reason or "No reason",
                            inline=False,
                        )
                        .set_footer(text=f"User id: {entry.target.id}")
                    )

                    return await channel.send(silent=True, embed=embed, view=LogsView())
        elif entry.action.name == "bot_add":
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                entry.guild.id,
                "members",
            ):
                if channel := entry.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            title="Bot added to the server",
                            description=f"**{entry.user}** (`{entry.user.id}`) added **{entry.target}** (`{entry.target.id}`) in the server",
                        )
                        .set_author(
                            name=str(entry.user), icon_url=entry.user.display_avatar.url
                        )
                        .set_footer(text=f"Bot id: {entry.target.id}")
                    )
                    return await channel.send(silent=True, embed=embed, view=LogsView())

    @Cog.listener()
    async def on_member_remove(self, member: Member):
        if channel_id := await self.bot.db.fetchval(
            """
            SELECT channel_id FROM logs
            WHERE guild_id = $1 
            AND log_type = $2
            """,
            member.guild.id,
            "members",
        ):
            if channel := member.guild.get_channel(channel_id):
                embed = (
                    Embed(
                        color=self.bot.color,
                        title="Member left",
                        description=f"{member} (`{member.id}`) left the server. This server has `{member.guild.member_count:,}` members now!",
                        timestamp=utils.utcnow(),
                    )
                    .set_author(name=str(member), icon_url=member.display_avatar.url)
                    .set_footer(text=f"User id: {member.id}")
                    .add_field(
                        name="Joined At",
                        value=utils.format_dt(member.joined_at),
                        inline=False,
                    )
                    .add_field(
                        name="Created at",
                        value=utils.format_dt(member.created_at),
                        inline=False,
                    )
                )

                return await channel.send(silent=True, embed=embed, view=LogsView())

    @Cog.listener()
    async def on_member_join(self, member: Member):
        if channel_id := await self.bot.db.fetchval(
            """
            SELECT channel_id FROM logs
            WHERE guild_id = $1 
            AND log_type = $2
            """,
            member.guild.id,
            "members",
        ):
            if channel := member.guild.get_channel(channel_id):
                embed = (
                    Embed(
                        color=self.bot.color,
                        title="Member Joined",
                        description=f"{member} (`{member.id}`) joined the server. This server has `{member.guild.member_count:,}` members now!",
                        timestamp=utils.utcnow(),
                    )
                    .set_author(name=str(member), icon_url=member.display_avatar.url)
                    .set_footer(text=f"User id: {member.id}")
                    .add_field(
                        name="Created at",
                        value=utils.format_dt(member.created_at),
                    )
                )

                return await channel.send(silent=True, embed=embed, view=LogsView())

    @Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        if after.guild:
            if before != after:
                if before.content != "" and after.content != "":
                    if channel_id := await self.bot.db.fetchval(
                        """
                        SELECT channel_id FROM logs
                        WHERE guild_id = $1 
                        AND log_type = $2
                        """,
                        after.guild.id,
                        "messages",
                    ):
                        if channel := after.guild.get_channel(channel_id):
                            embed = (
                                Embed(
                                    color=self.bot.color,
                                    title=f"Message edited in #{after.channel}",
                                    timestamp=utils.utcnow(),
                                )
                                .set_author(
                                    name=after.author.__str__(),
                                    icon_url=after.author.display_avatar.url,
                                )
                                .set_footer(text=f"Message id: {after.id}")
                                .add_field(
                                    name="Before", value=before.content, inline=False
                                )
                                .add_field(
                                    name="After", value=after.content, inline=False
                                )
                            )

                            return await channel.send(
                                silent=True, embed=embed, view=LogsView()
                            )

    @Cog.listener()
    async def on_message_delete(self, message: Message):
        if message.guild:
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                message.guild.id,
                "messages",
            ):
                if channel := message.guild.get_channel(channel_id):
                    embed = (
                        Embed(
                            color=self.bot.color,
                            title=f"Message Delete in #{message.channel}",
                            description=(
                                message.content
                                if message.content != ""
                                else "This message doesn't have content"
                            ),
                            timestamp=message.created_at,
                        )
                        .set_author(
                            name=message.author.__str__(),
                            icon_url=message.author.display_avatar.url,
                        )
                        .set_footer(text=f"User id: {message.author.id}")
                    )
                    return await channel.send(silent=True, embed=embed, view=LogsView())

    @Cog.listener()
    async def on_bulk_message_delete(self, messages: List[Message]):
        message = messages[0]
        if message.guild:
            if channel_id := await self.bot.db.fetchval(
                """
                SELECT channel_id FROM logs
                WHERE guild_id = $1 
                AND log_type = $2
                """,
                message.guild.id,
                "messages",
            ):
                if channel := message.guild.get_channel(channel_id):
                    embed = Embed(
                        color=self.bot.color,
                        title=f"Bulk Message Delete in #{message.channel}",
                        timestamp=utils.utcnow(),
                    ).set_author(name=message.guild.name, icon_url=message.guild.icon)
                    buffer = BytesIO(
                        bytes(
                            "\n".join(
                                f"{m.author} - {m.clean_content if m.clean_content != '' else 'Attachment, Embed or Sticker'}"
                                for m in messages
                            ),
                            "utf-8",
                        )
                    )
                    return await channel.send(
                        silent=True,
                        embed=embed,
                        file=File(buffer, filename=f"{message.channel}.txt"),
                    )


async def setup(bot: Client):
    await bot.add_cog(LogsEvents(bot))
