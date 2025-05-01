import logging
from typing import Union

import discord

logger = logging.getLogger("greed/utils/permissions")


class PermissionUtils:
    """
    Utility class for permission and hierarchy checks
    """
    def __init__(self, bot):
        self.bot = bot

    def is_touchable(self, obj: Union[discord.Role, discord.Member]) -> bool:
        """
        Check if the bot can modify the given role or member
        
        Args:
            obj: The role or member to check
            
        Returns:
            True if the bot can modify the object, False otherwise
        """
        def touchable(role: discord.Role) -> bool:
            guild = role.guild
            list(guild.roles)  # Ensure roles are cached
            if role >= guild.me.top_role:
                return False
            return True

        if isinstance(obj, discord.Member):
            return touchable(obj.top_role)
        else:
            return touchable(obj)

    def check_bot_hierarchy(self, guild: discord.Guild) -> bool:
        """
        Check if the bot's role is high enough in the guild hierarchy
        
        Args:
            guild: The guild to check
            
        Returns:
            True if the bot's role is in the top 5 roles, False otherwise
        """
        roles = sorted(guild.roles, key=lambda x: x.position, reverse=True)
        roles = roles[:5]
        if guild.me.top_role not in roles:
            del roles
            return False
        return True 