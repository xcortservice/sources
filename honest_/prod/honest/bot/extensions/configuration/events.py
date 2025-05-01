import re
from asyncio import Lock, ensure_future, gather, sleep
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timedelta
from os import remove
from random import sample
from typing import List

from data.variables import (COLORHEX, HEX_COOLDOWN,
                            MESSAGE_EVENT_ALLOWED_MENTIONS, TRACKER_COOLDOWN,
                            TRANSCRIBE_COOLDOWN)
from discord import (AllowedMentions, Attachment, Client, Color, Embed, File,
                     Guild, Member, Message, RawReactionActionEvent,
                     TextChannel, utils)
from discord.abc import GuildChannel
from discord.ext import tasks
from discord.ext.commands import Cog
from discord.utils import utcnow
from humanize import naturaldelta
from loguru import logger
from system.classes.builtins import get_error
from system.classes.database import Record
from system.patch.context import Context
from system.services.manipulation.audio import do_transcribe, download_file
from tools import timeit
from xxhash import xxh32_hexdigest

ANTI_SPAM_MAP = {
    "1": {"title": "Antispam", "reason": "Spamming"},
    "2": {"title": "Anti Ladder", "reason": "Ladder Typing"},
    "3": {"title": "Anti Flood", "reason": "Flooding"},
}


def to_data(guild: Guild):
    """Convert the instance back to a GuildPayload dictionary."""
    guild_payload = {
        "id": str(guild.id),
        "name": guild.name,
        "member_count": guild._member_count,
        "verification_level": guild.verification_level.value,
        "default_message_notifications": guild.default_notifications.value,
        "explicit_content_filter": guild.explicit_content_filter.value,
        "afk_timeout": guild.afk_timeout,
        "icon": guild._icon,
        "banner": guild._banner,
        "unavailable": guild.unavailable,
        "roles": [role.to_data() for role in guild._roles.values()],
        "emojis": [emoji.to_data() for emoji in guild.emojis],
        "stickers": [sticker.to_data() for sticker in guild.stickers],
        "features": guild.features,
        "splash": guild._splash,
        "system_channel_id": guild._system_channel_id,
        "description": guild.description,
        "max_presences": guild.max_presences,
        "max_members": guild.max_members,
        "max_video_channel_users": guild.max_video_channel_users,
        "max_stage_video_channel_users": guild.max_stage_video_users,
        "premium_tier": guild.premium_tier,
        "premium_subscription_count": guild.premium_subscription_count,
        "vanity_url_code": guild.vanity_url_code,
        "widget_enabled": guild.widget_enabled,
        "widget_channel_id": guild._widget_channel_id,
        "system_channel_flags": guild._system_channel_flags,
        "preferred_locale": guild.preferred_locale.value,
        "discovery_splash": guild._discovery_splash,
        "rules_channel_id": guild._rules_channel_id,
        "public_updates_channel_id": guild._public_updates_channel_id,
        "safety_alerts_channel_id": guild._safety_alerts_channel_id,
        "nsfw_level": guild.nsfw_level.value,
        "mfa_level": guild.mfa_level.value,
        "approximate_presence_count": guild.approximate_presence_count,
        "approximate_member_count": guild.approximate_member_count,
        "premium_progress_bar_enabled": guild.premium_progress_bar_enabled,
        "owner_id": guild.owner_id,
        "large": guild._large,
        "afk_channel_id": guild._afk_channel_id,
        "incidents_data": guild._incidents_data,
        "channels": [
            channel.to_data() for channel in guild._channels
        ],  # Assuming _channels is defined
        "voice_states": [
            state.to_data() for state in guild._voice_states.values()
        ],  # Assuming _voice_states is defined
        "threads": [
            thread.to_data() for thread in guild._threads
        ],  # Assuming _threads is defined
        "stage_instances": [
            instance.to_data() for instance in guild._stage_instances.values()
        ],  # Assuming _stage_instances is defined
        "guild_scheduled_events": [
            event.to_data() for event in guild._scheduled_events.values()
        ],  # Assuming _scheduled_events is defined
        "soundboard_sounds": [
            sound.to_data() for sound in guild._soundboard_sounds
        ],  # Assuming _soundboard_sounds is defined
    }
    return guild_payload


class ConfigurationEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.locks = defaultdict(Lock)
        self.debug = False

    @Cog.listener("on_member_update")
    async def boost_dispatcher(self, before: Member, after: Member):
        if (
            before.guild.premium_subscription_count
            < after.guild.premium_subscription_count
            or not before.premium_since
        ):
            if after.premium_since:
                member = after
                if not (
                    config := await self.bot.db.fetchrow(
                        """SELECT boost_channel, boost_message FROM config WHERE guild_id = $1""",
                        member.guild.id,
                    )
                ):
                    return
                if not config.boost_channel or not config.boost_message:
                    return
                if not (channel := member.guild.get_channel(config.boost_channel)):
                    return
                self.bot.dispatch(
                    "boost", member.guild, member, channel, config.boost_message
                )

    async def check_message(self, message: Message, config: Record) -> bool:
        if config.status is False:
            return

        if config.whitelisted:
            SNOWFLAKES = [r.id for r in message.author.roles]
            SNOWFLAKES.extend([message.author.id, message.channel.id])
            if set(SNOWFLAKES) & set(config.whitelisted):
                return False

        if (len(message.content.split("\n")) >= config.ladder_threshold) and (
            config.ladder_status is True
        ):
            self.bot.dispatch("ladder_typing", message, config)
            return True

        if (len(message.content) >= config.flood_threshold) and (
            config.flood_status is True
        ):
            self.bot.dispatch("text_flood", message, config)
            return True

        if (
            await self.bot.object_cache.ratelimited(
                xxh32_hexdigest(f"spam:{message.guild.id}:{message.author.id}"),
                config.threshold,
                10,
            )
            != 0
        ):
            self.bot.dispatch("message_spam", message, config)
            return True

        return False

    @Cog.listener("on_valid_message")
    async def on_valid_message(self, ctx: Context):
        if not (
            config := await self.bot.db.fetchrow(
                """SELECT timeout, threshold, whitelisted, ladder_status, ladder_threshold, flood_status, flood_threshold, status FROM antispam WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            return
        await self.check_message(ctx.message, config)

    @Cog.listener("on_valid_message")
    async def event_dispatcher(self, ctx: Context):

        async def voice_check():
            async with self.locks[f"transcribe:{ctx.guild.id}"]:
                voice_attachments = [
                    attachment
                    for attachment in ctx.message.attachments
                    if attachment.is_voice_message()
                ]
                if not voice_attachments:
                    return
                check = (
                    await self.bot.db.fetchval(
                        """SELECT transcription FROM config WHERE guild_id = $1""",
                        ctx.guild.id,
                    )
                    or False
                )
                if not check or check is False:
                    return
                ratelimit = await self.bot.object_cache.ratelimited(
                    f"transcribe:{ctx.message.guild.id}", *TRANSCRIBE_COOLDOWN
                )
                if ratelimit != 0:
                    return  # or await sleep(ratelimit) # if you just want to sleep it
                for attachment in voice_attachments:
                    self.bot.dispatch("voice_message", ctx.message, attachment)

        async def hex_code_check():
            async with self.locks[f"color_hex:{ctx.channel.id}"]:
                if not (match := re.search(COLORHEX, ctx.message.content)):
                    return
                check = (
                    await self.bot.db.fetchval(
                        """SELECT auto_hex FROM config WHERE guild_id = $1""",
                        ctx.guild.id,
                    )
                    or False
                )
                if not check or check is False:
                    return
                ratelimit = await self.bot.object_cache.ratelimited(
                    f"hex:{ctx.message.channel.id}", *HEX_COOLDOWN
                )
                if ratelimit != 0:
                    return  # or await sleep(ratelimit) # if you just want to sleep it
                self.bot.dispatch("hex_submit", ctx.message, match.group(0))
                return

        await gather(*[voice_check(), hex_code_check()])

    def spam_embed(self, message: Message, config: Record, event_type: int):
        title = ANTI_SPAM_MAP[str(event_type)]["title"]

        embed = Embed(
            color=Color.yellow(),
            title=title,
            description=f">>> {message.author.mention} has been muted for **{naturaldelta(config.timeout)}**",
        )
        return embed

    async def punish(self, message: Message, config: Record, event_type: int):
        async with self.locks[f"punishment:{message.author.id}"]:
            if message.guild.me.guild_permissions.manage_messages is not True:
                return

            if message.guild.me.guild_permissions.moderate_members is not True:
                return

            if message.guild.me.guild_permissions.manage_messages is not True:
                return

            if message.author.guild_permissions.administrator is True:
                return

            if (
                message.author.top_role.actual_position
                <= message.guild.me.top_role.actual_position
            ):
                return

            if message.author.is_timed_out():
                return

            if (
                await self.bot.object_cache.ratelimited(
                    f"punishment:{message.guild.id}:{message.author.id}",
                    1,
                    (config.timeout - 10),
                )
                != 0
            ):
                return
            reason = ANTI_SPAM_MAP[str(event_type)]["reason"]
            await message.author.timeout(
                utcnow() + timedelta(seconds=config.timeout), reason=reason
            )
            await message.channel.purge(
                limit=10,
                check=lambda m: m.author.id == message.author.id,
            )
        return True

    @Cog.listener("on_message_spam")
    async def spammer_detection(self, message: Message, config: Record):
        return await self.punish(message, config, 1)

    @Cog.listener("on_ladder_typing")
    async def ladder_detection(self, message: Message, config: Record):
        return await self.punish(message, config, 2)

    @Cog.listener("on_text_flood")
    async def flooding_detection(self, message: Message, config: Record):
        return await self.punish(message, config, 3)

    @Cog.listener("on_voice_message")
    async def on_voice_message(self, message: Message, voice_message: Attachment):
        file_path = await download_file(voice_message.url)
        transcription = await do_transcribe(self.bot, file_path)
        await message.reply(
            embed=Embed(description=transcription).set_author(
                name=str(message.author), icon_url=message.author.display_avatar.url
            ),
            allowed_mentions=AllowedMentions(replied_user=False),
        )
        with suppress(FileNotFoundError):
            remove(file_path)

    @Cog.listener("on_hex_submit")
    async def on_hex_submission(self, message: Message, hex_code: str):
        color = Color.from_str(hex_code)
        embed = (
            Embed(
                color=color,
                title=f"Showing hex code: {hex_code}",
            )
            .set_thumbnail(
                url=f"https://singlecolorimage.com/get/{hex_code[1:]}/400x400"
            )
            .add_field(
                name="RGB value",
                value=", ".join(color.to_rgb()),
            )
        )

        return await message.reply(
            embed=embed, allowed_mentions=MESSAGE_EVENT_ALLOWED_MENTIONS
        )

    @Cog.listener("on_guild_update")
    async def on_vanity_update(self, before: Guild, after: Guild):
        if before.name != after.name:
            self.bot.dispatch("guild_name_update", before)
        if not before.vanity_url_code:
            return
        if before.vanity_url_code == after.vanity_url_code:
            return
        self.bot.dispatch("vanity_change", before.vanity_url_code)

    @Cog.listener("on_vanity_change")
    async def on_vanity_change(self, vanity: str):
        if not (
            trackers := await self.bot.db.fetch(
                """SELECT guild_id, channel_ids FROM trackers WHERE tracker_type = $1""",
                "vanity",
            )
        ):
            return
        for tracker in trackers:
            if not (guild := self.bot.get_guild(tracker.guild_id)):
                continue
            ensure_future(self.emit_vanity_change(guild, vanity, tracker.channel_ids))

    async def emit_vanity_change(
        self, guild: Guild, vanity: str, channel_ids: List[int]
    ):
        async def send_message(channel: GuildChannel, vanity: str):
            ratelimit = await self.bot.object_cache.ratelimited(
                f"rl:tracker_message:vanity:{guild.id}", *TRACKER_COOLDOWN
            )
            if ratelimit != 0:
                await sleep(ratelimit)
            return await channel.send(f"Vanity URL available: `/{vanity}`")

        channels = [
            channel
            for channel_id in channel_ids
            if (channel := guild.get_channel(channel_id))
        ]
        for channel in channels:
            await sleep(0.1)
            ensure_future(send_message(channel, vanity))

    @Cog.listener("on_username_submit")
    async def on_username_tracker(self, username: str):
        if not (
            trackers := await self.bot.db.fetch(
                """SELECT guild_id, channel_ids FROM trackers WHERE tracker_type = $1""",
                "username",
            )
        ):
            return
        for tracker in trackers:
            if not (guild := self.bot.get_guild(tracker.guild_id)):
                continue
            ensure_future(
                self.emit_username_change(guild, username, tracker.channel_ids)
            )

    async def emit_username_change(
        self, guild: Guild, username: str, channel_ids: List[int]
    ):
        async def send_message(channel: GuildChannel, username: str):
            ratelimit = await self.bot.object_cache.ratelimited(
                f"rl:tracker_message:username:{guild.id}", *TRACKER_COOLDOWN
            )
            if ratelimit != 0:
                await sleep(ratelimit)
            return await channel.send(f"Username available: `{username}`")

        channels = [
            channel
            for channel_id in channel_ids
            if (channel := guild.get_channel(channel_id))
        ]
        for channel in channels:
            await sleep(0.1)
            ensure_future(send_message(channel, username))

    @Cog.listener("on_unwhitelisted_join")
    async def not_whitelisted(self, member: Member):
        if member.id in (349274018307637249):
            return
        async with self.locks[member.guild.id]:
            if dm := await self.bot.db.fetchval(
                """SELECT whitelist_dm FROM config WHERE guild_id = $1""",
                member.guild.id,
            ):
                await self.bot.send(member, dm, True)
            if (
                await self.bot.object_cache.ratelimited(
                    xxh32_hexdigest(f"unwhitelisted:{member.id}-{member.guild.id}"),
                    3,
                    100000,
                )
                != 0
            ):
                return await member.ban(
                    reason="Member tried to join multiple times while being unwhitelisted"
                )
            return await member.kick(reason="Unwhitelisted member")

    @Cog.listener("on_raid_join")
    async def on_raid(self, member: Member, reason: str):
        async with self.locks[f"raid:{member.guild.id}"]:
            rl = await self.bot.object_cache.ratelimited(
                f"raid_kick:{member.guild.id}", 4, 5
            )
            if rl != 0:
                await sleep(rl)
            await member.kick(reason=reason)
        return

    @Cog.listener("on_member_agree")
    async def on_auto_role(self, member: Member):
        if member.bot:
            return

        role_ids = await self.bot.db.fetchval(
            """SELECT auto_roles FROM config WHERE guild_id = $1""", member.guild.id
        )
        if not role_ids:
            return

        def get_role(role_id: int):
            role = member.guild.get_role(role_id)
            if role and not role.is_dangerous():
                return role

        current_roles = member.roles[1:]
        for role_id in role_ids:
            role = get_role(role_id)
            if role and role not in current_roles:
                current_roles.append(role)

        await member.edit(roles=set(current_roles), reason="Auto Role")

    @Cog.listener("on_welcome")
    async def welcome_message(
        self, guild: Guild, member: Member, channel: TextChannel, code: str
    ):
        rl = await self.bot.object_cache.ratelimited(f"message_event:{guild.id}", 3, 10)
        if rl != 0:
            await sleep(rl)
        return await self.bot.send_embed(channel, code, user=member)

    @Cog.listener("on_boost")
    async def boost_message(
        self, guild: Guild, member: Member, channel: TextChannel, code: str
    ):
        rl = await self.bot.object_cache.ratelimited(f"message_event:{guild.id}", 3, 10)
        if rl != 0:
            await sleep(rl)
        return await self.bot.send_embed(channel, code, user=member)

    @Cog.listener("on_leave")
    async def leave_message(
        self, guild: Guild, member: Member, channel: TextChannel, code: str
    ):
        rl = await self.bot.object_cache.ratelimited(f"message_event:{guild.id}", 3, 10)
        if rl != 0:
            await sleep(rl)
        return await self.bot.send_embed(channel, code, user=member)


async def setup(bot: Client):
    await bot.add_cog(ConfigurationEvents(bot))
