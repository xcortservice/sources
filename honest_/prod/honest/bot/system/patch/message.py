from typing import Any, Dict, List, Optional

from discord import Attachment, Message


class DiscordAttachment(Attachment):
    def to_dict(self: Attachment) -> Optional[Dict[str, Any]]:
        return {
            "url": self.url,
            "proxy_url": self.url,
            "size": self.size,
            "height": self.height,
            "width": self.width,
            "type": self.content_type,
            "filename": self.filename,
        }


class DiscordMessage(Message):
    def to_dict(self: Message) -> Optional[Dict[str, Any]]:
        return {
            "id": self.id,
            "channel_id": self.channel.id,
            "guild_id": self.guild.id,
            "author": {
                "id": self.author.id,
                "username": self.author.name,
                "discriminator": self.author.discriminator,
                "bot": self.author.bot,
                "color": int(self.author.color.value),
                "avatar": str(self.author.display_avatar.url),
            },
            "content": self.content,
            "timestamp": str(self.created_at),
            "edited_timestamp": str(self.edited_at) if self.edited_at else None,
            "raw_content": self.clean_content,
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "embeds": [i.to_dict() for i in self.embeds],
        }


Message.to_dict = DiscordMessage.to_dict
Attachment.to_dict = DiscordAttachment.to_dict
