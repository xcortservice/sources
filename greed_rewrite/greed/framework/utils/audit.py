import logging

import discord

logger = logging.getLogger("greed/utils/audit")


class AuditLogUtils:
    """
    Utility class for handling audit log events
    """
    def __init__(self, bot):
        self.bot = bot

    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry) -> None:
        """
        Handle audit log entry creation events
        
        Args:
            entry: The audit log entry that was created
        """
        try:
            if entry.action == discord.AuditLogAction.member_ban:
                self.bot.dispatch("member_ban", entry)
            elif entry.action == discord.AuditLogAction.member_unban:
                self.bot.dispatch("member_unban", entry)
            elif entry.action == discord.AuditLogAction.member_kick:
                self.bot.dispatch("member_kick", entry)
            elif entry.action == discord.AuditLogAction.member_update:
                self.bot.dispatch("member_update", entry)
            elif entry.action == discord.AuditLogAction.role_create:
                self.bot.dispatch("role_create", entry)
            elif entry.action == discord.AuditLogAction.role_delete:
                self.bot.dispatch("role_delete", entry)
            elif entry.action == discord.AuditLogAction.role_update:
                self.bot.dispatch("role_update", entry)
            elif entry.action == discord.AuditLogAction.channel_create:
                self.bot.dispatch("channel_create", entry)
            elif entry.action == discord.AuditLogAction.channel_delete:
                self.bot.dispatch("channel_delete", entry)
            elif entry.action == discord.AuditLogAction.channel_update:
                self.bot.dispatch("channel_update", entry)
            elif entry.action == discord.AuditLogAction.guild_update:
                self.bot.dispatch("guild_update", entry)
            elif entry.action == discord.AuditLogAction.invite_create:
                self.bot.dispatch("invite_create", entry)
            elif entry.action == discord.AuditLogAction.invite_delete:
                self.bot.dispatch("invite_delete", entry)
            elif entry.action == discord.AuditLogAction.webhook_create:
                self.bot.dispatch("webhook_create", entry)
            elif entry.action == discord.AuditLogAction.webhook_delete:
                self.bot.dispatch("webhook_delete", entry)
            elif entry.action == discord.AuditLogAction.webhook_update:
                self.bot.dispatch("webhook_update", entry)
            elif entry.action == discord.AuditLogAction.emoji_create:
                self.bot.dispatch("emoji_create", entry)
            elif entry.action == discord.AuditLogAction.emoji_delete:
                self.bot.dispatch("emoji_delete", entry)
            elif entry.action == discord.AuditLogAction.emoji_update:
                self.bot.dispatch("emoji_update", entry)
            elif entry.action == discord.AuditLogAction.message_delete:
                self.bot.dispatch("message_delete", entry)
            elif entry.action == discord.AuditLogAction.message_bulk_delete:
                self.bot.dispatch("message_bulk_delete", entry)
            elif entry.action == discord.AuditLogAction.message_pin:
                self.bot.dispatch("message_pin", entry)
            elif entry.action == discord.AuditLogAction.message_unpin:
                self.bot.dispatch("message_unpin", entry)
            elif entry.action == discord.AuditLogAction.integration_create:
                self.bot.dispatch("integration_create", entry)
            elif entry.action == discord.AuditLogAction.integration_delete:
                self.bot.dispatch("integration_delete", entry)
            elif entry.action == discord.AuditLogAction.integration_update:
                self.bot.dispatch("integration_update", entry)
            elif entry.action == discord.AuditLogAction.stage_instance_create:
                self.bot.dispatch("stage_instance_create", entry)
            elif entry.action == discord.AuditLogAction.stage_instance_delete:
                self.bot.dispatch("stage_instance_delete", entry)
            elif entry.action == discord.AuditLogAction.stage_instance_update:
                self.bot.dispatch("stage_instance_update", entry)
            elif entry.action == discord.AuditLogAction.sticker_create:
                self.bot.dispatch("sticker_create", entry)
            elif entry.action == discord.AuditLogAction.sticker_delete:
                self.bot.dispatch("sticker_delete", entry)
            elif entry.action == discord.AuditLogAction.sticker_update:
                self.bot.dispatch("sticker_update", entry)
            elif entry.action == discord.AuditLogAction.thread_create:
                self.bot.dispatch("thread_create", entry)
            elif entry.action == discord.AuditLogAction.thread_delete:
                self.bot.dispatch("thread_delete", entry)
            elif entry.action == discord.AuditLogAction.thread_update:
                self.bot.dispatch("thread_update", entry)
            else:
                logger.debug(f"Unhandled audit log action: {entry.action}")
        except Exception as e:
            logger.error(f"Error handling audit log entry: {e}", exc_info=True) 