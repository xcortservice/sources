"""
Sticker classes for Discord
"""

class StickerItem:
    """
    Represents a sticker item in Discord.
    """
    def __init__(self, *, id, name, format_type):
        self.id = id
        self.name = name
        self.format_type = format_type

class GuildSticker:
    """
    Represents a guild sticker in Discord.
    """
    def __init__(self, *, id, name, tags, format_type, description=None, available=True):
        self.id = id
        self.name = name
        self.tags = tags
        self.format_type = format_type
        self.description = description
        self.available = available 