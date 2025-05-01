from __future__ import annotations

from asyncio import Lock
from collections import defaultdict
from contextlib import suppress
from datetime import timedelta
from io import BytesIO
from logging import getLogger
from typing import (
    Optional,
    Sequence,
    TypedDict,
    Union,
    cast,
)
from humanfriendly import format_timespan
from cashews import cache

from discord import (
    Asset,
    AuditLogEntry,
    Color,
    DMChannel,
    Embed,
    Emoji,
    File,
    GroupChannel,
    Guild,
    GuildSticker,
    HTTPException,
    Invite,
    Member,
    Message,
    Object,
    PartialMessageable,
    Role,
    TextChannel,
    Thread,
    User,
    VoiceState,
    Webhook,
    VoiceChannel,
    ForumChannel,
    StageChannel,
)
from discord.abc import GuildChannel
from discord.ext.commands import Cog, group, has_permissions
from discord.ext.tasks import loop
from discord.utils import (
    MISSING,
    as_chunks,
    format_dt,
    utcnow,
)
from discord.webhook import WebhookMessage

from .enums import LogType
from greed.framework import Greed, Context
from greed.framework.tools.formatter import (
    plural,
    human_join,
)

logger = getLogger("greed/plugins/config/logging")


class Record(TypedDict):
    guild_id: int
    channel_id: int
    events: list[str]


queued_messages: dict[
    TextChannel | Thread,
    list[tuple[Embed, Optional[Sequence[File]]]],
] = defaultdict(list)
queue_lock = Lock()

webhooks: dict[int, Webhook] = {}


@cache(ttl="10m", key="webhook:channel:logs:{channel_id}")
async def get_webhook_id(
    bot: Greed, channel_id: int
) -> Optional[int]:
    """
    Get a webhook ID from the database.
    """
    return await bot.pool.fetchval(
        """
        SELECT webhook_id 
        FROM logging 
        WHERE channel_id = $1
        """,
        channel_id,
    )


async def get_or_create_webhook(
    bot: Greed, channel: TextChannel | Thread
) -> Webhook:
    """
    Get an existing webhook or create a new one for the channel.
    """
    if channel.id in webhooks:
        return webhooks[channel.id]

    webhook_id = await get_webhook_id(bot, channel.id)

    if webhook_id:
        with suppress(HTTPException):
            webhook = await bot.fetch_webhook(webhook_id)
            webhooks[channel.id] = webhook
            return webhook

    with suppress(HTTPException):
        avatar_bytes = (
            await channel.guild.me.avatar.read()
        )
        webhook = await channel.create_webhook(
            name=f"{channel.guild.me.name} Logs",
            avatar=avatar_bytes,
            reason="Creating logging webhook",
        )
        webhooks[channel.id] = webhook

        await bot.pool.execute(
            """
            UPDATE logging
            SET webhook_id = $2
            WHERE channel_id = $1
            """,
            channel.id,
            webhook.id,
        )
        return webhook


async def is_ignored(
    bot: Greed, guild_id: int, target_id: int
) -> bool:
    """
    Check if a target is ignored in the guild.
    """
    return (
        await bot.pool.fetchval(
            """
        SELECT * FROM ignored_logging 
        WHERE guild_id = $1 
        AND target_id = $2
        """,
            guild_id,
            target_id,
        )
        is not None
    )


