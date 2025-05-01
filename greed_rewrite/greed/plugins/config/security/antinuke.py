from __future__ import annotations

from discord.ext.commands import (
    Cog, 
    command, 
    check, 
    hybrid_group, 
    has_permissions
)
from discord import (
    AuditLogAction,
    AuditLogEntry,
    Member,
    Guild,
    User,
    Object,
    Role,
    utils,
    Embed,
    Permissions,
    TextChannel,
    Webhook,
    CategoryChannel,
    VoiceChannel,
)

from asyncio import gather, Lock, sleep
from datetime import timedelta, datetime
from collections import defaultdict
from typing import Optional, Union, Dict, Set, List, Any
from contextlib import suppress

from greed.framework import Context, Greed
from greed.framework.tools.conversion.discord import TouchableMember

MODULES = [
    "bot_add",
    "role_update",
    "channel_update",
    "guild_update",
    "kick",
    "ban",
    "member_prune",
    "webhooks",
]

def trusted():
    async def predicate(ctx: Context):
        """
        Check if the user is the guild owner, bot owner, or an antinuke admin.
        """
        if ctx.author.id in ctx.bot.owner_ids:
            return True
        
        check = await ctx.bot.db.fetchval(
            """
            SELECT COUNT(*) 
            FROM antinuke_admin 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            ctx.guild.id,
            ctx.author.id,
        )
        if check == 0 and not ctx.author.id == ctx.guild.owner_id:
            await ctx.embed(
                message="You aren't the guild owner or an antinuke admin!",
                message_type="warned"
            )
            return False
        
        return True

    return check(predicate)


def get_action(e: Union[AuditLogAction, AuditLogEntry]) -> str:
    """
    Get the action name from the audit log entry.
    """
    if isinstance(e, AuditLogAction):
        if "webhook" in str(e).lower():
            return "webhooks"
        return (
            str(e)
            .split(".")[-1]
            .replace("create", "update")
            .replace("delete", "update")
        )

    else:
        if "webhook" in str(e.action).lower():
            return "webhooks"
        
        return (
            str(e.action)
            .replace("create", "update")
            .replace("delete", "update")
            .split(".")[-1]
        )


class ActionBucket:
    """
    A class that implements a bucket system to track actions.
    """
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self.actions: List[datetime] = []
        
    def add_action(self) -> int:
        now = datetime.utcnow()
        self.actions = [t for t in self.actions if now - t < timedelta(seconds=self.window_seconds)]
        self.actions.append(now)
        return len(self.actions)
        
    def get_count(self) -> int:
        now = datetime.utcnow()
        self.actions = [t for t in self.actions if now - t < timedelta(seconds=self.window_seconds)]
        return len(self.actions)


class RateLimiter:
    """
    A class that implements a rate limiter to track actions.
    """
    def __init__(self):
        self.buckets: Dict[str, ActionBucket] = {}
        
    def check_rate(self, key: str, threshold: int, window: int = 60) -> bool:
        if key not in self.buckets:
            self.buckets[key] = ActionBucket(window)
        return self.buckets[key].add_action() > threshold


class AntiNuke(Cog):
    """
    A class that implements an anti-nuke system to protect a guild from malicious actions.
    """
    def __init__(self, bot: Greed):
        self.bot = bot
        self._locks = defaultdict(Lock)
        self.punishments = {}
        self.guilds = {}
        self.thresholds = {}
        self.rate_limiters: Dict[int, RateLimiter] = {}
        self.cleanup_queue: Dict[int, Set[str]] = defaultdict(set)
        self.entry_updating = False

    async def cog_load(self):
        await self.make_cache()

    def serialize(self, data: dict):
        """
        Serialize the data.
        """
        data.pop("guild_id", None)
        return data

    async def make_cache(self):
        """
        Make the cache.
        """
        try:
            rows = await self.bot.db.fetch(
                """
                SELECT guild_id, bot_add, role_update, channel_update, kick, ban, guild_update, member_prune, webhooks 
                FROM antinuke
                """
            )
            self.guilds = {}
            
            for r in rows:
                try:
                    guild_id = r.guild_id
                    guild_dict = self.serialize(dict(r))
                    self.guilds[guild_id] = guild_dict
                
                except Exception:
                    continue
        
            threshold_rows = await self.bot.db.fetch(
                """
                SELECT * FROM antinuke_threshold
                """
            )
            self.thresholds = {}
            for r in threshold_rows:
                try:
                    guild_id = r.guild_id
                    guild_dict = self.serialize(dict(r))
                    self.thresholds[guild_id] = guild_dict
                
                except Exception:
                    continue
                    
            return True
        
        except Exception:
            return False

    def make_reason(self, reason: str) -> str:
        """
        Make a reason for the punishment.
        """
        return f"[ {self.bot.user.name} antinuke ] {reason}"

    async def get_thresholds(
        self, guild: Guild, action: Union[AuditLogAction,str]
    ) -> Optional[int]:
        """
        Get the thresholds for the guild.
        """
        try:
            if guild.id in self.guilds:
                action_str = get_action(action) if isinstance(action, AuditLogAction) else action
                
                if guild.id in self.thresholds:
                    return self.thresholds[guild.id].get(action_str, 0)
                
                try:
                    threshold = await self.bot.db.fetchval(
                        f"""
                        SELECT {action_str} 
                        FROM antinuke_threshold 
                        WHERE guild_id = $1
                        """,
                        guild.id,
                    )
                    if threshold is not None:
                        return int(threshold)
                except Exception:
                    pass
                    
            return 0
        
        except Exception:
            return None
            
    async def do_ban(self, guild: Guild, user: Union[User, Member], reason: str):
        """
        Do a ban on the user.
        """
        try:
            if hasattr(user, "top_role"):
                if user.top_role >= guild.me.top_role:
                    return False
                
                if user.id == guild.owner_id:
                    return False
            
            if await self.bot.glory_cache.ratelimited(f"punishment-{guild.id}-{user.id}", 3, 15) != 0:
                return False

            await guild.ban(Object(user.id), reason=reason)
            return True
        
        except Exception:
            return False

    async def do_kick(self, guild: Guild, user: Union[User, Member], reason: str):
        """
        Do a kick on the user.
        """
        try:
            if hasattr(user, "top_role"):
                if user.top_role.position >= guild.me.top_role.position:
                    return False
                
                if user.id == guild.owner_id:
                    return False
            
            if await self.bot.glory_cache.ratelimited(f"punishment-{guild.id}-{user.id}", 3, 15) != 0:
                return False
                
            await user.kick(reason=reason)
            return True
        
        except Exception:
            return False

    async def do_strip(
            self, 
            guild: Guild, 
            user: Union[Member, User], 
            reason: str
        ):
        """
        Do a strip on the user.
        """
        try:
            if isinstance(user, User):
                return False
                
            if user.top_role >= guild.me.top_role:
                return False
                
            if user.id == guild.owner_id:
                return False
                
            if await self.bot.glory_cache.ratelimited(f"punishment-{guild.id}-{user.id}", 3, 15) != 0:
                return False
                
            after_roles = [r for r in user.roles if not r.is_assignable()]
            await user.edit(roles=after_roles, reason=reason)
            return True
        
        except Exception:
            return False

    async def do_punishment(
            self, 
            guild: Guild, 
            user: Union[User, Member], 
            reason: str
        ):
        """
        Do a punishment on the user.
        """
        try:
            punishment = await self.bot.db.fetchval(
                """
                SELECT punishment 
                FROM antinuke 
                WHERE guild_id = $1
                """,
                guild.id
            )
            if punishment is None:
                punishment = "ban"
            
            result = False
            if user.bot:
                if not guild.me.guild_permissions.ban_members:
                    return
                
                result = await self.do_ban(guild, user, reason)
            elif punishment.lower() == "ban":
                if not guild.me.guild_permissions.ban_members:
                    return

                result = await self.do_ban(guild, user, reason)
            elif punishment.lower() == "kick":
                if not guild.me.guild_permissions.kick_members:
                    return

                result = await self.do_kick(guild, user, reason)
            else:
                if not guild.me.guild_permissions.manage_roles:
                    return
                
                result = await self.do_strip(guild, user, reason)
                
            return result
        
        except Exception:
            return False

    def get_rate_limiter(self, guild_id: int) -> RateLimiter:
        """
        Get the rate limiter for the guild.
        """
        if guild_id not in self.rate_limiters:
            self.rate_limiters[guild_id] = RateLimiter()
        return self.rate_limiters[guild_id]

    async def check_rate_limit(
            self, 
            guild: Guild, 
            user_id: int, 
            action: Union[AuditLogAction, str], 
            threshold: int
        ) -> bool:
        """
        Check if the user has exceeded the rate limit.
        """
        if isinstance(action, AuditLogAction):
            action_str = get_action(action)
        else:
            action_str = action
            
        rate_limiter = self.get_rate_limiter(guild.id)
        key = f"{user_id}:{action_str}"
        
        return rate_limiter.check_rate(key, threshold)

    async def queue_cleanup(self, guild_id: int, action_key: str):
        """
        Queue a cleanup action.
        """
        self.cleanup_queue[guild_id].add(action_key)
        
    async def process_cleanup_queue(self, guild: Guild):
        """
        Process the cleanup queue.
        """
        if not self.cleanup_queue[guild.id]:
            return
            
        async with self.locks[f"cleanup-{guild.id}"]:
            for action_key in list(self.cleanup_queue[guild.id]):
                try:
                    await self.attempt_cleanup(guild.id, action_key)
                    self.cleanup_queue[guild.id].remove(action_key)
                except Exception:
                    pass
                await sleep(1)

    async def check_entry(
            self, 
            guild: Guild, 
            entry: AuditLogEntry
        ) -> bool:
        """
        Check if the entry is valid.
        """
        if entry.user is None:
            return True
            
        try:
            threshold = await self.get_thresholds(guild, entry.action)
            
            if await self.bot.db.fetchval(
                """
                SELECT user_id 
                FROM antinuke_whitelist 
                WHERE user_id = $1 
                AND guild_id = $2
                """,
                entry.user.id,
                guild.id,
            ):
                return True
                
            if (
                entry.user.id == guild.owner_id
                or entry.user.id == self.bot.user.id
                or (hasattr(entry.user, "top_role") and entry.user.top_role >= guild.me.top_role)
            ):
                return True
                
            if await self.check_rate_limit(guild, entry.user.id, entry.action, threshold):
                return False
                
        except Exception:
            pass
            
        return True

    def check_guild(
            self, 
            guild: Guild, 
            action: Union[AuditLogAction, str]
        ):
        """
        Check if the guild has the action enabled.
        """
        if guild.id in self.guilds:
            
            if isinstance(action, AuditLogAction):
                action_str = get_action(action)
                result = action_str in self.guilds[guild.id]
                
                if result:
                    enabled_value = self.guilds[guild.id].get(action_str)
                    return enabled_value
            else:
                result = action in self.guilds[guild.id]
                
                if result:
                    enabled_value = self.guilds[guild.id].get(action)
                    return enabled_value
        return False

    async def get_audit(
            self, 
            guild: Guild, 
            action: AuditLogAction = None
        ):
        """
        Get the audit log entry.
        """
        try:
            if not guild.me.guild_permissions.view_audit_log:
                return None
            
            time_window = 5 if action in [AuditLogAction.webhook_create, AuditLogAction.webhook_update] else 3
                
            try:
                if action is not None:
                    audits = [
                        a
                        async for a in guild.audit_logs(
                            limit=2,
                            after=utils.utcnow() - timedelta(seconds=time_window),
                            action=action,
                        )
                    ]
                    if not audits:
                        return None
                    audit = audits[0]
                else:
                    audit = [
                        a
                        async for a in guild.audit_logs(
                            limit=1, after=utils.utcnow() - timedelta(seconds=time_window)
                        )
                    ][0]
                    
                if audit.user_id == self.bot.user.id and audit.reason and "|" in audit.reason:
                    try:
                        user_id = int(audit.reason.split(" | ")[-1].strip())
                        audit.user = self.bot.get_user(user_id)
                    
                    except (ValueError, IndexError):
                        pass
                        
                if action in [AuditLogAction.webhook_create, AuditLogAction.webhook_update]:                    
                    return audit
                
                return audit
            
            except IndexError:
                return None
            
        except Exception:
            return None

    async def check_role(self, role: Role) -> bool:
        """
        Check if the role has the required permissions.
        """
        if (
            role.permissions.administrator
            or role.permissions.manage_guild
            or role.permissions.kick_members
            or role.permissions.ban_members
            or role.permissions.manage_roles
            or role.permissions.manage_channels
            or role.permissions.manage_webhooks
        ):
            return True
        return False

    async def get_channel_state(
            self, 
            channel: TextChannel | VoiceChannel | CategoryChannel
        ) -> dict:
        """
        Get the channel state.
        """
        try:
            state = {
                "name": getattr(channel, "name", "Unknown Channel"),
                "position": getattr(channel, "position", 0),
            }

            if hasattr(channel, "overwrites"):
                state["overwrites"] = channel.overwrites
                
            if hasattr(channel, "topic"):
                state["topic"] = channel.topic
                
            if hasattr(channel, "slowmode_delay"):
                state["slowmode_delay"] = channel.slowmode_delay
                
            if hasattr(channel, "nsfw"):
                state["nsfw"] = channel.nsfw
                
            if hasattr(channel, "bitrate"):
                state["bitrate"] = channel.bitrate
                
            if hasattr(channel, "user_limit"):
                state["user_limit"] = channel.user_limit
                
            if hasattr(channel, "rtc_region"):
                state["rtc_region"] = channel.rtc_region
                
            if hasattr(channel, "video_quality_mode"):
                state["video_quality_mode"] = channel.video_quality_mode
                
            if hasattr(channel, "type"):
                state["type"] = str(channel.type.name)
                
            return state
            
        except Exception:
            return {"name": "Unknown Channel", "error": True}

    async def get_role_state(self, role: Role) -> dict:
        """
        Get the role state.
        """
        try:
            state = {
                "name": getattr(role, "name", "Unknown Role"),
                "permissions": Permissions(getattr(role, "permissions", Permissions.none()).value),
                "color": getattr(role, "color", 0),
                "hoist": getattr(role, "hoist", False),
                "mentionable": getattr(role, "mentionable", False)
            }
            return state
        
        except Exception:
            return {
                "name": "Unknown Role", 
                "permissions": Permissions.none(), 
                "error": True
            }

    async def get_guild_state(self, guild: Guild) -> dict:
        """
        Get the guild state.
        """
        state = {
            "name": guild.name,
            "description": guild.description,
        }
        
        if guild.icon:
            try:
                state["icon_bytes"] = await guild.icon.read()
            except:
                pass
                
        if guild.banner:
            try:
                state["banner_bytes"] = await guild.banner.read()
            except:
                pass
                
        if guild.splash:
            try:
                state["splash_bytes"] = await guild.splash.read()
            except:
                pass
                
        return state

    async def attempt_cleanup(
            self, 
            guild_id: int, 
            action_key: str
    ):
        """
        Helper method to attempt cleanup actions with retries.
        """
        for _ in range(5):
            if await self.bot.glory_cache.ratelimited(f"cleanup-{guild_id}", 1, 10) == 0:
                try:
                    return await self.attempt_cleanup_action(guild_id, action_key)
                except Exception:
                    pass
            await sleep(2)
        return None

    async def attempt_cleanup_action(self, guild_id: int, action_key: str):
        """
        Helper method to attempt cleanup actions with retries.
        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
            
        try:
            action_type, target_id = action_key.split(":")
            target_id = int(target_id)
            
            await self.initialize_guild_storage(guild)
            
            if action_type == "role_delete":
                deleted_roles = getattr(guild, "_deleted_roles", {})
                if target_id in deleted_roles:
                    role_data = deleted_roles[target_id]
                    try:
                        await guild.create_role(
                            name=role_data.get("name", "Restored Role"),
                            permissions=role_data.get("permissions", Permissions.none()),
                            color=role_data.get("color", 0),
                            hoist=role_data.get("hoist", False),
                            mentionable=role_data.get("mentionable", False),
                            reason=self.make_reason("Restoring deleted role")
                        )
                    except Exception:
                        pass
                else:
                    pass
                
            elif action_type == "role_update":
                role = guild.get_role(target_id)
                if role:
                    role_data = getattr(role, "_before_state", None)
                    if role_data:
                        try:
                            edit_kwargs = {k: v for k, v in role_data.items()}
                            await role.edit(**edit_kwargs, reason=self.make_reason("Restoring role settings"))
                        except Exception:
                            pass
                    else:
                        pass
                else:
                    pass
                    
            elif action_type == "channel_delete":
                channel = guild.get_channel(target_id)
                
                if not channel:
                    deleted_channels = getattr(guild, "_deleted_channels", {})
                    
                    if target_id in deleted_channels:
                        channel_data = deleted_channels[target_id]
                        try:
                            
                            if channel_data.get("type") == "text":
                                await guild.create_text_channel(
                                    name=channel_data.get("name", "restored-channel"),
                                    topic=channel_data.get("topic"),
                                    position=channel_data.get("position"),
                                    overwrites=channel_data.get("overwrites", {}),
                                    reason=self.make_reason("Restoring deleted channel")
                                )
                            
                            elif channel_data.get("type") == "voice":
                                await guild.create_voice_channel(
                                    name=channel_data.get("name", "Restored Channel"),
                                    position=channel_data.get("position"),
                                    overwrites=channel_data.get("overwrites", {}),
                                    reason=self.make_reason("Restoring deleted channel")
                                )
                        
                        except Exception:
                            pass
                    else:
                        pass
                
            elif action_type == "channel_update":
                channel = guild.get_channel(target_id)
                if channel:
                    before_state = getattr(channel, "_before_state", None)
                    
                    if before_state:
                        try:
                            update_kwargs = {k: v for k, v in before_state.items() if hasattr(channel, k)}
                            
                            if update_kwargs:
                                await channel.edit(**update_kwargs, reason=self.make_reason("Restoring channel settings"))
                        
                        except Exception:
                            pass
                    else:
                        pass
                else:
                    pass
                
            elif action_type == "webhook_create":
                channel = guild.get_channel(target_id)
                if channel:
                    try:
                        webhooks = await channel.webhooks()
                        deleted = 0
                        
                        for webhook in webhooks:
                            try:
                                await webhook.delete(reason=self.make_reason("Removing unauthorized webhook"))
                                deleted += 1
                            except Exception:
                                pass
                        
                        if deleted > 0:
                            pass
                    
                    except Exception:
                        pass
                else:
                    pass
                        
            elif action_type == "role_assignment":
                member = guild.get_member(target_id)
                if member:
                    try:
                        dangerous_roles = getattr(member, "_dangerous_roles", [])
                        
                        if dangerous_roles:
                            await member.remove_roles(*dangerous_roles, reason=self.make_reason("Removing unauthorized roles"))
                            pass
                        else:
                            pass
                    except Exception:
                        pass
                else:
                    pass
                        
            elif action_type == "ban":
                try:
                    await guild.unban(Object(target_id), reason=self.make_reason("Reversing unauthorized ban"))
                    pass
                
                except Exception:
                    pass
                    
            elif action_type == "guild_update":
                before_state = getattr(guild, "_before_state", None)
                if before_state:
                    try:
                        edit_kwargs = {}    
                        
                        if "name" in before_state:
                            edit_kwargs["name"] = before_state["name"]
                        
                        if "description" in before_state:
                            edit_kwargs["description"] = before_state["description"]
                        
                        if "icon_bytes" in before_state:
                            edit_kwargs["icon"] = before_state["icon_bytes"]
                        
                        if "banner_bytes" in before_state:
                            edit_kwargs["banner"] = before_state["banner_bytes"]
                        
                        if "splash_bytes" in before_state:
                            edit_kwargs["splash"] = before_state["splash_bytes"]
                        
                        if edit_kwargs:
                            await guild.edit(**edit_kwargs, reason=self.make_reason("Restoring guild settings"))
                    
                    except Exception:
                        pass
                else:
                    pass
                    
        except Exception:
            pass

    async def handle_action(
        self, 
        guild: Guild, 
        entry: AuditLogEntry, 
        cleanup_key: Optional[str] = None
    ):
        """
        Handle the action based on the audit log entry.
        """
        if not await self.check_entry(guild, entry):
            if cleanup_key:
                await self.queue_cleanup(guild.id, cleanup_key)
                
            reason = self.make_reason(f"User caught performing {entry.action}")
            await self.do_punishment(guild, entry.user, reason)
            
            await self.process_cleanup_queue(guild)
            return False
        
        return True

    @Cog.listener("on_guild_role_update")
    async def role_update(
        self, 
        before: Role, 
        after: Role
    ):
        """
        Listen for role update events and punish the user if necessary.
        """
        try:
            if not before.guild.me.guild_permissions.view_audit_log:
                return
                
            if await self.check_role(after) is not True:
                return
                
            if self.check_guild(after.guild, "role_update") is not True:
                return
                
            entry = await self.get_audit(after.guild, AuditLogAction.role_update)
            if entry is None:
                return
                
            storage_initialized = await self.initialize_guild_storage(after.guild)
            if not storage_initialized:
                pass
            
            try:
                await self.initialize_object_attributes(after)
            except Exception:
                pass

            try:
                role_state = await self.get_role_state(before)
                attr_set = self.safe_set_attribute(after, "_before_state", role_state)
                if attr_set:
                    pass
                else:
                    pass
            
            except Exception:
                pass
            
            cleanup_key = f"role_update:{after.id}"
            await self.handle_action(after.guild, entry, cleanup_key)
        
        except Exception:
            pass

    @Cog.listener("on_guild_role_delete") 
    async def role_delete(self, role: Role):
        """
        Listen for role deletion events and punish the user if necessary.
        """
        try:
            guild = role.guild
            if self.check_guild(guild, "role_update") is not True:
                return
                
            storage_initialized = await self.initialize_guild_storage(guild)
            if not storage_initialized:
                pass
            
            try:
                role_state = await self.get_role_state(role)
                
                deleted_roles = self.safe_get_attribute(guild, "_deleted_roles", {})
                
                if isinstance(deleted_roles, dict):
                    deleted_roles[role.id] = role_state
                    
                    self.safe_set_attribute(guild, "_deleted_roles", deleted_roles)
                    pass
                else:
                    pass
            except Exception:
                pass
                
            entry = await self.get_audit(guild, AuditLogAction.role_delete)
            if entry is None:
                return
                
            cleanup_key = f"role_delete:{role.id}"
            await self.handle_action(guild, entry, cleanup_key)
        
        except Exception:
            pass

    @Cog.listener("on_guild_channel_delete")
    async def channel_delete(self, channel):
        """
        Listen for channel deletion events and punish the user if necessary.
        """
        try:
            guild = channel.guild
            if self.check_guild(guild, "channel_update") is not True:
                return
                
            storage_initialized = await self.initialize_guild_storage(guild)
            if not storage_initialized:
                pass
                
            try:
                channel_state = await self.get_channel_state(channel)
                if hasattr(channel, "type"):
                    channel_state["type"] = channel.type.name
                
                deleted_channels = self.safe_get_attribute(guild, "_deleted_channels", {})
                if isinstance(deleted_channels, dict):
                    deleted_channels[channel.id] = channel_state
                    
                    self.safe_set_attribute(guild, "_deleted_channels", deleted_channels)
                    pass
                else:
                    pass
                
            except Exception:
                pass
                
            entry = await self.get_audit(guild, AuditLogAction.channel_delete)
            if entry is None:
                return
                
            cleanup_key = f"channel_delete:{channel.id}"
            await self.handle_action(guild, entry, cleanup_key)
        
        except Exception:
            pass

    @Cog.listener("on_guild_channel_update")
    async def channel_update(self, before: TextChannel, after: TextChannel):
        """
        Listen for channel update events and punish the user if necessary.
        """
        try:
            guild = after.guild
            if self.check_guild(guild, "channel_update") is not True:
                return
                
            entry = await self.get_audit(guild, AuditLogAction.channel_update)
            if entry is None:
                return
                
            storage_initialized = await self.initialize_guild_storage(guild)
            if not storage_initialized:
                pass
            
            try:
                await self.initialize_object_attributes(after)
            
            except Exception:
                pass
            
            try:
                channel_state = await self.get_channel_state(before)
                attr_set = self.safe_set_attribute(after, "_before_state", channel_state)
                if attr_set:
                    pass
                else:
                    pass
            
            except Exception:
                pass
            
            await self.handle_action(guild, entry, f"channel_update:{after.id}")
        
        except Exception:
            pass
            
            try:
                channel_state = await self.get_channel_state(before)
                attr_set = self.safe_set_attribute(after, "_before_state", channel_state)
            
            except Exception:
                pass
                
            await self.handle_action(guild, entry, f"channel_update:{after.id}")


    @Cog.listener()
    async def on_webhooks_update(self, channel: TextChannel):
        """
        Listen for webhook update events and punish the user if necessary.
        """
        try:
            guild: Guild = channel.guild
            
            webhook_protection = self.check_guild(guild, AuditLogAction.webhook_create)
            if webhook_protection is not True:
                return
                
            entry: Optional[AuditLogEntry] = await self.get_audit(guild, AuditLogAction.webhook_create)
            if entry is None:
                entry = await self.get_audit(guild, AuditLogAction.webhook_update)
                if entry is None:
                    return
                    
            webhook_id: int = entry.target.id if entry.target else 0
            if not webhook_id:
                return
                
            try:
                webhook_state: Dict[str, Any] = {
                    "id": webhook_id,
                    "name": None,
                    "channel_id": None,
                    "type": 1,
                    "avatar": None,
                    "created_at": entry.created_at,
                    "created_by": entry.user.id if entry.user else None
                }
                
                if entry.changes:
                    if hasattr(entry.changes, "name"):
                        webhook_state["name"] = entry.changes.name.new
                    
                    if hasattr(entry.changes, "channel"):
                        webhook_state["channel_id"] = getattr(entry.changes.channel.new, "id", None)
                    
                    if hasattr(entry.changes, "type"):
                        webhook_state["type"] = entry.changes.type.new
                    
                    if hasattr(entry.changes, "avatar"):
                        webhook_state["avatar"] = entry.changes.avatar.new
                
                if webhook_state["name"] is None:
                    webhook_state["name"] = "Unknown Webhook"
            
                if webhook_state["channel_id"] is None and hasattr(entry.target, "channel_id"):
                    webhook_state["channel_id"] = entry.target.channel_id
                
                elif webhook_state["channel_id"] is None:
                    webhook_state["channel_id"] = channel.id
                
                storage_initialized: bool = await self.initialize_guild_storage(guild)
                if not storage_initialized:
                    pass
                
                webhooks: Dict[int, Dict[str, Any]] = self.safe_get_attribute(guild, "_webhooks", {})
                webhooks[webhook_id] = webhook_state
                self.safe_set_attribute(guild, "_webhooks", webhooks)
                
            except Exception:
                pass
                    
            await self.handle_action(guild, entry, f"webhook_create:{webhook_id}")
            
        except Exception:
            pass

    @Cog.listener()
    async def on_webhook_delete(self, webhook: Webhook):
        """
        Listen for webhook delete events and punish the user if necessary.
        """
        try:
            guild: Guild = webhook.guild
            
            webhook_protection = self.check_guild(guild, AuditLogAction.webhook_delete)
            if webhook_protection is not True:
                return
                
            entry: Optional[AuditLogEntry] = await self.get_audit(guild, AuditLogAction.webhook_delete)
            if entry is None:
                return
                
            webhook_id: int = webhook.id
                
            try:
                webhook_state: Dict[str, Any] = {
                    "id": webhook_id,
                    "name": webhook.name,
                    "channel_id": webhook.channel_id,
                    "type": 1,
                    "avatar": webhook.avatar.url if webhook.avatar else None,
                    "deleted_at": entry.created_at if entry else datetime.utcnow(),
                    "deleted_by": entry.user.id if entry and entry.user else None
                }
                
                storage_initialized: bool = await self.initialize_guild_storage(guild)
                if not storage_initialized:
                    pass
                
                deleted_webhooks: Dict[int, Dict[str, Any]] = self.safe_get_attribute(guild, "_deleted_webhooks", {})
                deleted_webhooks[webhook_id] = webhook_state
                self.safe_set_attribute(guild, "_deleted_webhooks", deleted_webhooks)
                
            except Exception:
                pass
                
            if entry:
                await self.handle_action(guild, entry, f"webhook_delete:{webhook_id}")
            
        except Exception:
            pass

    @Cog.listener("on_audit_log_entry_create")
    async def on_member_action(self, entry: AuditLogEntry):
        """
        Listen for member actions and punish the user if necessary.
        """
        if self.check_guild(entry.guild, entry.action) is False:
            return
            
        if entry.action in [AuditLogAction.kick, AuditLogAction.ban, AuditLogAction.member_prune]:
            if entry.user_id == self.bot.user.id and entry.reason and "|" in entry.reason:
                entry.user = self.bot.get_user(int(entry.reason.split(" | ")[-1].strip()))
                
            await self.handle_action(entry.guild, entry, f"{entry.action.name}:{entry.target.id}")

    @Cog.listener("on_member_update")
    async def dangerous_role_assignment(
        self, 
        before: Member, 
        after: Member
    ):
        """
        Listen for role assignment and punish the user if necessary.
        """
        try:
            if not before.guild.me.guild_permissions.view_audit_log:
                return
                
            if before.roles == after.roles:
                return
                
            if self.check_guild(after.guild, "role_update") is not True:
                return
                
            new_roles = [r for r in after.roles if r not in before.roles and r.is_assignable()]
            if not new_roles:
                return
                
            dangerous_roles = []
            for role in new_roles:
                if await self.check_role(role):
                    dangerous_roles.append(role)
                    
            if not dangerous_roles:
                return
                
            await self.initialize_guild_storage(after.guild)
            await self.initialize_object_attributes(after, {"_dangerous_roles": dangerous_roles})
            
            entry = await self.get_audit(after.guild, AuditLogAction.member_role_update)
            if not entry:
                return
                
            if after.guild.me.top_role.position <= after.top_role.position:
                return
                
            await self.handle_action(after.guild, entry, f"role_assignment:{after.id}")
        
        except Exception:
            pass
    
    @Cog.listener("on_guild_update")
    async def change_guild(
        self, 
        before: Guild, 
        after: Guild
    ):
        """
        Listen for guild update events and punish the user if necessary.
        """
        try:
            if self.check_guild(after, "guild_update") is not True:
                return
                
            storage_initialized = await self.initialize_guild_storage(after)
            if not storage_initialized:
                pass
            
            try:
                await self.initialize_object_attributes(after)
            except Exception:
                pass
            
            try:
                guild_state = await self.get_guild_state(before)
                attr_set = self.safe_set_attribute(after, "_before_state", guild_state)
                if attr_set:
                    pass
                else:
                    pass
            
            except Exception:
                pass
                
            entry = await self.get_audit(after, AuditLogAction.guild_update)
            if not entry:
                return
                
            await self.handle_action(after, entry, f"guild_update:{after.id}")
        
        except Exception:
            pass

    @Cog.listener("on_member_join")
    async def antibot(
        self, 
        member: Member
    ):
        """
        Listen for member join events and punish the user if necessary.
        """
        try:
            if not member.bot:
                return
                
            guild = member.guild
            if self.check_guild(guild, "bot_add") is not True:
                return
                
            entry = await self.get_audit(guild, AuditLogAction.bot_add)
            if not entry:
                return
                
            await self.handle_action(guild, entry, f"bot_add:{member.id}")
        
        except Exception:
            pass

    @hybrid_group(
        name="antinuke", 
        aliases=["an"], 
        invoke_without_command=True
    )
    async def antinuke(self, ctx: Context):
        """
        Protect your server from malicious actions.
        """
        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command.qualified_name)
    
    @trusted()
    @antinuke.command(name="enable", aliases=["e", "setup", "on"])
    async def antinuke_enable(self, ctx: Context):
        """
        Enable all antinuke settings with a default threshold of 0.
        """
        await self.bot.db.execute(
            """
            INSERT INTO antinuke (guild_id, bot_add, guild_update, channel_update, role_update, kick, ban, webhooks, member_prune, threshold)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (guild_id) DO UPDATE SET
            bot_add = excluded.bot_add,
            guild_update = excluded.guild_update,
            role_update = excluded.role_update,
            channel_update = excluded.channel_update,
            webhooks = excluded.webhooks,
            kick = excluded.kick,
            ban = excluded.ban,
            member_prune = excluded.member_prune,
            threshold = excluded.threshold
            """,
            ctx.guild.id,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            0,
        )
        self.guilds[ctx.guild.id] = {
            "bot_add": True,
            "guild_update": True,
            "channel_update": True,
            "role_update": True,
            "kick": True,
            "ban": True,
            "webhooks": True,
            "member_prune": True,
            "threshold": 0,
        }
        return await ctx.embed(
            message=f"AntiNuke is now enabled",
            message_type="approved"
        )

    @antinuke.command(name="disable", aliases=["off", "d", "reset"])
    @trusted()
    async def antinuke_disable(self, ctx: Context):
        """
        Disable all antinuke settings.
        """
        await self.bot.db.execute(
            """
            DELETE FROM antinuke 
            WHERE guild_id = $1
            """,
            ctx.guild.id
        )
        try:
            self.guilds.pop(ctx.guild.id)
        
        except Exception:
            pass
        
        return await ctx.embed(
            message="AntiNuke is now disabled",
            message_type="approved"
        )

    @antinuke.command(name="punishment", aliases=["punish"])
    @trusted()
    async def antinuke_punishment(
        self, 
        ctx: Context, 
        punishment: str
    ):
        """
        Set a punishment a user will recieve for breaking an antinuke rule.
        """
        if punishment.lower() not in ["ban", "kick", "strip"]:
            return await ctx.embed(
                message="Punishment not recognized, please use one of the following `ban`, `kick`, `strip`",
                message_type="warned"
            )
        
        await self.bot.db.execute(
            """
            UPDATE antinuke 
            SET punishment = $1 
            WHERE guild_id = $2
            """,
            punishment,
            ctx.guild.id,
        )
        
        return await ctx.embed(
            message=f"Antinuke punishment set to `{punishment}`",
            message_type="approved"
        )

    @antinuke.command(name="whitelist", aliases=["wl"])
    @trusted()
    async def antinuke_whitelist(
        self, 
        ctx: Context, 
        *, 
        user: Union[User, Member]
    ):
        """
        Whitelist a user from antinuke.
        """
        if await self.bot.db.fetchval(
            """
            SELECT user_id 
            FROM antinuke_whitelist 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            ctx.guild.id,
            user.id,
        ):
            await self.bot.db.execute(
                """
                DELETE FROM antinuke_whitelist 
                WHERE guild_id = $1 
                AND user_id = $2
                """,
                ctx.guild.id,
                user.id,
            )

            return await ctx.embed(
                message=f"Successfully unwhitelisted {user.name}",
                message_type="approved"
            )
        
        else:
            await self.bot.db.execute(
                """
                INSERT INTO antinuke_whitelist (guild_id, user_id) 
                VALUES($1,$2) 
                ON CONFLICT(guild_id,user_id) DO NOTHING
                """,
                ctx.guild.id,
                user.id,
            )
            
            return await ctx.embed(
                message=f"Successfully whitelisted {user.name}",
                message_type="approved"
            )

    @antinuke.command(name="trust", aliases=["admin"])
    @trusted()
    async def antinuke_trust(
        self, 
        ctx: Context, 
        *, 
        user: Union[User, Member]
    ):
        """
        Permit a user to use antinuke commands as an antinuke admin.
        """
        if await self.bot.db.fetchval(
            """
            SELECT user_id 
            FROM antinuke_admin 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            ctx.guild.id,
            user.id,
        ):
            await self.bot.db.execute(
                """
                DELETE FROM antinuke_admin 
                WHERE guild_id = $1 
                AND user_id = $2
                """,
                ctx.guild.id,
                user.id,
            )
            
            return await ctx.embed(
                message=f"Successfully untrusted {user.name}",
                message_type="approved"
            )
        else:
            await self.bot.db.execute(
                """
                INSERT INTO antinuke_admin (guild_id, user_id) 
                VALUES($1,$2) 
                ON CONFLICT(guild_id,user_id) DO NOTHING
                """,
                ctx.guild.id,
                user.id,
            )
            
            return await ctx.embed(
                message=f"Successfully trusted {user.name}",
                message_type="approved"
            )

    @antinuke.command(name="whitelisted", aliases=["whitelists", "wld"])
    @trusted()
    async def antinuke_whitelisted(self, ctx: Context):
        """
        List all users that cannot be effected by antinuke.
        """
        record = await self.bot.db.fetch(
            """
            SELECT * 
            FROM antinuke_whitelist 
            WHERE guild_id = $1
            """,
            ctx.guild.id
        )
        if not record:
            return await ctx.embed(
                message="No whitelisted members found!",
                message_type="warned"
            )

        entries = [
            f"{member.mention} (``{member.id}``)"
            for member in ctx.guild.members
            if member.id in [record["user_id"] for record in record]
        ]
        
        return await ctx.paginate(
            entries=entries, embed=Embed(title="Whitelisted Members"))

    @antinuke.command(name="trusted", aliases=["admins"])
    @trusted()
    async def antinuke_trusted(self, ctx: Context):
        """
        List all users that are trusted by antinuke.
        """
        record = await self.bot.db.fetch(
            """
            SELECT user_id 
            FROM antinuke_admin 
            WHERE guild_id = $1
            """,
            ctx.guild.id
        )
        if not record:
            return await ctx.embed(
                message="No trusted members found!",
                message_type="warned"
            )
        
        entries = [
            f"{member.mention} (``{member.id}``)"
            for member in ctx.guild.members
            if member.id in [record["user_id"] for record in record]
        ]
        
        return await ctx.paginate(
            entries=entries, embed=Embed(title="Trusted Members"))

    @antinuke.command(name="threshold", brief="Set the threshold until antinuke bans the user")
    @trusted()
    async def antinuke_threshold(
        self, 
        ctx: Context, 
        action: str, 
        threshold: int
    ):
        """
        Set the threshold until antinuke bans the user.
        """
        if action not in MODULES:
            return await ctx.embed(
                message="Invalid action provided!",
                message_type="warned"
            )
        
        if await self.bot.db.fetch(
            """
            SELECT * FROM antinuke_threshold 
            WHERE guild_id = $1
            """, 
            ctx.guild.id
        ):
            await self.bot.db.execute(
                f"""
                UPDATE antinuke_threshold 
                SET {action} = $1 
                WHERE guild_id = $2
                """,
                threshold,
                ctx.guild.id,
            )
        else:
            await self.bot.db.execute(
                """
                INSERT INTO antinuke_threshold (guild_id, {action}) 
                VALUES($1, $2)
                """,
                ctx.guild.id,
                threshold,
            )

        await self.make_cache()
        return await ctx.embed(
            message=f"Antinuke **threshold** set to `{threshold}` for **{action}**",
            message_type="approved"
        )

    async def get_users(self, ctx: Context, whitelisted: Optional[bool] = False):
        if whitelisted is False:
            users = [
                r.user_id
                for r in await self.bot.db.fetch(
                    """
                    SELECT user_id 
                    FROM antinuke_admin 
                    WHERE guild_id = $1
                    """,
                    ctx.guild.id,
                )
            ]
        else:
            users = [
                r.user_id
                for r in await self.bot.db.fetch(
                    """
                    SELECT user_id 
                    FROM antinuke_whitelist 
                    WHERE guild_id = $1
                    """,
                    ctx.guild.id,
                )
            ]
        _ = []
        for m in users:
            if user := self.bot.get_user(m):
                _.append(user)
        _.append(ctx.guild.owner)
        return _

    async def find_thres(self, guild: Guild, action: str):
        d = await self.get_thresholds(guild, action)
        if not d:
            d = 0
        return (action, d)

    def format_module(self, module: str):
        module = module.replace("_", " ")
        return f"**anti [{module}]({self.bot.domain}):**"

    @antinuke.command(name="settings", aliases=["config"])
    @trusted()
    async def antinuke_settings(self, ctx: Context):
        """
        List your antinuke settings along with their thresholds.
        """
        data = await self.bot.db.fetchrow(
            """
            SELECT * 
            FROM antinuke 
            WHERE guild_id = $1
            """,
            ctx.guild.id
        )
        if not data:
            return await ctx.embed(
                message="Antinuke is not setup!",
                message_type="warned"
            )
        try:
            thresholds = await gather(
                *[self.find_thres(ctx.guild, a) for a in MODULES]
            )
            thresholds = {a[0]: a[1] for a in thresholds}
        
        except Exception:
            thresholds = {a: 0 for a in MODULES}
        
        embed = Embed(title="Antinuke Settings")
        d = dict(data)
        d.pop("guild_id")
        description = f"**Punishment:** `{d.get('punishment','ban')}`\n"
        
        try:
            d.pop("punishment")
        
        except Exception:
            pass
        
        for k, v in d.items():
            if isinstance(v, tuple) or isinstance(k, tuple):
                continue
            
            if k == "threshold":
                continue
        
        embed.description = description
        whitelisted = [user for user in await self.get_users(ctx, True) if user is not None]
        admins = [user for user in await self.get_users(ctx, False) if user is not None]
        
        if len(whitelisted) > 0:
            embed.add_field(
                name="Whitelisted",
                value=", ".join(m.mention for m in whitelisted),
                inline=True,
            )
        
        if len(admins) > 0:
            embed.add_field(
                name="Admins", value=", ".join(m.mention for m in admins), inline=True
            )
        
        return await ctx.send(embed=embed)

    @antinuke.command(name="botadd", aliases=["bot", "ba", "bot_add"])
    @trusted()
    async def antinuke_bot_add(
        self, 
        ctx: Context, 
        state: bool
    ):
        """
        Toggle the anti bot add of antinuke.
        """
        return await self.antinuke_toggle(ctx, "bot_add", state)

    @antinuke.command(
        name="role",
        brief="toggle the anti role update of antinuke",
        aliases=["roles", "role_update"],
        parameters={
            "threshold": {
                "type": int,
                "required": False,
                "brief": "set the threshold until antinuke bans the user",
            }
        },
    )
    @trusted()
    async def antinuke_role_update(
        self, 
        ctx: Context, 
        state: bool
    ):
        """
        Toggle the anti role update of antinuke.
        """
        return await self.antinuke_toggle(ctx, "role_update", state)

    @antinuke.command(name="channel", aliases=["channels", "channel_update"])
    @trusted()
    async def antinuke_channel_update(
        self, 
        ctx: Context, 
        state: bool
    ):
        """
        Toggle the anti channel update of antinuke.
        """
        return await self.antinuke_toggle(ctx, "channel_update", state)

    @antinuke.command(name="webhooks")
    @trusted()
    async def antinuke_webhooks(
        self, 
        ctx: Context, 
        state: bool
    ):
        """
        Toggle the anti webhooks of antinuke.
        """
        return await self.antinuke_toggle(ctx, "webhooks", state)

    @antinuke.command(name="guild")
    @trusted()
    async def antinuke_guild_update(
        self, 
        ctx: Context, 
        state: bool
    ):
        """
        Toggle the anti guild update of antinuke.
        """
        return await self.antinuke_toggle(ctx, "guild_update", state)

    @antinuke.command(name="prune", aliases=["member_prune"])
    @trusted()
    async def antinuke_member_prune(self, ctx: Context, state: bool):
        """
        Toggle the anti member prune of antinuke.
        """
        return await self.antinuke_toggle(ctx, "member_prune", state)

    @antinuke.command(name="kick")
    @trusted()
    async def antinuke_kick(self, ctx: Context, state: bool):
        """
        Toggle the anti kick of antinuke.
        """
        return await self.antinuke_toggle(ctx, "kick", state)

    @antinuke.command(name="ban")
    @trusted()
    async def antinuke_ban(self, ctx: Context, state: bool):
        """
        Toggle the anti ban of antinuke.
        """
        return await self.antinuke_toggle(ctx, "ban", state)

    async def antinuke_toggle(
        self, 
        ctx: Context, 
        module: str, 
        state: bool,
    ):
        """
        Toggle the antinuke of antinuke.
        """
        modules = [
            "bot_add",
            "role_update",
            "channel_update",
            "guild_update",
            "kick",
            "ban",
            "member_prune",
            "webhooks",
        ]
        try:
            threshold = int(ctx.parameters.get("threshold", 0))
        
        except Exception:
            threshold = 0
            
        if module not in modules:
            for m in modules:
                if str(module).lower() in m.lower():
                    module = m
            
            if module not in modules:
                return await ctx.embed(
                    message=f"Module {module} is not a valid feature!",
                    message_type="warned"
                )

        if not await self.bot.db.fetchrow(
            """
            SELECT * FROM antinuke 
            WHERE guild_id = $1
            """, 
            ctx.guild.id
        ):
            return await ctx.embed(
                message="Antinuke is not setup!",
                message_type="warned"
            )

        await self.bot.db.execute(
            f"""
            UPDATE antinuke 
            SET {module} = $1 
            WHERE guild_id = $2
            """,
            state,
            ctx.guild.id,
        )
    
        if ctx.guild.id in self.guilds:
            self.guilds[ctx.guild.id][module] = state
        else:
            self.guilds[ctx.guild.id] = {module: state}

        if threshold > 0:
            has_threshold_entry = await self.bot.db.fetchval(
                """
                SELECT COUNT(*) 
                FROM antinuke_threshold 
                WHERE guild_id = $1
                """, 
                ctx.guild.id
            )
            
            if has_threshold_entry:
                await self.bot.db.execute(
                    f"""
                    UPDATE antinuke_threshold 
                    SET {module} = $1 
                    WHERE guild_id = $2
                    """,
                    threshold,
                    ctx.guild.id,
                )
            else:
                await self.bot.db.execute(
                    f"""
                    INSERT INTO antinuke_threshold (guild_id, {module}) 
                    VALUES($1, $2)
                    """,
                    ctx.guild.id,
                    threshold,
                )
            
            if ctx.guild.id in self.thresholds:
                self.thresholds[ctx.guild.id][module] = threshold
            else:
                self.thresholds[ctx.guild.id] = {module: threshold}

        if module == "webhooks":
            await self.make_cache()

        if threshold == 0:
            thres = ""
        else:
            thres = f" with a threshold of `{threshold}`"
        
        if state is True:
            status = "enabled"
        else:
            status = "disabled"
            
        return await ctx.embed(
            message=f"Successfully **{status}** `{module}`{thres}",
            message_type="approved"
        )

    @antinuke.command(name="modules", aliases=["features", "events"])
    @trusted()
    async def antinuke_modules(self, ctx: Context):
        """
        List all available antinuke modules.
        """
        return await ctx.embed(
            message=f"{MODULES}",
            message_type="neutral"
        )

    # @command(name="hardban", aliases=["hb"], brief="Hardban a user", example=",hardban @wurri")
    # @trusted()
    # @has_permissions(ban_members=True)
    # async def hardban(
    #     self, 
    #     ctx: Context, 
    #     user: Union[User, Member],
    #     *, 
    #     reason: str = "No reason provided"
    # ):
    #     """
    #     Hardban a user.
    #     """
    #     if isinstance(user, Member):
    #         await TouchableMember().check(ctx, user)

    #     record = await self.bot.db.fetchval(
    #         """
    #         SELECT user_id FROM hardban 
    #         WHERE guild_id = $1 
    #         AND user_id = $2
    #         """,
    #         ctx.guild.id,
    #         user.id,
    #     )
        
    #     if record:
    #         await ctx.prompt("User is already hardbanned. Do you want to unhardban?")
    #         await self.bot.db.execute(
    #             """
    #             DELETE FROM hardban WHERE guild_id = $1 
    #             AND user_id = $2
    #             """,    
    #             ctx.guild.id,
    #             user.id,
    #         )
    #         await ctx.guild.unban(
    #             user, 
    #             reason=f"User unhardbanned by {ctx.author.name} ({ctx.author.id}) / {reason}"
    #         )
    #         return await ctx.embed(
    #             message=f"Successfully unhardbanned {user.name}",
    #             message_type="approved"
    #         )
    #     else:
    #         await self.bot.db.execute(
    #             """
    #             INSERT INTO hardban (guild_id, user_id) 
    #             VALUES($1, $2)
    #             """,
    #             ctx.guild.id,
    #             user.id,
    #         )
    #         await ctx.guild.ban(
    #             user, 
    #             reason=f"User hardbanned by {ctx.author.name} ({ctx.author.id}) / {reason}"
    #         )
    #         return await ctx.embed(
    #             message=f"Successfully hardbanned {user.mention}",
    #             message_type="approved"
    #         )
        
    @Cog.listener("on_member_join")
    async def hardban_listener(self, member: Member):
        """
        Listener for hardban.
        """
        record = await self.bot.db.fetchval(
            """
            SELECT user_id FROM hardban 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            member.guild.id,
            member.id,
        )
        if record:
            with suppress(Exception):
                await member.ban(reason="User is hardbanned")

    @Cog.listener("on_member_unban")
    async def hardban_ban_listener(
        self, 
        guild: Guild, 
        user: User
    ):
        """
        Listener for hardban unban.
        """
        record = await self.bot.db.fetchval(
            """
            SELECT user_id FROM hardban 
            WHERE guild_id = $1 
            AND user_id = $2
            """,
            guild.id,
            user.id,
        )
        if record:
            with suppress(Exception):
                await guild.ban(
                    user, 
                    reason="User is hardbanned"
                )

async def setup(bot: Greed):
    """
    Setup the AntiNuke cog.
    """
    return await bot.add_cog(AntiNuke(bot))