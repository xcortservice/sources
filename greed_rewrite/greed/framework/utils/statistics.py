import logging
from typing import List

import discord

logger = logging.getLogger("greed/utils/statistics")


class StatisticsUtils:
    """
    Utility class for gathering bot statistics across clusters
    """
    def __init__(self, bot):
        self.bot = bot
        self.ipc = bot.ipc

    async def guild_count(self) -> int:
        """
        Get the total number of guilds across all clusters
        
        Returns:
            The total number of guilds
        """
        try:
            logger.info("Starting guild_count method")
            if not hasattr(self.bot, "ipc") or self.bot.user.name != "greed":
                logger.info("Using local guild count (no IPC or not greed)")
                return len(self.bot.guilds)
                
            logger.info("Fetching guild count via IPC")
            responses = await self.ipc.broadcast("get_guild_count")
            logger.info(f"Received guild counts from IPC: {responses}")
            
            if responses:
                total = sum(count for count in responses.values() if isinstance(count, (int, float)))
                logger.info(f"Calculated total guild count: {total}")
                return total
                
            logger.info("Falling back to local guild count")
            return len(self.bot.guilds)
        except Exception as e:
            logger.error(f"Error in guild_count: {e}", exc_info=True)
            return len(self.bot.guilds)

    async def user_count(self) -> int:
        """
        Get the total number of users across all clusters
        
        Returns:
            The total number of users
        """
        try:
            logger.info("Starting user_count method")
            if not hasattr(self.bot, "ipc") or self.bot.user.name != "greed":
                logger.info("Using local user count (no IPC or not greed)")
                return sum(guild.member_count for guild in self.bot.guilds)
                
            logger.info("Fetching user count via IPC")
            responses = await self.ipc.broadcast("get_user_count")
            logger.info(f"Received user counts from IPC: {responses}")
            
            if responses:
                total = sum(count for count in responses.values() if isinstance(count, (int, float)))
                logger.info(f"Calculated total user count: {total}")
                return total
                
            logger.info("Falling back to local user count")
            return sum(guild.member_count for guild in self.bot.guilds)
        except Exception as e:
            logger.error(f"Error in user_count: {e}", exc_info=True)
            return sum(guild.member_count for guild in self.bot.guilds)

    async def role_count(self) -> int:
        """
        Get the total number of roles across all clusters
        
        Returns:
            The total number of roles
        """
        try:
            logger.info("Starting role_count method")
            if not hasattr(self.bot, "ipc") or self.bot.user.name != "greed":
                logger.info("Using local role count (no IPC or not greed)")
                return sum(len(guild.roles) for guild in self.bot.guilds)
                
            logger.info("Fetching role count via IPC")
            responses = await self.ipc.broadcast("get_role_count")
            logger.info(f"Received role counts from IPC: {responses}")
            
            if responses:
                total = sum(count for count in responses.values() if isinstance(count, (int, float)))
                logger.info(f"Calculated total role count: {total}")
                return total
                
            logger.info("Falling back to local role count")
            return sum(len(guild.roles) for guild in self.bot.guilds)
        except Exception as e:
            logger.error(f"Error in role_count: {e}", exc_info=True)
            return sum(len(guild.roles) for guild in self.bot.guilds)

    async def channel_count(self) -> int:
        """
        Get the total number of channels across all clusters
        
        Returns:
            The total number of channels
        """
        try:
            logger.info("Starting channel_count method")
            if not hasattr(self.bot, "ipc") or self.bot.user.name != "greed":
                logger.info("Using local channel count (no IPC or not greed)")
                return sum(len(guild.channels) for guild in self.bot.guilds)
                
            logger.info("Fetching channel count via IPC")
            responses = await self.ipc.broadcast("get_channel_count")
            logger.info(f"Received channel counts from IPC: {responses}")
            
            if responses:
                total = sum(count for count in responses.values() if isinstance(count, (int, float)))
                logger.info(f"Calculated total channel count: {total}")
                return total
                
            logger.info("Falling back to local channel count")
            return sum(len(guild.channels) for guild in self.bot.guilds)
        except Exception as e:
            logger.error(f"Error in channel_count: {e}", exc_info=True)
            return sum(len(guild.channels) for guild in self.bot.guilds)

    async def get_channels(self, channel_id: int) -> List[discord.TextChannel]:
        """
        Get channels from all clusters via IPC and return valid TextChannel objects
        
        Args:
            channel_id: The ID of the channel to get
            
        Returns:
            A list of TextChannel objects
        """
        if not isinstance(channel_id, int):
            raise TypeError(f"channel_id must be int, not {type(channel_id)}")

        channels = []
        try:
            responses = await self.ipc.broadcast("get_channel", {"channel_id": channel_id})

            logger.debug(f"Got channel responses: {responses}")

            if not responses:
                logger.debug(f"No responses for channel {channel_id}")
                return channels

            for cluster_id, channel_data in responses.items():
                try:
                    if not channel_data:
                        logger.debug(f"Empty channel data in response")
                        continue

                    if isinstance(channel_data, dict):
                        guild_id = channel_data.get("guild_id")
                        guild = self.bot.get_guild(guild_id)

                        if not guild:
                            logger.debug(f"Could not find guild {guild_id}")
                            continue

                        channel = guild.get_channel(channel_data.get("id"))
                        if isinstance(channel, discord.TextChannel):
                            channels.append(channel)
                        else:
                            logger.debug(
                                f"Channel {channel_data.get('id')} is not TextChannel: {type(channel)}"
                            )

                    elif isinstance(channel_data, discord.TextChannel):
                        channels.append(channel_data)
                    else:
                        logger.debug(
                            f"Unexpected channel data type: {type(channel_data)}"
                        )

                except Exception as e:
                    logger.error(f"Error processing channel data {channel_data}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to get channels from IPC: {e}")
            raise  

        return channels 