async def log(
    event: LogType,
    guild: Guild,
    embed: Optional[Embed] = None,
    *,
    user: Optional[Member | User] = None,
    files: Sequence[File] = MISSING,
) -> Optional[WebhookMessage]:
    """
    Send a log to the appropriate channel.
    """
    bot = cast(Greed, guild._state._get_client())
    if not guild.me:
        logger.warning(f"Guild {guild.id} has no bot member, skipping log")
        return

    if user and await is_ignored(bot, guild.id, user.id):
        logger.debug(f"User {user.id} is ignored in guild {guild.id}, skipping log")
        return

    channel_id = cast(
        Optional[int],
        await bot.pool.fetchval(
            """
            SELECT channel_id
            FROM logging
            WHERE guild_id = $1 AND $2 = ANY(events)
            """,
            guild.id,
            event.name,
        ),
    )
    if not channel_id:
        logger.debug(f"No logging channel found for event {event.name} in guild {guild.id}")
        return

    channel = cast(
        Optional[TextChannel | Thread],
        guild.get_channel_or_thread(channel_id),
    )
    if not channel:
        logger.warning(f"Logging channel {channel_id} not found in guild {guild.id}, removing from database")
        await bot.pool.execute(
            """
            DELETE FROM logging 
            WHERE guild_id = $1 
            AND channel_id = $2
            """,
            guild.id,
            channel_id,
        )
        return

    if await is_ignored(bot, guild.id, channel.id):
        logger.debug(f"Channel {channel.id} is ignored in guild {guild.id}, skipping log")
        return

    elif not all((
        channel.permissions_for(guild.me).send_messages,
        channel.permissions_for(guild.me).embed_links,
        channel.permissions_for(guild.me).attach_files,
    )):
        logger.warning(f"Bot missing required permissions in channel {channel.id} for logging")
        return

    elif not embed:
        logger.warning("No embed provided for logging")
        return

    if user and not embed.author:
        embed.set_author(
            name=user, icon_url=user.avatar
        )
        if not embed.footer:
            embed.set_footer(
                text=f"{user.__class__.__name__} ID: {user.id}"
            )

    if not embed.timestamp:
        embed.timestamp = utcnow()

    if files:
        try:
            webhook = await get_or_create_webhook(bot, channel)
            if not webhook:
                logger.error(f"Failed to get/create webhook for channel {channel.id}")
                return
            logger.debug(f"Sending log with files to webhook {webhook.id}")
            return await webhook.send(
                embed=embed, files=files, silent=True
            )
        except Exception as e:
            logger.error(f"Failed to send webhook message: {e}")
            return

    async with queue_lock:
        queued_messages[channel].append((
            embed,
            files if files is not MISSING else None,
        ))
        logger.debug(f"Queued log for channel {channel.id}, queue size: {len(queued_messages[channel])}")

    logger.info(
        f"Queued {event.name} log for {guild} in {channel} / {plural(len(queued_messages[channel])):message} queued"
    )


