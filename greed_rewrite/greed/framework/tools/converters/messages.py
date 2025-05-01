# implement message converters

from discord.ext.commands import (
    MessageConverter as DiscordMessageConverter,
    Context,
    Converter,
)
import discord


class MessageConverter(Converter):
    async def convert(
        self, ctx: Context, argument: str
    ) -> discord.Message:
        """
        Converts the argument to a discord.Message object using the built-in converter.
        Handles message IDs, jump links, and replied messages.
        Lets standard discord.py exceptions propagate.
        """
        if ctx.message.reference and not argument:
            return await ctx.fetch_message(
                ctx.message.reference.message_id
            )

        base_converter = DiscordMessageConverter()
        message = await base_converter.convert(
            ctx, argument
        )

        return message
