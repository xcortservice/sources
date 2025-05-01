from discord import Client, Message

from .YouTube import download, extract
from .YouTube import repost as repost_youtube


def repost(bot: Client, message: Message):
    repost_youtube(bot, message)
