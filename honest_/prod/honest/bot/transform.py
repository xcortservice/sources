import traceback
from typing import Any, Dict, Optional, Union

from discord import (CategoryChannel, Client, Emoji, Guild, Member,
                     PartialEmoji, Role, ScheduledEvent, SoundboardSound,
                     StageChannel, StageInstance, Sticker, TextChannel, Thread,
                     User, VoiceChannel, VoiceState)
from loguru import logger

Channel = Union[VoiceChannel, TextChannel, Thread, StageChannel]


class Transformers:
    def __init__(self, bot: Client):
        self.bot = bot

    def role(self, role: Role) -> Dict[str, Any]:
        if role is None:
            return {}

        def transform_tags(role: Role) -> Dict[str, Any]:
            return {
                "bot_id": role.tags.bot_id,
                "integration_id": role.tags.integration_id,
                "subscription_listing_id": role.tags.subscription_listing_id,
                "premium_subscriber": (
                    role.tags._premium_subscriber
                    if role.tags._premium_subscriber
                    else None
                ),
                "available_for_purchase": (
                    role.tags._available_for_purchase
                    if role.tags._available_for_purchase
                    else None
                ),
                "guild_connections": (
                    role.tags._guild_connections
                    if role.tags._guild_connections
                    else None
                ),
            }

        return {
            "name": role.name,
            "id": str(role.id),
            "permissions": role._permissions,
            "position": role.position,
            "color": role._colour,
            "hoist": role.hoist,
            "icon": role._icon or None,
            "unicode_emoji": role.unicode_emoji or None,
            "managed": role.managed or False,
            "mentionable": role.mentionable or False,
            "tags": transform_tags(role) if role.tags else None,
            "flags": int(role._flags) if hasattr(role, "_flags") else None,
        }

    def channel(self, channel: Channel, guild: Optional[dict] = None) -> Dict[str, Any]:
        if channel is None:
            return {}

        def get_type(channel: Channel):
            try:
                return channel._type.value
            except AttributeError:
                try:
                    return channel._type
                except AttributeError:
                    try:
                        return channel.type.value
                    except AttributeError:
                        return channel.type

        if isinstance(channel, CategoryChannel):
            return {
                "guild": guild if guild else self.guild(guild=channel.guild),
                "name": channel.name,
                "type": 4,
                "category_id": channel.category_id,
                "position": channel.position,
                "nsfw": channel.nsfw,
                "permission_overwrites": [o._asdict() for o in channel._overwrites],
            }
        elif not isinstance(channel, (VoiceChannel, StageChannel, CategoryChannel)):
            return {
                "guild": guild if guild else self.guild(guild=channel.guild),
                "name": channel.name,
                "parent_id": channel.category_id,
                "topic": channel.topic if hasattr(channel, "topic") else None,
                "position": channel.position,
                "nsfw": channel.nsfw,
                "rate_limit_per_user": channel.slowmode_delay,
                "default_auto_archive_duration": channel.default_auto_archive_duration,
                "default_thread_rate_limit_per_user": channel.default_thread_slowmode_delay,
                "type": get_type(channel),
                "last_message_id": channel.last_message_id,
                "permission_overwrites": [o._asdict() for o in channel._overwrites],
            }
        else:
            return {
                "guild": guild if guild else self.guild(guild=channel.guild),
                "name": channel.name,
                "type": get_type(channel),
                "nsfw": channel.nsfw,
                "video_quality_mode": int(channel.video_quality_mode),
                "parent_id": channel.category_id,
                "last_message_id": channel.last_message_id,
                "position": channel.position,
                "rate_limit_per_user": channel.slowmode_delay,
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit,
                "permission_overwrites": [o._asdict() for o in channel._overwrites],
            }

    def user(self, user: User) -> Dict[str, Any]:
        if isinstance(user, int):
            user = self.bot.get_user(user)
        if user is None:
            return {}

        logger.info(f"{user} - {type(user)}")
        return {
            "id": str(user.id),
            "username": str(user),
            "avatar": user.avatar.key if user.avatar else None,
            "discriminator": str(user.discriminator),
            "public_flags": user._public_flags,
            "flags": user._public_flags,
            "banner": user.banner.key if user.banner else None,
            "accent_color": int(user.accent_color) if user.accent_color else None,
            "global_name": user.global_name,
            "avatar_decoration_data": {
                "asset": user.avatar_decoration.key,
                "sku_id": user.avatar_decoration_sku_id,
                "expires_at": None,
            },
            "banner_color": None,
            "mutual_guilds": [self.guild(guild=g) for g in user.mutual_guilds],
        }

    def member(self, member: Member) -> Dict[str, Any]:
        if member is None:
            return {}
        logger.info(f"{member} - {type(member)}")
        return {
            "id": str(member.id),
            "user": self.user(user=member._user),
            "nick": member.nick,
            "joined_at": member.joined_at.timestamp(),
            "premium_since": (
                member.premium_since.timestamp() if member.premium_since else None
            ),
            "roles": [i for i in member._roles],
            "pending": member.pending,
            "avatar": member._avatar,
            "banner": member._banner,
            "flags": member._flags,
            "communication_disabled_until": (
                member.timed_out_until.timestamp() if member.timed_out_until else None
            ),
        }

    def emoji(self, emoji: Union[Emoji, PartialEmoji]) -> Dict[str, Any]:
        if emoji is None:
            return {}
        if isinstance(emoji, int):
            emoji = self.bot.get_emoji(emoji)

        return {
            "id": str(emoji.id),
            "require_colons": emoji.require_colons,
            "managed": emoji.managed,
            "name": emoji.name,
            "animated": emoji.animated,
            "available": emoji.available,
            "roles": [i for i in emoji._roles],
            "user": self.user(user=emoji.user) if emoji.user else None,
        }

    def sticker(self, sticker: Sticker) -> Dict[str, Any]:
        if sticker is None:
            return {}
        if isinstance(sticker, int):
            sticker = self.bot.get_sticker(sticker)
        return {
            "id": str(sticker.id),
            "name": sticker.name,
            "format_type": str(int(sticker.format.value)),
            "description": sticker.description,
        }

    def thread(self, thread: Thread) -> Dict[str, Any]:
        if thread is None:
            return {}
        if isinstance(thread, int):
            thread = self.bot.get_channel(thread)

        def roll_metadata(thread: Thread):
            return {
                "archived": thread.archived,
                "archiver_id": thread.archiver_id,
                "auto_archive_duration": thread.auto_archive_duration,
                "archive_timestamp": (
                    thread.archive_timestamp.timestamp()
                    if thread.archive_timestamp
                    else None
                ),
                "locked": thread.locked,
                "invitable": thread.invitable,
                "create_timestamp": (
                    thread._created_at.timestamp() if thread._created_at else None
                ),
            }

        return {
            "id": str(thread.id),
            "parent_id": str(thread.parent_id),
            "owner_id": str(thread.owner_id),
            "name": str(thread.name),
            "type": thread._type,
            "last_message_id": thread.last_message_id,
            "rate_limit_per_user": thread.slowmode_delay,
            "message_count": thread.message_count,
            "member_count": thread.member_count,
            "flags": thread._flags,
            "applied_tags": [i for i in thread._applied_tags],
            "thread_metadata": roll_metadata(thread),
        }

    def event(self, event: ScheduledEvent) -> Dict[str, Any]:
        if event is None:
            return {}

        return {
            "id": str(event.id),
            "guild_id": str(event.guild_id),
            "name": str(event.name),
            "description": event.description,
            "entity_id": event.entity_id,
            "entity_type": event.entity_type,
            "scheduled_start_time": event.start_time.timestamp(),
            "status": int(event.privacy_level),
            "image": event._cover_image,
            "user_count": event.user_count,
            "creator_id": event.creator_id,
            "scheduled_end_time": event.end_time.timestamp(),
            "channel_id": event.channel_id,
            "entity_metadata": {"location": event.location or None},
        }

    def sound(self, sound: SoundboardSound) -> Dict[str, Any]:
        if sound is None:
            return {}

        return {
            "volume": sound.volume,
            "name": sound.name,
            "emoji_id": sound.emoji.id if sound.emoji else None,
            "emoji_name": sound.emoji.name if sound.emoji else None,
            "available": sound.available,
        }

    def stage(self, stage: StageInstance) -> Dict[str, Any]:
        if stage is None:
            return {}

        return {
            "id": stage.id,
            "channel_id": stage.channel_id,
            "topic": stage.topic,
            "privacy_level": int(stage.privacy_level),
            "discoverable_disabled": stage.discoverable_disabled,
            "guild_scheduled_event_id": stage.scheduled_event_id,
        }

    def voice(self, voice: VoiceState) -> Dict[str, Any]:
        if voice is None:
            return {}

        return {
            "self_mute": voice.self_mute,
            "self_deaf": voice.self_deaf,
            "self_stream": voice.self_stream,
            "self_video": voice.self_video,
            "suppress": voice.suppress,
            "mute": voice.mute,
            "deaf": voice.deaf,
            "request_to_speak_timestamp": (
                voice.requested_to_speak_at.timestamp()
                if voice.requested_to_speak_at
                else None
            ),
            "channel": self.channel(channel=voice.channel),
        }

    def guild(self, guild: Guild) -> Dict[str, Any]:
        if guild is None:
            return {}

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
            "roles": [self.role(role) for role in guild._roles.values()],
            "emojis": (
                [self.emoji(emoji=emoji) for emoji in guild.emojis]
                if len(guild.emojis) > 0
                else []
            ),
            "stickers": (
                [self.sticker(sticker=sticker) for sticker in guild.stickers]
                if len(guild.stickers) > 0
                else []
            ),
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
            "voice_states": [
                self.voice(state) for state in guild._voice_states.values()
            ],
            "threads": [self.thread(thread) for thread in guild._threads],
            "stage_instances": [
                self.stage(instance) for instance in guild._stage_instances.values()
            ],
            "guild_scheduled_events": [
                self.event(event) for event in guild._scheduled_events.values()
            ],
            "soundboard_sounds": [
                self.sound(sound) for sound in guild._soundboard_sounds
            ],
        }
        copy = guild_payload.copy()
        guild_payload["channels"] = [
            self.channel(channel=channel, guild=copy) for channel in guild.channels
        ]
        return guild_payload

    def test(self, ctx):
        import json

        guild = self.guild(guild=ctx.guild)
        channel = self.channel(channel=ctx.channel)
        user = self.user(user=ctx.bot.get_user(ctx.author.id))
        member = self.member(ctx.author)
        role = self.role(ctx.author.top_role)
        try:
            with open("data.json", "w") as file:
                file.write(
                    json.dumps(
                        {
                            "guild": guild,
                            "channel": channel,
                            "user": user,
                            "member": member,
                            "role": role,
                        },
                        indent=4,
                    )
                )
        except Exception as e:
            exc = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.info(f"dumping the transformed objects raised {exc}")
        return {
            "guild": guild,
            "channel": channel,
            "user": user,
            "member": member,
            "role": role,
        }
