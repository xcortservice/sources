import logging

from greed.framework.discord import Context

logger = logging.getLogger("greed/utils/tracking")


class CommandTracker:
    """
    Utility class for tracking command usage and statistics
    """
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database

    async def on_command_completion(self, ctx: Context) -> None:
        """
        Track command usage in the database and log it
        
        Args:
            ctx: The command context
        """
        await self.db.execute(
            """
            INSERT INTO command_usage (guild_id, user_id, command_name, command_type)
                VALUES ($1,$2,$3,$4)
            ON CONFLICT (guild_id, user_id, command_name) DO UPDATE SET
                uses = command_usage.uses + 1;
            """,
            ctx.guild.id,
            ctx.author.id,
            ctx.command.qualified_name,
            "internal",
        )
        logger.info(f"{ctx.guild.id} > {ctx.author.name}: {ctx.message.content}")
        
        await self.bot.memory_cleanup(force=False) 