class Logging(Cog):
    """
    Log actions happening within the guild.
    """

    def __init__(self, bot: Greed):
        self.bot = bot
        self.send_queued_log_messages.start()

    async def cog_load(self) -> None:
        return await super().cog_load()

    async def cog_unload(self) -> None:
        self.send_queued_log_messages.cancel()
        return await super().cog_unload()

    @loop(seconds=2)
    async def send_queued_log_messages(self):
        if not queued_messages:
            return

        async with queue_lock:
            total_messages = sum(map(len, queued_messages.values()))
            if total_messages > 50:
                logger.warning(f"Dispatching {total_messages} queued log messages")

            for channel, records in queued_messages.copy().items():
                try:
                    webhook = await get_or_create_webhook(self.bot, channel)
                    if not webhook:
                        logger.error(f"Failed to get/create webhook for channel {channel.id}")
                        continue

                    for chunk in as_chunks(records, 10):
                        embeds = []
                        all_files = []
                        for embed, files in chunk:
                            if embed:
                                embeds.append(embed)
                            if files:
                                all_files.extend(files)

                        if embeds:
                            logger.debug(f"Sending {len(embeds)} embeds to webhook {webhook.id}")
                            await webhook.send(
                                embeds=embeds,
                                files=all_files or MISSING,
                                silent=True,
                                username=f"{self.bot.user.name} Logs",
                            )
                except Exception as e:
                    logger.error(f"Failed to send webhook message: {e}")
                    continue
            queued_messages.clear()

    @group(
        name="logs",
        example="add #logs all",
        aliases=("log",),
        usage="<subcommand> <channel> <events>",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def logs(self, ctx: Context) -> Message:
        """
        Set up logging for your community.
        """
        return await ctx.send_help(ctx.command)

    @logs.command(
        name="add",
        aliases=("set", "enable"),
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def logs_add(
        self,
        ctx: Context,
        channel: TextChannel,
        *event_names: str,
    ) -> Message:
        """
        Set up logging in a channel.
        """
        if not event_names:
            return await ctx.send_help(ctx.command)

        valid_events = []
        invalid_events = []

        if "all" in event_names:
            valid_events = LogType.all()
        else:
            for event_name in event_names:
                try:
                    if (
                        event_name.upper()
                        in LogType.__members__
                    ):
                        event = LogType.from_str(event_name)
                        valid_events.append(event)
                    else:
                        invalid_events.append(event_name)
                except (
                    KeyError,
                    ValueError,
                    AttributeError,
                ):
                    invalid_events.append(event_name)

        if invalid_events:
            return await ctx.embed(
                f"**Invalid event types**: {', '.join(f'`{e}`' for e in invalid_events)}\n"
                f"Valid options are: {', '.join(f'`{e.lower()}`' for e in LogType.all())}.",
                message_type="warned",
            )

        record = await self.bot.pool.fetchrow(
            """
            SELECT * FROM logging 
            WHERE guild_id = $1 
            AND channel_id = $2
            """,
            ctx.guild.id,
            channel.id,
        )
        if record:
            for event in record["events"]:
                event = LogType.from_str(event)
                if event not in valid_events:
                    valid_events.append(event)

        await self.bot.pool.execute(
            """
            INSERT INTO logging (guild_id, channel_id, events)
            VALUES ($1, $2, $3) ON CONFLICT (guild_id, channel_id) DO UPDATE
            SET events = EXCLUDED.events
            """,
            ctx.guild.id,
            channel.id,
            [event.name for event in valid_events],
        )

        if "all" in event_names:
            event_text = ", ".join(
                f"`{event}`" for event in valid_events
            )
        elif len(event_names) == 1:
            event_text = f"`{valid_events[0]}`"
        else:
            event_text = ", ".join(
                f"`{event}`" for event in valid_events
            )

        return await ctx.embed(
            f"**Event** {' ' if len(event_names) == 1 else 's '}{event_text} will now be **logged** in {channel.mention}",
            message_type="approved",
        )

    @logs.command(name="list")
    @has_permissions(manage_guild=True)
    async def logs_list(self, ctx: Context) -> Message:
        """
        View all logging channels and their events.
        """
        records = await self.bot.pool.fetch(
            """
            SELECT channel_id, events 
            FROM logging WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        if not records:
            return await ctx.embed(
                "No **logging channels** have been set up",
                message_type="warned",
            )

        entries = []
        for record in records:
            channel = ctx.guild.get_channel(
                record["channel_id"]
            )
            if not channel:
                continue

            events = [
                LogType.from_str(event)
                for event in record["events"]
            ]
            events_str = ", ".join(
                f"`{event}`" for event in events
            )
            entries.append(
                f"{channel.mention}: \n > {events_str}"
            )

        embed = Embed(title="Logging Channels")
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.avatar.url,
        )

        return await ctx.paginate(
            embed=embed, entries=entries
        )

    @logs.group(name="ignore", invoke_without_command=True)
    @has_permissions(manage_guild=True)
    async def logs_ignore(
        self,
        ctx: Context,
        member_or_channel: Union[
            TextChannel,
            VoiceChannel,
            ForumChannel,
            StageChannel,
            Member,
        ],
    ) -> Message:
        """
        Toggle ignore status for a member or channel.
        """
        record = await self.bot.pool.fetchval(
            """
                SELECT * FROM ignored_logging 
                WHERE guild_id = $1 
                AND target_id = $2
                """,
            ctx.guild.id,
            member_or_channel.id,
        )

        if record:
            await self.bot.pool.execute(
                """
                DELETE FROM ignored_logging 
                WHERE guild_id = $1 
                AND target_id = $2
                """,
                ctx.guild.id,
                member_or_channel.id,
            )
            return await ctx.embed(
                f"{member_or_channel.mention} will now be **logged**",
                message_type="approved",
            )

        await self.bot.pool.execute(
            """
            INSERT INTO ignored_logging (guild_id, target_id) 
            VALUES ($1, $2)
            """,
            ctx.guild.id,
            member_or_channel.id,
        )
        return await ctx.embed(
            f"{member_or_channel.mention} will no longer be **logged**",
            message_type="warned",
        )

    @logs_ignore.command(name="list")
    @has_permissions(manage_guild=True)
    async def logs_ignore_list(
        self, ctx: Context
    ) -> Message:
        """
        View all ignored members and channels.
        """
        records = await self.bot.pool.fetch(
            """
            SELECT target_id 
            FROM ignored_logging 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )
        if not records:
            return await ctx.embed(
                "No **members** or **channels** are being ignored",
                message_type="warned",
            )

        entries = [
            f"<@{record['target_id']}>"
            for record in records
        ]

        embed = Embed(title="Ignored Members & Channels")
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.avatar.url,
        )
        return await ctx.paginate(
            embed=embed, entries=entries
        )

    @logs.command(name="remove", aliases=("disable", "off"))
    @has_permissions(manage_guild=True)
    async def logs_remove(
        self,
        ctx: Context,
        channel: TextChannel | Thread,
        *event_names: str,
    ) -> Message:
        """
        Remove events from a logging channel.
        """
        record = await self.bot.pool.fetchrow(
            """
            SELECT * FROM logging 
            WHERE guild_id = $1 
            AND channel_id = $2
            """,
            ctx.guild.id,
            channel.id,
        )
        if not record:
            return await ctx.embed(
                f"No **events** are set up for {channel.mention}",
                message_type="warned",
            )

        if "all" in event_names:
            await ctx.prompt(
                "Are you sure you want to remove all logging events from this channel?"
            )
            await self.bot.pool.execute(
                """
                DELETE FROM logging 
                WHERE guild_id = $1 
                AND channel_id = $2
                """,
                ctx.guild.id,
                channel.id,
            )
            return await ctx.embed(
                f"No longer **logging** any events in {channel.mention}",
                message_type="approved",
            )

        valid_events = []
        invalid_events = []

        for event_name in event_names:
            try:
                event = LogType.from_str(event_name)
                valid_events.append(event)
            except KeyError:
                invalid_events.append(event_name)

        if invalid_events:
            return await ctx.embed(
                f"**Option** must be one of: {', '.join(f'`{e}`' for e in LogType.all())}",
                message_type="warned",
            )

        new_events = [
            LogType.from_str(event)
            for event in record["events"]
        ]
        removed_events = []
        for event in valid_events:
            if event in new_events:
                new_events.remove(event)
                removed_events.append(event)

        if not removed_events:
            return await ctx.embed(
                f"None of these events were set up in {channel.mention}",
                message_type="warned",
            )

        await self.bot.pool.execute(
            """
            UPDATE logging
            SET events = $3
            WHERE guild_id = $1 
            AND channel_id = $2
            """,
            ctx.guild.id,
            channel.id,
            [str(event) for event in new_events],
        )

        if len(removed_events) == 1:
            event_text = f"`{removed_events[0]}`"
        else:
            event_text = ", ".join(
                f"`{event}`" for event in removed_events
            )

        return await ctx.embed(
            f"No longer **logging** {event_text} in {channel.mention}",
            message_type="approved",
        )

    @Cog.listener("on_member_join")
    async def log_member_join(self, member: Member) -> None:
        """
        Log when a member joins the guild.
        """
        embed = Embed(title="Member Joined")
        if member.created_at > utcnow() - timedelta(days=1):
            embed.description = (
                "**⚠ Account created less than a day ago**"
            )

        embed.add_field(
            name="Account Created",
            value=f"{format_dt(member.created_at, 'F')} ({format_dt(member.created_at, 'R')})",
            inline=False,
        )
        if member.joined_at:
            embed.add_field(
                name="Joined Server",
                value=f"{format_dt(member.joined_at, 'F')} ({format_dt(member.joined_at, 'R')})",
                inline=False,
            )

        await log(
            LogType.MEMBER, member.guild, embed, user=member
        )

    @Cog.listener("on_member_remove")
    async def log_member_remove(
        self, member: Member
    ) -> None:
        """
        Log when a member leaves the guild.
        """
        if not member.joined_at:
            return

        embed = Embed(title="Member Left")
        embed.add_field(
            name="Joined Server",
            value=f"{format_dt(member.joined_at, 'F')} ({format_dt(member.joined_at, 'R')})",
            inline=False,
        )

        await log(
            LogType.MEMBER, member.guild, embed, user=member
        )

    @Cog.listener("on_member_update")
    async def log_member_update(
        self, before: Member, after: Member
    ) -> None:
        """
        Log when a member's details are updated.
        """
        changes: list[tuple[str, str]] = []
        if before.nick != after.nick:
            changes.append((
                "Nickname",
                f"{before.nick} → {after.nick}",
            ))

        if before.guild_avatar != after.guild_avatar:
            changes.append((
                "Server Avatar",
                "Server avatar changed",
            ))

        if before.guild_banner != after.guild_banner:
            changes.append((
                "Server Banner",
                "Server banner changed",
            ))

        if not changes:
            return

        embed = Embed(title="Member Updated")
        for name, value in changes:
            embed.add_field(
                name=name, value=value, inline=False
            )

        await log(
            LogType.MEMBER, after.guild, embed, user=after
        )

    @Cog.listener("on_message_delete")
    async def log_message_delete(
        self, message: Message
    ) -> None:
        """
        Log when a message is deleted.
        """
        if (
            not message.guild
            or message.author.bot
            or isinstance(
                message.channel,
                (
                    GroupChannel,
                    DMChannel,
                    PartialMessageable,
                ),
            )
        ):
            return

        embed = Embed(
            description=f"Message from {message.author.mention} deleted in {message.channel.mention}\n it was sent at {format_dt(message.created_at, 'f')}",
        )

        embed.set_author(
            name="Message Deleted",
            icon_url=message.author.avatar,
        )
        embed.set_footer(
            text=f"User ID: {message.author.id}"
        )

        if message.system_content:
            embed.add_field(
                name="Message Content",
                value=message.system_content[:1024],
                inline=False,
            )

        if message.stickers:
            embed.set_image(url=message.stickers[0].url)

        for embed_ in message.embeds:
            if embed_.image:
                embed.set_image(url=embed_.image.url)
                break

        files: list[File] = []
        for attachment in message.attachments:
            with suppress(HTTPException):
                file = await attachment.to_file(
                    description=f"Attachment from {message.author}'s message",
                    spoiler=attachment.is_spoiler(),
                )
                files.append(file)

        if not embed.fields and not files:
            return

        await log(
            LogType.MESSAGE,
            message.guild,
            embed,
            user=message.author,
            files=files,
        )

    @Cog.listener("on_message_edit")
    async def log_message_edit(
        self, before: Message, after: Message
    ) -> None:
        """
        Log when a message is edited.
        """
        if (
            not after.guild
            or after.author.bot
            or isinstance(
                after.channel,
                (
                    GroupChannel,
                    DMChannel,
                    PartialMessageable,
                ),
            )
        ):
            return

        embed = Embed()
        embed.set_author(
            name="Message Edited",
            icon_url=before.author.avatar,
        )
        embed.description = ""

        if before.system_content != after.system_content:
            embed.description = f"Message from {before.author.mention} edited {format_dt(before.created_at, 'R')}"
            for key, value in (
                ("Before", before.system_content),
                ("After", after.system_content),
            ):
                embed.add_field(
                    name=key,
                    value=value[:1024],
                    inline=False,
                )

        elif before.attachments and not after.attachments:
            embed.description = f"Attachment removed from {before.author.mention}'s message"

        elif before.embeds and not after.embeds:
            for embed_ in before.embeds:
                if embed_.image:
                    embed.set_image(url=embed_.image.url)
                    break

        if not embed.description and not embed.image:
            return

        embed.description += f"\n> [Jump to the message]({after.jump_url}) in {after.channel.mention}"
        files: list[File] = []
        for attachment in before.attachments:
            if attachment in after.attachments:
                continue

            with suppress(HTTPException):
                file = await attachment.to_file(
                    description=f"Attachment from {before.author}'s message",
                    spoiler=attachment.is_spoiler(),
                )
                files.append(file)
        embed.set_footer(
            text=f"User ID: {before.author.id}"
        )

        await log(
            LogType.MESSAGE,
            after.guild,
            embed,
            user=after.author,
            files=files,
        )

    @Cog.listener("on_bulk_message_delete")
    async def log_bulk_message_delete(
        self, messages: list[Message]
    ) -> None:
        """
        Log when messages are bulk deleted.
        """
        if not messages:
            return

        guild = messages[0].guild
        if not guild:
            return

        record = await self.bot.pool.fetchval(
            """
            SELECT channel_id
            FROM logging
            WHERE guild_id = $1
            AND $2 = ANY(events)
            """,
            guild.id,
            LogType.MESSAGE.name,
        )
        if not record:
            return

        logging_channel = guild.get_channel(record)
        if not logging_channel:
            return

        embed = Embed()
        embed.set_author(
            name="Bulk Message Delete", icon_url=None
        )

        members = list({
            message.author for message in messages
        })
        embed.timestamp = messages[0].created_at
        embed.description = f"> **{len(messages)} messages** deleted in {messages[0].channel.mention}\n> <t:{int(messages[0].created_at.timestamp())}>"

        embed.add_field(
            name=f"**{plural(members):member}**",
            value="\n".join(
                [
                    f"> {member.mention} (`{member.id}`)"
                    for member in members[:10]
                ]
                + (
                    [f"> ... and {len(members) - 10} more"]
                    if len(members) > 10
                    else []
                )
            ),
        )

        buffer = BytesIO()
        for message in sorted(
            messages, key=lambda m: m.created_at
        ):
            buffer.write(
                f"{message.created_at.strftime('%m/%d/%Y @ %H:%M:%S')} - {message.author} ({message.author.id}): {message.content or ''}\n".encode(),
            )

        buffer.seek(0)

        with suppress(HTTPException, Exception) as e:
            webhook = await get_or_create_webhook(
                self.bot, logging_channel
            )
            if not webhook:
                return

        await webhook.send(
            embed=embed,
            files=[File(buffer, filename="messages.txt")],
            silent=True,
            username=f"{self.bot.user.name} Logs",
        )

    @Cog.listener("on_audit_log_entry_role_create")
    async def log_role_creation(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when a role is created.
        """
        role = cast(Role, entry.target)
        embed = Embed(title="Role Created")
        embed.description = f"Role {role.mention} created"
        if entry.user:
            embed.description += f" by {entry.user.mention}"

        if role.is_integration():
            embed.description += " (integration)"

        for key, value in (
            ("Name", role.name),
            ("Color", f"`{role.color}`"),
            ("ID", f"`{role.id}`"),
        ):
            embed.add_field(name=key, value=value)

        await log(
            LogType.ROLE,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_role_delete")
    async def log_role_deletion(
        self, entry: AuditLogEntry
    ) -> None:
        """Log when a role is deleted."""

        if isinstance(entry.target, Object):
            return

        role = cast(Role, entry.target)
        embed = Embed(title="Role Deleted")
        embed.description = f"Role {role.name} deleted"
        if entry.user:
            embed.description += f" by {entry.user.mention}"

        await log(
            LogType.ROLE,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_role_update")
    async def log_role_update(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when a role is updated.
        """
        role = cast(Role, entry.target)
        embed = Embed()
        embed.description = f"Role {role.mention} updated"
        if entry.user:
            embed.description += f" by {entry.user.mention}"

        if role.color != Color.default():
            embed.color = role.color

        if isinstance(role.display_icon, Asset):
            embed.set_thumbnail(url=role.display_icon)

        changes: list[tuple[str, str]] = []
        if before := entry.before:
            if (
                getattr(before, "name", role.name)
                != role.name
            ):
                changes.append((
                    "Name",
                    f"{before.name} -> {role.name}",
                ))

            if (
                getattr(before, "color", role.color)
                != role.color
            ):
                changes.append((
                    "Color",
                    f"`{before.color}` -> `{role.color}``",
                ))

            if (
                getattr(before, "hoist", role.hoist)
                != role.hoist
            ):
                changes.append((
                    "Hoisted",
                    f"The role is {'now' if role.hoist else 'no longer'} hoisted",
                ))

            if (
                getattr(
                    before, "mentionable", role.mentionable
                )
                != role.mentionable
            ):
                changes.append((
                    "Mentionable",
                    f"The role is {'now' if role.mentionable else 'no longer'} mentionable",
                ))

            if (
                getattr(before, "position", role.position)
                != role.position
            ):
                changes.append((
                    "Position",
                    f"{before.position} -> {role.position}",
                ))

            if (
                getattr(
                    before, "permissions", role.permissions
                )
                != role.permissions
            ):
                changes.append((
                    "Permissions Updated",
                    "\n".join([
                        f"> `{'✅' if status else '❌'}`"
                        f" **{permission.replace('_', ' ').title()}**"
                        for permission, status in role.permissions
                        if status
                        != getattr(
                            before.permissions, permission
                        )
                    ]),
                ))

        if not changes:
            return

        for name, value in changes:
            embed.add_field(
                name=name, value=value, inline=False
            )

        if not embed.fields:
            return

        embed.set_author(
            name="Role Updated",
            icon_url=entry.user.avatar,
        )
        embed.set_footer(text=f"User ID: {entry.user.id}")
        await log(
            LogType.ROLE,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_member_role_update")
    async def log_member_role_update(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when a member's roles are updated.
        """
        member = cast(Member, entry.target)
        embed = Embed()
        embed.set_author(
            name="Member Roles Updated",
            icon_url=member.avatar,
        )

        moderator_info = "Unknown"
        if entry.user and entry.user != member:
            moderator_info = (
                f"{entry.user.mention} (`{entry.user.id}`)"
            )

        granted = [
            role.mention
            for role in entry.after.roles
            if role not in entry.before.roles
        ]
        removed = [
            role.mention
            for role in entry.before.roles
            if role not in entry.after.roles
        ]

        if granted:
            embed.description = f"{member.mention} was granted {', '.join(granted)}"

        if removed:
            embed.description = f"{member.mention} was removed from {', '.join(removed)}"

        embed.add_field(
            name="Moderator",
            value=moderator_info,
            inline=False,
        )
        embed.set_footer(text=f"User ID: {member.id}")

        await log(
            LogType.MEMBER, entry.guild, embed, user=member
        )

    @Cog.listener("on_audit_log_entry_channel_create")
    async def log_channel_creation(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when a channel is created.
        """
        channel = cast(TextChannel, entry.target)
        embed = Embed()
        embed.description = f"{channel.type.name.title()} Channel **{channel.mention}** created"
        if entry.user:
            embed.description += f" by {entry.user.mention}"

        embed.set_author(
            name="Channel Created",
            icon_url=entry.user.avatar,
        )
        embed.set_footer(text=f"User ID: {entry.user.id}")
        await log(
            LogType.CHANNEL,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_channel_delete")
    async def log_channel_deletion(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when a channel is deleted.
        """
        entry.target = cast(Object, entry.target)
        channel = cast(GuildChannel, entry.before)

        embed = Embed()
        embed.description = f"{channel.type.name.replace('_', ' ').title()} Channel **#{channel.name}** deleted"
        if entry.user:
            embed.description += f" by {entry.user.mention} \n Channel was created at {format_dt(entry.target.created_at, 'F')} ({format_dt(entry.target.created_at, 'R')})"
        embed.set_author(
            name="Channel Deleted",
            icon_url=entry.user.avatar,
        )
        embed.set_footer(text=f"User ID: {entry.user.id}")

        await log(
            LogType.CHANNEL,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_invite_create")
    async def log_invite_creation(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when an invite is created.
        """
        invite = cast(Invite, entry.target)
        embed = Embed()
        embed.description = f"{invite.temporary and 'Temporary' or ''} Invite [`{invite.code}`]({invite.url}) created"
        if entry.user:
            embed.description += f" by {entry.user.mention}"
        embed.set_author(
            name="Invite Created",
            icon_url=entry.user.avatar,
        )

        if isinstance(invite.channel, GuildChannel):
            embed.add_field(
                name="Channel", value=invite.channel.mention
            )

        if invite.max_uses:
            embed.add_field(
                name="Max Uses",
                value=f"`{invite.max_uses}`",
            )

        if invite.max_age:
            embed.add_field(
                name="Max Age",
                value=format_timespan(invite.max_age),
            )

        await log(
            LogType.INVITE,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_invite_delete")
    async def log_invite_deletion(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when an invite is deleted.
        """
        invite = cast(Invite, entry.target)
        embed = Embed()
        embed.description = f"Invite [`{invite.code}`]({invite.url}) deleted"
        if entry.user:
            embed.description += f" by {entry.user.mention}"
        embed.set_author(
            name="Invite Deleted",
            icon_url=entry.user.avatar,
        )

        if invite.uses:
            embed.add_field(
                name="Uses",
                value=f"`{invite.uses}`/`{invite.max_uses or '∞'}`",
            )

        if invite.inviter and invite.inviter != entry.user:
            embed.add_field(
                name="Inviter", value=invite.inviter.mention
            )

        await log(
            LogType.INVITE,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_emoji_create")
    async def log_emoji_creation(
        self, entry: AuditLogEntry
    ) -> None:
        """Log when an emoji is created."""

        emoji = cast(Emoji, entry.target)
        embed = Embed()
        embed.description = f"Emoji {emoji} created"
        if entry.user:
            embed.description += f" by {entry.user.mention}"
        embed.set_author(
            name="Emoji Created",
            icon_url=entry.user.avatar,
        )

        embed.set_thumbnail(url=emoji.url)
        for key, value in (
            ("Name", emoji.name),
            ("ID", f"`{emoji.id}`"),
        ):
            embed.add_field(name=key, value=value)

        await log(
            LogType.EMOJI,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_emoji_update")
    async def log_emoji_update(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when an emoji is updated.
        """
        emoji = cast(Emoji, entry.target)
        embed = Embed()
        embed.description = f"Emoji {emoji} updated"
        if entry.user:
            embed.description += f" by {entry.user.mention}"
        embed.set_author(
            name="Emoji Updated",
            icon_url=entry.user.avatar,
        )

        if (
            getattr(entry.before, "name", emoji.name)
            != emoji.name
        ):
            embed.add_field(
                name="Name",
                value=f"{entry.before.name} → {emoji.name}",
            )

        if (
            getattr(entry.before, "roles", emoji.roles)
            != emoji.roles
        ):
            embed.add_field(
                name="Required Roles",
                value=human_join(
                    [role.mention for role in emoji.roles],
                    final="and",
                ),
            )

        if not embed.fields:
            return

        await log(
            LogType.EMOJI,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_sticker_create")
    async def log_sticker_creation(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when a sticker is created.
        """
        sticker = cast(GuildSticker, entry.target)
        embed = Embed()
        embed.description = f"Sticker {sticker} created"
        if entry.user:
            embed.description += f" by {entry.user.mention}"

        embed.set_author(
            name="Sticker Created",
            icon_url=entry.user.avatar,
        )

        embed.set_thumbnail(url=sticker.url)
        for key, value in (
            ("Name", sticker.name),
            ("ID", f"`{sticker.id}`"),
        ):
            embed.add_field(name=key, value=value)

        await log(
            LogType.STICKER,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_audit_log_entry_sticker_update")
    async def log_sticker_update(
        self, entry: AuditLogEntry
    ) -> None:
        """
        Log when a sticker is updated.
        """
        sticker = cast(GuildSticker, entry.target)
        embed = Embed()
        embed.description = f"Sticker {sticker} updated"
        if entry.user:
            embed.description += f" by {entry.user.mention}"
        embed.set_author(
            name="Sticker Updated",
            icon_url=entry.user.avatar,
        )

        if (
            getattr(entry.before, "name", sticker.name)
            != sticker.name
        ):
            embed.add_field(
                name="Name",
                value=f"{entry.before.name} → {sticker.name}",
            )

        if (
            getattr(
                entry.before,
                "description",
                sticker.description,
            )
            != sticker.description
        ):
            embed.add_field(
                name="Description",
                value=f"{entry.before.description} → {sticker.description or 'None'}",
            )

        if (
            getattr(entry.before, "emoji", sticker.emoji)
            != sticker.emoji
        ):
            embed.add_field(
                name="Emoji",
                value=f"{entry.before.emoji} → {sticker.emoji}",
            )

        if not embed.fields:
            return

        await log(
            LogType.STICKER,
            entry.guild,
            embed,
            user=entry.user,
        )

    @Cog.listener("on_voice_state_update")
    async def log_voice_state_update(
        self,
        member: Member,
        before: VoiceState,
        after: VoiceState,
    ) -> None:
        """
        Log when a member's voice state is updated.
        """
        embed = Embed()
        embed.set_author(
            name="Voice State Updated",
            icon_url=member.avatar,
        )

        if (
            before.channel == after.channel
            and after.channel
        ):
            if before.self_mute != after.self_mute:
                embed.description = f"{member.mention} {'muted' if after.self_mute else 'unmuted'} themselves"
                embed.add_field(
                    name="Current Channel",
                    value=f"{after.channel.mention}",
                    inline=False,
                )

            elif before.self_deaf != after.self_deaf:
                embed.description = f"{member.mention} {'deafened' if after.self_deaf else 'undeafened'} themselves"
                embed.add_field(
                    name="Current Channel",
                    value=f"{after.channel.mention}",
                    inline=False,
                )

            elif before.self_stream != after.self_stream:
                embed.description = f"{member.mention} {'started' if after.self_stream else 'stopped'} streaming"
                embed.add_field(
                    name="Current Channel",
                    value=f"{after.channel.mention}",
                    inline=False,
                )

            elif before.self_video != after.self_video:
                embed.description = f"{member.mention} {'started' if after.self_video else 'stopped'} video"
                embed.add_field(
                    name="Current Channel",
                    value=f"{after.channel.mention}",
                    inline=False,
                )

            elif before.mute != after.mute:
                embed.description = f"{member.mention} was {'muted' if after.mute else 'unmuted'} by an moderator"
                embed.add_field(
                    name="Current Channel",
                    value=f"{after.channel.mention}",
                    inline=False,
                )

            elif before.deaf != after.deaf:
                embed.description = f"{member.mention} was {'deafened' if after.deaf else 'undeafened'} by an moderator"
                embed.add_field(
                    name="Current Channel",
                    value=f"{after.channel.mention}",
                    inline=False,
                )

            elif before.suppress != after.suppress:
                embed.description = f"{member.mention} was {'suppressed' if after.suppress else 'unsuppressed'} by an moderator"
                embed.add_field(
                    name="Current Channel",
                    value=f"{after.channel.mention}",
                    inline=False,
                )

        elif not before.channel and after.channel:
            embed.description = f"{member.mention} joined {after.channel.mention}"
            embed.add_field(
                name="Current Channel",
                value=f"{after.channel.mention}",
                inline=False,
            )

        elif before.channel and not after.channel:
            embed.description = f"{member.mention} left {before.channel.mention}"

        elif before.channel and after.channel:
            embed.description = f"{member.mention} moved from {before.channel.mention} to {after.channel.mention}"
            embed.add_field(
                name="Previous Channel",
                value=f"{before.channel.mention}",
                inline=False,
            )
            embed.add_field(
                name="Current Channel",
                value=f"{after.channel.mention}",
                inline=False,
            )

        embed.set_footer(text=f"User ID: {member.id}")

        if not embed.description:
            return

        await log(
            LogType.VOICE, member.guild, embed, user=member
        )