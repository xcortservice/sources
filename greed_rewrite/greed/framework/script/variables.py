import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

from discord import (
    Asset,
    Color,
    Guild,
    Member,
    Role,
    Status,
    TextChannel,
    Thread,
    User,
    VoiceChannel,
)
from humanfriendly import format_timespan
from pydantic import BaseModel

Block = Union[
    Member,
    User,
    Role,
    Guild,
    VoiceChannel,
    TextChannel,
    Thread,
    BaseModel,
    str,
]
pattern = re.compile(r"(?<!\\)\{([a-zA-Z0-9_.]+)\}")


def get_suffix(n: int) -> str:
    return (
        "th"
        if 11 <= n <= 13
        else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    )


def to_dict(
    block: Block,
    _key: Optional[str] = None,
) -> Dict[str, str]:
    origin = block.__class__.__name__.lower()
    key = _key or getattr(block, "variable", origin)
    key = (
        "user"
        if key == "member"
        else "channel"
        if "channel" in key
        else key
    )

    data: Dict[str, str] = {key: str(block)}

    if isinstance(block, (Member, User)):
        data.update({
            "user": f"{block.name}#{block.discriminator}",
            "user.id": str(block.id),
            "user.mention": block.mention,
            "user.name": block.name,
            "user.tag": block.discriminator,
            "user.avatar": str(
                block.avatar.url
                if block.avatar
                else block.default_avatar.url
            ),
            "user.display_avatar": str(
                block.display_avatar.url
            ),
            "user.created_at": str(block.created_at),
            "user.created_at_timestamp": str(
                int(block.created_at.timestamp())
            ),
            "user.display_name": block.display_name,
            "user.bot": "Yes" if block.bot else "No",
        })

        if isinstance(block, Member):
            guild_avatar = (
                block.guild_avatar.url
                if block.guild_avatar
                else "N/A"
            )
            joined_at = block.joined_at
            premium_since = block.premium_since
            roles = sorted(
                block.roles[1:],
                key=lambda r: r.position,
                reverse=True,
            )

            data.update({
                "user.guild_avatar": str(guild_avatar),
                "user.joined_at": str(joined_at)
                if joined_at
                else "N/A",
                "user.joined_at_timestamp": (
                    str(int(joined_at.timestamp()))
                    if joined_at
                    else "N/A"
                ),
                "user.boost": "Yes"
                if premium_since
                else "No",
                "user.boost_since": str(premium_since)
                if premium_since
                else "N/A",
                "user.boost_since_timestamp": (
                    str(int(premium_since.timestamp()))
                    if premium_since
                    else "N/A"
                ),
                "user.color": str(block.color)
                if block.color
                else "N/A",
                "user.top_role": str(block.top_role)
                if len(roles) > 0
                else "N/A",
                "user.role_list": ", ".join(
                    r.name for r in roles
                )
                or "N/A",
                "user.role_text_list": ", ".join(
                    r.mention for r in roles
                )
                or "N/A",
            })

            sorted_members = sorted(
                block.guild.members,
                key=lambda m: m.joined_at or datetime.max,
            )
            position = sorted_members.index(block) + 1
            data.update({
                "user.join_position": str(position),
                "user.join_position_suffix": f"{position}{get_suffix(position)}",
            })

    elif isinstance(
        block, (TextChannel, VoiceChannel, Thread)
    ):
        data.update({
            "channel.name": block.name,
            "channel.id": str(block.id),
            "channel.mention": block.mention,
            "channel.type": str(block.type),
            "channel.position": str(block.position),
        })

        if hasattr(block, "topic"):
            data["channel.topic"] = str(
                block.topic or "N/A"
            )

        if hasattr(block, "category"):
            data.update({
                "channel.category_id": (
                    str(block.category.id)
                    if block.category
                    else "N/A"
                ),
                "channel.category_name": (
                    str(block.category.name)
                    if block.category
                    else "N/A"
                ),
            })

        if hasattr(block, "slowmode_delay"):
            data["channel.slowmode_delay"] = str(
                block.slowmode_delay
            )

    elif isinstance(block, Guild):
        data.update({
            "guild.name": str(block.name),
            "guild.id": str(block.id),
            "guild.count": str(block.member_count),
            "guild.region": (
                str(block.region)
                if hasattr(block, "region")
                else "N/A"
            ),
            "guild.shard": str(block.shard_id),
            "guild.owner_id": str(block.owner_id),
            "guild.created_at": str(
                int(block.created_at.timestamp())
            ),
            "guild.emoji_count": str(len(block.emojis)),
            "guild.role_count": str(len(block.roles)),
            "guild.boost_count": str(
                block.premium_subscription_count or 0
            ),
            "guild.boost_tier": str(
                block.premium_tier or "No Level"
            ),
            "guild.preferred_locale": str(
                block.preferred_locale
            ),
            "guild.key_features": ", ".join(block.features)
            or "N/A",
            "guild.icon": str(
                block.icon.url if block.icon else "N/A"
            ),
            "guild.banner": str(
                block.banner.url if block.banner else "N/A"
            ),
            "guild.splash": str(
                block.splash.url if block.splash else "N/A"
            ),
            "guild.discovery": str(
                block.discovery_splash.url
                if block.discovery_splash
                else "N/A"
            ),
            "guild.max_presences": str(
                block.max_presences or "N/A"
            ),
            "guild.max_members": str(
                block.max_members or "N/A"
            ),
            "guild.max_users": str(
                block.max_members or "N/A"
            ),
            "guild.max_video_channel_users": str(
                block.max_video_channel_users or "N/A"
            ),
            "guild.afk_timeout": str(block.afk_timeout),
            "guild.afk_channel": str(
                block.afk_channel or "N/A"
            ),
            "guild.channels": ", ".join(
                c.name for c in block.channels
            )
            or "N/A",
            "guild.channels_count": str(
                len(block.channels)
            ),
            "guild.text_channels": ", ".join(
                c.name for c in block.text_channels
            )
            or "N/A",
            "guild.text_channels_count": str(
                len(block.text_channels)
            ),
            "guild.voice_channels": ", ".join(
                c.name for c in block.voice_channels
            )
            or "N/A",
            "guild.voice_channels_count": str(
                len(block.voice_channels)
            ),
            "guild.category_channels": ", ".join(
                c.name for c in block.categories
            )
            or "N/A",
            "guild.category_channels_count": str(
                len(block.categories)
            ),
        })

    for name in dir(block):
        if name.startswith("_"):
            continue

        try:
            value = getattr(block, name)
        except (ValueError, AttributeError):
            continue

        if callable(value):
            continue

        if isinstance(value, datetime):
            data[f"{key}.{name}"] = str(
                int(value.timestamp())
            )

        elif isinstance(value, timedelta):
            data[f"{key}.{name}"] = format_timespan(value)

        elif isinstance(value, int):
            data[f"{key}.{name}"] = (
                format(value, ",")
                if not name.endswith(("id", "duration"))
                else str(value)
            )

        elif isinstance(
            value, (str, bool, Status, Asset, Color)
        ):
            data[f"{key}.{name}"] = str(value)

        elif isinstance(value, BaseModel):
            base_model_data = to_dict(value)
            for __key, val in base_model_data.items():
                data[f"{key}.{__key}"] = val

    if "user.display_avatar" in data:
        data["user.avatar"] = data["user.display_avatar"]

    return data


def parse(
    string: str,
    blocks: List[Block | Tuple[str, Block]] = [],
    **kwargs,
) -> str:
    """
    Parse a string with a given environment.
    """
    local_blocks = blocks.copy()
    local_blocks.extend(kwargs.items())
    string = string.replace("{embed}", "{embed:0}")
    string = string.replace("{timestamp}", "{timestamp:}")
    variables: Dict[str, str] = {}
    for block in local_blocks:
        if isinstance(block, tuple):
            variables.update(to_dict(block[1], block[0]))
        else:
            variables.update(to_dict(block))

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name == "guild.member_count":
            return variables.get(name, name)
        name_mod = name.replace("author", "user").replace(
            "member", "user"
        )
        value = variables.get(name_mod)
        if name_mod == "user.bot" and value in ("0", "1"):
            return "Yes" if value == "1" else "No"
        return value or name

    return pattern.sub(replace, string)
