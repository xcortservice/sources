import contextlib
from typing import Any, Union

from data.config import CONFIG
from discord import AllowedMentions, Embed, HTTPException, Message
from discord import TextChannel as DefaultTextChannel
from discord import Thread as DefaultThread
from discord.abc import Messageable as DefaultMessageable
from discord.ext.commands import UserInputError

from .context import ConfirmView


async def confirm(
    self: Union[DefaultTextChannel, DefaultThread], message: str, **kwargs: Any
):
    view = ConfirmView(self)
    message = await self.fail(message, view=view, **kwargs)

    await view.wait()
    with contextlib.suppress(HTTPException):
        await message.delete()

    if view.value is False:
        raise UserInputError("Prompt was denied.")
    return view.value


async def success(
    self: Union[DefaultTextChannel, DefaultThread], text: str, *args: Any, **kwargs: Any
) -> Message:
    emoji = CONFIG["emojis"]["success"]
    color = CONFIG["colors"]["success"]
    author = kwargs.pop("author", None)
    if author is None:
        a = ""
    else:
        a = author.mention
    embed = Embed(color=color, description=f"{emoji} {a}: {text}")
    if footer := kwargs.pop("footer", None):
        if isinstance(footer, tuple):
            embed.set_footer(text=footer[0], icon_url=footer[1])
        else:
            embed.set_footer(text=footer)
    if author := kwargs.pop("author", None):
        if isinstance(author, tuple):
            embed.set_author(name=author[0], icon_url=author[1])
        else:
            embed.set_author(name=author)
    if delete_after := kwargs.get("delete_after"):
        delete_after = delete_after
    else:
        delete_after = None
    if kwargs.get("return_embed", False) is True:
        return embed
    return await self.send(
        embed=embed, delete_after=delete_after, view=kwargs.pop("view", None), **kwargs
    )


async def dump_history(self: Union[DefaultTextChannel, DefaultThread]):
    return [i.to_dict() async for i in self.history(limit=None)]


async def fail(
    self: Union[DefaultTextChannel, DefaultThread], text: str, *args: Any, **kwargs: Any
) -> Message:
    emoji = CONFIG["emojis"]["fail"]
    color = CONFIG["colors"]["fail"]
    author = kwargs.pop("author", None)
    if author is None:
        a = ""
    else:
        a = author.mention
    embed = Embed(color=color, description=f"{emoji} {a}: {text}")
    if footer := kwargs.pop("footer", None):
        if isinstance(footer, tuple):
            embed.set_footer(text=footer[0], icon_url=footer[1])
        else:
            embed.set_footer(text=footer)
    if author := kwargs.pop("author", None):
        if isinstance(author, tuple):
            embed.set_author(name=author[0], icon_url=author[1])
        else:
            embed.set_author(name=author)
    if delete_after := kwargs.get("delete_after"):
        delete_after = delete_after
    else:
        delete_after = None
    if kwargs.get("return_embed", False) is True:
        return embed
    return await self.send(
        embed=embed, delete_after=delete_after, view=kwargs.pop("view", None), **kwargs
    )


async def warning(
    self: Union[DefaultTextChannel, DefaultThread], text: str, *args: Any, **kwargs: Any
) -> Message:
    emoji = CONFIG["emojis"]["warning"]
    color = CONFIG["colors"]["warning"]
    author = kwargs.pop("author", None)
    if author is None:
        a = ""
    else:
        a = author.mention
    embed = Embed(color=color, description=f"{emoji} {a}: {text}")
    if footer := kwargs.pop("footer", None):
        if isinstance(footer, tuple):
            embed.set_footer(text=footer[0], icon_url=footer[1])
        else:
            embed.set_footer(text=footer)
    if author := kwargs.pop("author", None):
        if isinstance(author, tuple):
            embed.set_author(name=author[0], icon_url=author[1])
        else:
            embed.set_author(name=author)
    if delete_after := kwargs.get("delete_after"):
        delete_after = delete_after
    else:
        delete_after = None
    if kwargs.get("return_embed", False) is True:
        return embed
    return await self.send(
        embed=embed, delete_after=delete_after, view=kwargs.pop("view", None), **kwargs
    )


async def normal(
    self: Union[DefaultTextChannel, DefaultThread], text: str, *args: Any, **kwargs: Any
) -> Message:
    color = CONFIG["colors"].get("bleed", 0x2B2D31)
    author = kwargs.pop("author", None)
    if author is None:
        a = ""
    else:
        a = author.mention
    embed = Embed(color=color, description=f"{a}: {text}")
    if footer := kwargs.pop("footer", None):
        if isinstance(footer, tuple):
            embed.set_footer(text=footer[0], icon_url=footer[1])
        else:
            embed.set_footer(text=footer)
    if author := kwargs.pop("author", None):
        if isinstance(author, tuple):
            embed.set_author(name=author[0], icon_url=author[1])
        else:
            embed.set_author(name=author)
    if delete_after := kwargs.get("delete_after"):
        delete_after = delete_after
    else:
        delete_after = None
    if kwargs.get("return_embed", False) is True:
        return embed
    return await self.send(
        embed=embed, delete_after=delete_after, view=kwargs.pop("view", None), **kwargs
    )


async def reply(
    self: Union[DefaultTextChannel, DefaultThread], *args: Any, **kwargs: Any
) -> Message:
    if kwargs.pop("mention", True) is False:
        kwargs["allowed_mentions"] = AllowedMentions(replied_user=False)
    return await super().reply(*args, **kwargs)
