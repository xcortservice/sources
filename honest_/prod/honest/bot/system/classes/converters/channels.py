import discord
from data.variables import DISCORD_CHANNEL_MENTION, DISCORD_ID
from discord.ext import commands
from system.patch.context import Context


class TextChannelConverter(commands.TextChannelConverter):
    async def convert(self, ctx: Context, argument: str):
        argument = argument.replace(" ", "-")
        try:
            return await super().convert_(ctx, argument)
        except Exception:
            pass
        if match := DISCORD_ID.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        if match := DISCORD_CHANNEL_MENTION.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        else:
            channel = discord.utils.find(
                lambda m: m.name.lower() == argument.lower(),
                ctx.guild.text_channels,
            ) or discord.utils.find(
                lambda m: argument.lower() in m.name.lower(),
                ctx.guild.text_channels,
            )

            if channel:
                return channel
            else:
                raise discord.ext.commands.errors.ChannelNotFound(
                    f"channel `{channel}` not found"
                )


class GuildChannelConverter(commands.GuildChannelConverter):
    async def convert(self, ctx: Context, argument: str):
        try:
            if c := await super().convert_(ctx, argument):
                return c
        except Exception:
            pass
        if match := DISCORD_ID.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        if match := DISCORD_CHANNEL_MENTION.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        else:
            channel = (
                discord.utils.find(
                    lambda m: m.name.lower() == argument.lower(),
                    ctx.guild.channels,
                )
                or discord.utils.find(
                    lambda m: argument.lower() in m.name.lower(),
                    ctx.guild.channels,
                )
                or discord.utils.find(
                    lambda m: str(m.id) == argument, ctx.guild.channels
                )
            )
            if channel:
                return channel
            else:
                raise discord.ext.commands.errors.ChannelNotFound(f"`{argument}`")


class CategoryChannelConverter(commands.TextChannelConverter):
    async def convert(self, ctx: Context, argument: str):
        try:
            return await super().convert_(ctx, argument)
        except Exception:
            pass
        if match := DISCORD_ID.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        if match := DISCORD_CHANNEL_MENTION.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        else:
            channel = (
                discord.utils.find(
                    lambda m: m.name.lower() == argument.lower(),
                    ctx.guild.categories,
                )
                or discord.utils.find(
                    lambda m: argument.lower() in m.name.lower(),
                    ctx.guild.categories,
                )
                or discord.utils.find(
                    lambda m: str(m.id) == argument, ctx.guild.categories
                )
            )
            if channel:
                return channel
            else:
                raise discord.ext.commands.errors.ChannelNotFound(
                    f"channel `{channel}` not found"
                )


class ThreadChannelConverter(commands.ThreadConverter):
    async def convert(self, ctx: Context, argument: str):
        if match := DISCORD_ID.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        if match := DISCORD_CHANNEL_MENTION.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        else:
            channel = (
                discord.utils.find(
                    lambda m: m.name.lower() == argument.lower(),
                    ctx.guild.threads,
                )
                or discord.utils.find(
                    lambda m: argument.lower() in m.name.lower(),
                    ctx.guild.threads,
                )
                or discord.utils.find(
                    lambda m: str(m.id) == argument, ctx.guild.threads
                )
            )
            if channel:
                return channel
            else:
                raise discord.ext.commands.errors.ChannelNotFound(f"`{argument}`")


class VoiceChannelConverter(commands.TextChannelConverter):
    async def convert(self, ctx: Context, argument: str):
        try:
            return await super().convert_(ctx, argument)
        except Exception:
            pass
        if match := DISCORD_ID.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        if match := DISCORD_CHANNEL_MENTION.match(argument):
            channel = ctx.guild.get_channel(int(match.group(1)))
        else:
            channel = discord.utils.find(
                lambda m: m.name.lower() == argument.lower(),
                ctx.guild.voice_channels,
            ) or discord.utils.find(
                lambda m: argument.lower() in m.name.lower(),
                ctx.guild.voice_channels,
            )
            if channel:
                return channel
            else:
                raise discord.ext.commands.errors.ChannelNotFound(
                    f"channel `{channel}` not found"
                )
