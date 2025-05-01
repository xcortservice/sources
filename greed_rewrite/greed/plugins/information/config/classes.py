import re

from discord import Interaction, app_commands
from discord.ext.commands import (
    Command,
    CommandError, 
    Bot,
    Cog
)
from discord.app_commands import Choice

from io import BytesIO
from munch import DefaultMunch
from pydantic import BaseModel
from typing import Union, Optional

from greed.framework import Context
from greed.framework.tools.converters.basic import DISCORD_FILE_PATTERN


class Image:
    def __init__(self, fp: bytes, url: str, filename: str):
        self.fp = fp
        self.url = url
        self.filename = filename

    @property
    def buffer(self) -> BytesIO:
        buffer = BytesIO(self.fp)
        buffer.name = self.filename
        return buffer

    @classmethod
    async def fallback(cls, ctx: Context) -> "Image":
        if ref := ctx.message.reference:
            message = await ctx.channel.fetch_message(ref.message_id)
        else:
            message = ctx.message
        
        if not message.attachments:
            raise CommandError("You must provide an image!")
        
        attachment = message.attachments[0]
        
        if not attachment.content_type:
            raise CommandError(f"The [attachment]({attachment.url}) provided is invalid!")
        
        elif not attachment.content_type.startswith("image"):
            raise CommandError(f"The [attachment]({attachment.url}) provided must be an image file.")
        
        buffer = await attachment.read()
        return cls(fp=buffer, url=attachment.url, filename=attachment.filename)

    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> "Image":
        
        if not (match := re.match(DISCORD_FILE_PATTERN, argument)):
            raise CommandError("The URL provided doesn't match the **Discord** regex!")
        
        response = await ctx.bot.session.get(match.group())
        if not response.content_type.startswith("image"):
            raise CommandError(f"The [URL]({argument}) provided must be an image file.")
        
        buffer = await response.read()
        return cls(fp=buffer, url=match.group(), filename=match.group("filename") or match.group("hash"))

class UrbanDefinition(BaseModel):
    definition: str
    permalink: str
    thumbs_up: int
    author: str
    word: str
    defid: int
    current_vote: str
    written_on: str
    example: str
    thumbs_down: int

class Object:
    def __init__(self, data: dict):
        self.data = data

    def from_data(self):
        return DefaultMunch(object(), self.data)

class Tempature(BaseModel):
    celsius: Union[int, float]
    fahrenheit: Union[int, float]

class WeatherResponse(BaseModel):
    cloud_pct: Union[int, float]
    temp: Tempature
    feels_like: Tempature
    humidity: Union[int, float]
    min_temp: Tempature
    max_temp: Tempature
    wind_speed: Union[int, float]
    wind_degrees: Union[int, float]
    sunrise: Union[int, float]
    sunset: Union[int, float]

class CategoryTransformer(app_commands.Transformer):
    async def autocomplete(self, interaction: Interaction, value: str) -> list[Choice[str]]:
        bot: Bot = interaction.client
        return [Choice(name=cog.qualified_name, value=name) for name, cog in bot.cogs.items() if cog.qualified_name.casefold().startswith(value.casefold())][:25]

    async def transform(self, interaction: Interaction, value: str) -> Cog:
        cog: Optional[Cog] = interaction.client.get_cog(value)
        if cog is None:
            raise ValueError(f"Category {value} not found.")
        else:
            return cog

class CommandTransformer(app_commands.Transformer):
    async def autocomplete(self, interaction: Interaction, value: str) -> list[Choice[str]]:
        bot: Bot = interaction.client
        return [Choice(name=command.qualified_name, value=command.qualified_name) for command in bot.walk_commands() if command.qualified_name.casefold().startswith(value.casefold())][:25]

    async def transform(self, interaction: Interaction, value: str) -> Command:
        command: Optional[Command] = interaction.client.get_command(value)
        if command is None:
            raise ValueError(f"Command {value} not found.")
        else:
            return command