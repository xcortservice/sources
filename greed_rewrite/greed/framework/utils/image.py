import logging
from typing import Optional

from greed.framework.discord import Context

logger = logging.getLogger("greed/utils/image")


class ImageUtils:
    """
    Utility class for handling image-related operations
    """
    def __init__(self, bot):
        self.bot = bot

    async def get_image(self, ctx: Context, *args) -> Optional[str]:
        """
        Extract an image URL from a message, either from attachments, referenced message, or URL arguments
        
        Args:
            ctx: The command context
            *args: Additional arguments that might contain URLs
            
        Returns:
            The URL of the image or None if no image was found
        """
        if len(ctx.message.attachments) > 0:
            return ctx.message.attachments[0].url
        elif ctx.message.reference:
            if msg := await self.bot.get_message(
                ctx.channel, ctx.message.reference.message_id
            ):
                if len(msg.attachments) > 0:
                    return msg.attachments[0].url
                else:
                    logger.info(
                        f"there are no attachments for {msg} : {msg.attachments}"
                    )
            else:
                logger.info("could not get message")
        else:
            for i in args:
                if i.startswith("http"):
                    return i
        return None 