import logging
from typing import Optional

import discord

logger = logging.getLogger("greed/utils/message")


class MessageUtils:
    """
    Utility class for message handling operations
    """
    def __init__(self, bot):
        self.bot = bot

    async def get_message(self, channel: discord.TextChannel, message_id: int) -> Optional[discord.Message]:
        """
        Get a message from cache or fetch it from the API
        
        Args:
            channel: The channel to get the message from
            message_id: The ID of the message to get
            
        Returns:
            The message object or None if not found
        """
        logger.info(f"getting message {message_id} in {channel.name}")
        if message := discord.utils.get(self.bot.cached_messages, id=message_id):
            logger.info(f"getting it returned type {type(message)}")
            return message
        else:
            if m := await channel.fetch_message(message_id):
                logger.info(f"fetched message {m.id} in {channel.name}")
                return m
        return None 