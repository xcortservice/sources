from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional, Union, List
import aiohttp
import logging
from asyncio import sleep, gather
from contextlib import suppress
from urllib.parse import urlparse
from io import BytesIO
import asyncio
import discord
from discord.ext import commands
from discord.ext.commands import (
    Context,
    Converter,
    bot_has_permissions,
    has_permissions,
    Group,
    CommandError
)
from discord import HTTPException
from discord.ui import View, button
from discord import Interaction, Message, Member
from discord.enums import ButtonStyle

from greed.framework.tools.offload import offloaded

if TYPE_CHECKING:
    from greed.framework import Greed

logger = logging.getLogger("greed/plugins/config/emojis")


def link(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


class Attachment(commands.Converter):
    async def convert(
        self, ctx: "Context", argument: str, fail: bool = True
    ) -> Optional[str]:
        if argument and link(argument):
            return argument
        if fail:
            with suppress(Exception):
                await ctx.send_help(ctx.command.qualified_name)
            assert False

    @staticmethod
    async def search(ctx: "Context", fail: bool = False) -> Optional[str]:
        if ref := ctx.message.reference:
            logger.info("attachment search has a reference")
            if channel := ctx.guild.get_channel(ref.channel_id):
                if message := await channel.fetch_message(ref.message_id):
                    if message.attachments:
                        return message.attachments[0].url
                    logger.info("attachment.search failed: message has no attachments")
        if ctx.message.attachments:
            logger.info("message attachments exist")
            return ctx.message.attachments[0].url
        if fail:
            with suppress(Exception):
                await ctx.send_help(ctx.command.qualified_name)
            assert False
        return None


class EmojiEntry:
    def __init__(self, name: str, url: str, id: int):
        self.name = name
        self.url = url
        self.id = id

    def __str__(self) -> str:
        return f"<:{self.name}:{self.id}>"


class EmojiConfirmation(View):
    def __init__(
        self: "EmojiConfirmation",
        message: Message,
        emojis: EmojiEntry,
        invoker: Member = None,
    ) -> None:
        super().__init__(timeout=60.0)
        self.index = 0
        self.emojis = emojis
        self.value = False
        self.message = message
        self.invoker = invoker

    @button(style=ButtonStyle.green, emoji="✅")
    async def approve(self: "EmojiConfirmation", interaction: Interaction, _: None):
        if interaction.user.id != self.invoker.id:
            return await interaction.response.send_message(
                "This isn't your emoji to steal!", ephemeral=True
            )
        self.value = True
        await self.confirmation(interaction, True)

    @button(style=ButtonStyle.red, emoji="❌")
    async def decline(self: "EmojiConfirmation", interaction: Interaction, _: None):
        if interaction.user.id != self.invoker.id:
            return await interaction.response.send_message(
                "This isn't your emoji to steal!", ephemeral=True
            )
        self.value = False
        await self.confirmation(interaction, False)

    async def confirmation(
        self: "EmojiConfirmation", interaction: Interaction, value: bool
    ) -> None:
        await interaction.response.defer()

        with suppress(HTTPException):
            if self.value is True:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.emojis.url) as resp:
                        if resp.status != 200:
                            return await self.message.edit(
                                embed=discord.Embed(
                                    description="Failed to download emoji image",
                                    color=0x2B2D31,
                                ),
                                view=None,
                            )
                        image = await resp.read()
                try:
                    emoji = await interaction.guild.create_custom_emoji(
                        name=self.emojis.name,
                        image=image,
                        reason=f"Emoji steal by {interaction.user}",
                    )
                    await self.message.edit(
                        embed=discord.Embed(
                            description=f"{interaction.user.mention}: **added** {emoji}",
                            color=0x2B2D31,
                        ),
                        view=None,
                    )
                except discord.HTTPException as e:
                    if "emoji limit" in str(e).lower():
                        await self.message.edit(
                            embed=discord.Embed(
                                description="Server has reached emoji limit",
                                color=0x2B2D31,
                            ),
                            view=None,
                        )
                    else:
                        await self.message.edit(
                            embed=discord.Embed(
                                description="Failed to create emoji",
                                color=0x2B2D31,
                            ),
                            view=None,
                        )
            else:
                await self.message.edit(
                    embed=discord.Embed(
                        description="**Cancelled** emoji steal",
                        color=0x2B2D31,
                    ),
                    view=None,
                )

        self.stop()

    async def on_timeout(self) -> None:
        with suppress(HTTPException):
            await self.message.edit(
                embed=discord.Embed(
                    description="**Timed out** waiting for confirmation",
                    color=0x2B2D31,
                ),
                view=None,
            )


class Emoji(Converter[discord.Emoji]):
    async def convert(self, ctx: Context, argument: str) -> discord.Emoji:
        try:
            return await commands.EmojiConverter().convert(ctx, argument)
        except commands.BadArgument:
            raise commands.BadArgument(f"Emoji {argument} not found.")


class EmojiList(Converter[List[discord.Emoji]]):
    async def convert(
        self,
        ctx: Context,
        argument: str,
        reference: bool = False,
        multiple: bool = False,
    ) -> List[discord.Emoji]:
        if reference and ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            argument = message.content

        emojis = []
        for match in re.finditer(r"<a?:(\w+):(\d+)>", argument):
            try:
                emoji = await commands.EmojiConverter().convert(ctx, match.group(0))
                emojis.append(emoji)
                if not multiple:
                    break
            except commands.BadArgument:
                continue

        if not emojis:
            raise commands.BadArgument("No valid emojis found")
        return emojis


class Sticker(Converter[discord.GuildSticker]):
    async def convert(self, ctx: Context, argument: str) -> discord.GuildSticker:
        try:
            return await commands.GuildStickerConverter().convert(ctx, argument)
        except commands.BadArgument:
            raise commands.BadArgument(f"Sticker {argument} not found.")


class Stickers(Converter[List[discord.GuildSticker]]):
    async def convert(
        self,
        ctx: Context,
        argument: str,
        reference: bool = False,
        multiple: bool = False,
    ) -> List[discord.GuildSticker]:
        if reference and ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            argument = message.content

        stickers = []
        for match in re.finditer(r"<a?:(\w+):(\d+)>", argument):
            try:
                sticker = await commands.GuildStickerConverter().convert(
                    ctx, match.group(0)
                )
                stickers.append(sticker)
                if not multiple:
                    break
            except commands.BadArgument:
                continue

        if not stickers:
            raise commands.BadArgument("No valid stickers found")
        return stickers


class Emojis(commands.Cog):
    def __init__(self, bot: "Greed"):
        self.bot = bot

    @commands.group(
        name="emoji",
        usage="<sub command>",
        example="removeduplicates",
        invoke_without_command=True,
    )
    @bot_has_permissions(manage_emojis=True)
    @has_permissions(manage_emojis=True)
    async def emoji(self: "Emojis", ctx: Context):
        """
        Manage the server emojis
        """
        return await ctx.send_help(ctx.command.qualified_name)

    @emoji.command(
        name="steal", brief="steal the most recently used emoji", example=",emoji steal"
    )
    @bot_has_permissions(manage_emojis=True)
    @has_permissions(manage_emojis=True)
    async def emoji_steal(self, ctx: Context):
        try:
            emoji = None
            i = 0
            if ctx.message.reference:
                emoji = await Emojis().convert(ctx, "", True)
                emoji = emoji[0]
            else:

                async for message in ctx.channel.history(limit=200):
                    i += 1
                    if await Emojis().convert(ctx, message.content):  
                        try:
                            emoj = await self.get_emojis(message.content)
                            try:
                                if get_emoji := self.bot.get_emoji(int(emoj.id)):
                                    if get_emoji.guild.id != ctx.guild.id:
                                        emoji = emoj
                                        break
                                    else:
                                        continue
                                else:
                                    emoji = emoj
                                    break
                            except Exception:  
                                emoji = emoj
                        except Exception:  
                            emoji = await self.get_emojis(message.content)
                            if emoji:
                                break
            if emoji is None:
                return await ctx.embed(
                    f"no **emojis** found in the last {i} messages", "denied"
                )
            embed = discord.Embed().add_field(
                name="Emoji ID", value=emoji.id, inline=True
            )
            if get_emoji := self.bot.get_emoji(int(emoji.id)):
                embed.add_field(name="Guild", value=get_emoji.guild.name, inline=True)
            embed.add_field(
                name="Image URL",
                value=f"[**Click here to open the image**]({emoji.url})",
                inline=False,
            )
            embed.set_image(url=emoji.url)
            embed.set_author(
                name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
            )
            embed.title = emoji.name
            message = await ctx.send(embed=embed)
            view = EmojiConfirmation(message, emoji, ctx.author)
            await message.edit(view=view)
            await view.wait()
        except Exception as e:
            if ctx.author.name == "aiohttp":
                raise e
            else:
                return await ctx.embed("No stealable emojis detected", "denied")

    @emoji.command(
        name="add",
        aliases=("create",),
        example=",emoji add [emojis]",
        brief="Add multiple emojis to the server",
    )
    @bot_has_permissions(manage_emojis=True)
    @has_permissions(manage_emojis=True)
    async def emoji_addmultiple(
        self: "Emojis",
        ctx: Context,
        *,
        emojis: Optional[EmojiList] = None,
    ):
        """
        Create multiple emojis
        """
        if ctx.message.reference and not emojis:
            emojis = await EmojiList().convert(ctx, "", True, True)
        else:
            if not emojis:
                return await ctx.embed("Please provide **Emojis**", "denied")
        if len(ctx.guild.emojis) >= ctx.guild.emoji_limit:
            return await ctx.embed("**Server exceeds** the **emoji limit**.", "denied")
        if not emojis:
            return await ctx.embed("No **Emojis** were found", "denied")

        created_emojis = []  
        logger.info(emojis)
        msg = None
        remaining = ctx.guild.emoji_limit - len(ctx.guild.emojis)
        e = emojis[:remaining] if isinstance(emojis, list) else [emojis]
        logger.info(f"{e} {remaining}")
        for emoji in e:
            await sleep(0.001)
            if (
                await self.bot.glory_cache.ratelimited(
                    f"emojis:{ctx.guild.id}", 49, 60 * 60
                )
                != 0
            ):  
                raise CommandError("Emoji adding is ratelimited for this guild")
            new_emoji = await ctx.guild.create_custom_emoji(
                name=emoji.name,
                image=await emoji.read(),
                reason=f"{self.bot.user.name.title()} Utilities[{ctx.author}]",
            )
            created_emojis.append(new_emoji)

        if not created_emojis:
            return await ctx.embed("**No emojis** could be added", "denied")

        created_emoji_str = " ".join(str(emoji) for emoji in created_emojis)

        if len(created_emojis) != len(e):
            return await ctx.embed(
                f"**Could only create** {created_emoji_str}", "approved"
            )
        if msg is not None:
            return await msg.edit(
                embed=discord.Embed(
                     description=f"**Created** {created_emoji_str}"
                )
            )
        return await ctx.embed(f"**Created** {created_emoji_str}", "approved")

    @emoji.command(
        name="image",
        aliases=("fromfile",),
        example=",emoji add :sad_bear:",
        brief="Add an emoji to the guild",
    )
    @bot_has_permissions(manage_emojis=True)
    @has_permissions(manage_emojis=True)
    async def emoji_add(
        self: "Emojis",
        ctx: Context,
        *,
        name: Optional[Union[discord.PartialEmoji, str, discord.Emoji]] = "lol",
    ):
        """
        Create a new emoji
        """
        logger.info(f"got type {type(name)}")
        if sum(ctx.guild.emojis) >= ctx.guild.emoji_limit:
            return await ctx.embed("**Server exceeds** the **emoji limit**", "denied")

        if not isinstance(name, discord.PartialEmoji) and not isinstance(
            name, discord.PartialEmoji
        ):
            if len(name) < 2 or len(name) > 30:
                return await ctx.embed(
                    "Please provide a **valid** name between 2 and 30 characters.",
                    "denied",
                )
            if not (image := await Attachment.search(ctx)):
                return await ctx.embed(
                    "There are **no recently sent images**", "denied"
                )
        else:
            image = await name.read()
            name = name.name
        if isinstance(image, str):
            image = await Attachment.search(ctx)
            async with aiohttp.ClientSession() as session:
                async with session.get(image) as response:
                    content_type = response.headers.get("Content-Type")
                    if content_type != "image/gif":
                        count = ctx.static_emoji_count
                    else:
                        count = ctx.animated_emoji_count
                    image = await response.read()
            name = name
        try:
            if (
                await self.bot.glory_cache.ratelimited(
                    f"emojis:{ctx.guild.id}", 49, 60 * 60
                )
                != 0
            ):  
                raise CommandError("Emoji adding is ratelimited for this guild")
            emoji = await ctx.guild.create_custom_emoji(
                name=name,
                image=image,
                reason=f"{self.bot.user.name.title()} Utilities[{str(ctx.author)}]",
            )

        except HTTPException as error:
            if "(error code: 30008)" in str(error):
                return await ctx.embed(
                    "**Server** doesn't have enough **emoji slots**", "denied"
                )
            
            if "(error code: 50045)" in str(error):
                return await ctx.embed("The **Image** you sent was to large", "denied")
            if ctx.author.name == "aiohttp":
                raise error
            return await ctx.embed("Please provide a **valid** image.", "denied")

        return await ctx.embed(
            f"**Created** the emoji [**{emoji.name}**]({emoji.url})", "approved"
        )

    @emoji.command(
        name="remove",
        aliases=("delete",),
        example=",emoji remove [emoji]",
        brief="Remove an emoji from the server",
    )
    @bot_has_permissions(manage_emojis=True)
    @has_permissions(manage_emojis=True)
    async def emoji_remove(
        self: "Emojis", ctx: Context, *, emoji: Union[discord.Emoji, str]
    ):
        """Remove an emoji from the server"""

        if isinstance(emoji, str) or (
            isinstance(emoji, discord.Emoji) and emoji.guild_id != ctx.guild.id
        ):
            return await ctx.embed(
                "That emoji cannot be deleted from this server", "denied"
            )

        await emoji.delete(
            reason=f"{self.bot.user.name.title()} Utilities [{ctx.author}]"
        )
        return await ctx.embed("**Deleted** that emoji", "approved")

    @emoji.command(
        name="rename",
        aliases=("name",),
        example=",emoji rename :sad: megasad",
        brief="Rename an emoji",
    )
    @bot_has_permissions(manage_emojis=True)
    @has_permissions(manage_emojis=True)
    async def emoji_rename(self: "Emojis", ctx: Context, emoji: Emoji, *, name: str):

        if len(name) < 2 or len(name) > 30:
            return await ctx.embed(
                "Name must be between **2** and **30 characters**", "denied"
            )

        await emoji.edit(
            name=name, reason=f"{self.bot.user.name.title()} Utilities[{ctx.author}]"
        )

        return await ctx.embed(f"Renamed** that emoji to: **{name}**", "approved")

    @emoji.command(
        name="removeduplicates",
        brief="Remove all emojis that has a duplicate",
        example=",emoji removeduplicates",
    )
    @bot_has_permissions(manage_emojis=True)
    @has_permissions(manage_emojis=True)
    async def emoji_removeduplicates(self: "Emojis", ctx: Context):
        if not ctx.guild.emojis:
            return await ctx.embed("There are **no emojis**", "denied")

        @offloaded
        def find_duplicates(emojis_bytes):
            duplicates = set()
            seen = set()
            for emoji, emoji_bytes in zip(ctx.guild.emojis, emojis_bytes):
                if emoji_bytes in seen:
                    duplicates.add(emoji)
                else:
                    seen.add(emoji_bytes)
            return duplicates

        try:
            emojis_bytes = await asyncio.gather(
                *[emoji.read() for emoji in ctx.guild.emojis]
            )
            duplicates = await find_duplicates(emojis_bytes)
            
            if not duplicates:
                return await ctx.embed("No duplicate emojis found", "success")
            
            deleted = 0
            for emoji in duplicates:
                try:
                    await emoji.delete(reason="Duplicate emoji removal")
                    deleted += 1
                except discord.Forbidden:
                    continue
                except discord.HTTPException:
                    continue
            
            if deleted:
                await ctx.embed(f"Successfully removed **{deleted}** duplicate emojis", "success")
            else:
                await ctx.embed("Could not remove any duplicate emojis", "denied")
                
        except Exception as e:
            await ctx.embed(f"An error occurred: {str(e)}", "error")

    @commands.group(
        name="sticker",
        brief="Manage the servers stickers",
        example=",sticker",
        invoke_without_command=True,
    )
    @bot_has_permissions(manage_emojis_and_stickers=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def sticker(self: "Emojis", ctx: Context):
        return await ctx.send_help(ctx.command.qualified_name)

    def rerun(self, image_bytes: bytes, size=(120, 120), max_size_kb=512):
        from PIL import Image, ImageSequence

        with BytesIO(image_bytes) as input_buffer:
            with Image.open(input_buffer) as im:
                frames = [
                    frame.copy()
                    for i, frame in enumerate(ImageSequence.Iterator(im))
                    if i % 3 == 0
                ]
                resized_frames = [frame.resize(size, Image.LANCZOS) for frame in frames]

                output_buffer = BytesIO()
                quality = 90
                resized_frames[0].save(
                    output_buffer,
                    format="GIF",
                    save_all=True,
                    append_images=resized_frames[1:],
                    loop=0,
                    optimize=True,
                    quality=quality,
                )

                while output_buffer.tell() > max_size_kb * 1024:
                    output_buffer = BytesIO()
                    quality -= 10
                    if quality < 10:
                        raise ValueError(
                            "Cannot compress the image to the required size."
                        )
                    resized_frames[0].save(
                        output_buffer,
                        format="GIF",
                        save_all=True,
                        append_images=resized_frames[1:],
                        loop=0,
                        optimize=True,
                        quality=quality,
                    )

                output_buffer.seek(0)
                return output_buffer.read()

    async def convert_sticker(self, img_url: str, svg: bool = False) -> discord.File:
        from PIL import Image, ImageSequence
        from wand.image import Image as IMG

        @offloaded
        def convert_gif(
            image_bytes: bytes,
            gif: Optional[bool] = False,
            size=(320, 320),
            max_size_kb=512,
        ):
            from PIL import Image, ImageSequence
            from wand.image import Image as IMG
            from io import BytesIO

            if gif is True:
                with BytesIO(image_bytes) as input_buffer:
                    with Image.open(input_buffer) as im:
                        frames = [
                            frame.copy()
                            for i, frame in enumerate(ImageSequence.Iterator(im))
                            if i % 3 == 0
                        ]
                        resized_frames = [
                            frame.resize(size, Image.LANCZOS) for frame in frames
                        ]

                        output_buffer = BytesIO()
                        quality = 90
                        resized_frames[0].save(
                            output_buffer,
                            format="GIF",
                            save_all=True,
                            append_images=resized_frames[1:],
                            loop=0,
                            optimize=True,
                            quality=quality,
                        )

                        while output_buffer.tell() > max_size_kb * 1024:
                            output_buffer = BytesIO()
                            quality -= 10
                            if quality < 10:
                                try:
                                    return self.rerun(image_bytes)
                                except Exception:
                                    raise ValueError(
                                        "Cannot compress the image to the required size."
                                    )
                            resized_frames[0].save(
                                output_buffer,
                                format="GIF",
                                save_all=True,
                                append_images=resized_frames[1:],
                                loop=0,
                                optimize=True,
                                quality=quality,
                            )

                        output_buffer.seek(0)
                        return output_buffer.read()
            else:
                with IMG(blob=image_bytes) as i:
                    i.coalesce()
                    i.optimize_layers()
                    i.compression_quality = 100
                    png_bytes = i.make_blob(format="apng" if i.animation else "png")
                    return png_bytes

        if ".gif" in img_url:
            conversion = await convert_gif(await get_raw_asset(img_url), True)
            filename = "meow.gif"
        else:
            conversion = await convert_gif(await get_raw_asset(img_url))
            filename = "meow.png"

        return discord.File(fp=BytesIO(conversion), filename=filename)

    @sticker.command(
        name="add",
        aliases=("create",),
        example=",sticker add (reply to sticker)",
        brief="Add a sticker recently posted in chat to the server",
    )
    @bot_has_permissions(manage_emojis_and_stickers=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def sticker_add(self: "Emojis", ctx: Context, *, name: str):
        """
        Create a new sticker
        """
        if len(ctx.guild.stickers) == ctx.guild.sticker_limit:
            return await ctx.embed(
                "This server exceeds the **sticker limit**", "denied"
            )

        if len(name) < 2 or len(name) > 30:
            return await ctx.embed(
                "Name must be between between **2** and **30 characters**", "denied"
            )

        try:
            image = await Stickers.search(ctx)
        except Exception:
            image = None
        if not image:
            image = await Attachment.search(ctx)
            logger.info(f"getting asset from {image}")
            if image is None:
                return await ctx.embed("No image provided", "denied")
        a = await get_raw_asset(image)
        ext = await get_file_ext(image)

        try:
            sticker = await ctx.guild.create_sticker(
                name=name,
                description="...",
                file=discord.File(fp=BytesIO(a), filename=f"{name}.{ext}"),
                reason=f"{self.bot.user.name.title()} Utilities [{ctx.author}]",
                emoji="??",
            )
        except Exception:
            message = await ctx.embed(
                "please wait while I attempt to compress this asset", "normal"
            )
            embed = message.embeds[0]
            try:
                file = await self.convert_sticker(image)
                sticker = await ctx.guild.create_sticker(
                    name=name,
                    description="...",
                    file=file,
                    reason=f"{self.bot.user.name.title()} Utilities [{ctx.author}]",
                    emoji="??",
                )
                embed.description = (
                    f"**Created** the sticker [**{sticker.name}**]({sticker.url})"
                )
            except Exception:
                embed.description = "**Failed** to create the sticker with the attachment provided due to it being to large"

            return await message.edit(embed=embed)
        return await ctx.embed(
            f"**Created** the sticker [**{sticker.name}**]({sticker.url})", "approved"
        )

    @sticker.command(
        name="remove",
        aliases=("delete",),
        usage="<sticker>",
        example=",sticker delete dumb_sticker",
        brief="Delete a sticker from the server",
    )
    @bot_has_permissions(manage_emojis_and_stickers=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def sticker_remove(self: "Emojis", ctx: Context, *, sticker: Sticker):
        """
        Delete an existing sticker
        """
        await sticker.delete(
            reason=f"{self.bot.user.name.title()} Utilities [{ctx.author}]"
        )
        return await ctx.embed("**Deleted** that sticker", "approved")

    @sticker.command(
        name="rename",
        aliases=("name",),
        usage="<sticker>",
        example=",sticker rename dumb_sticker, new_name,",
        brief="Rename a sticker in the server",
    )
    @bot_has_permissions(manage_emojis_and_stickers=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def sticker_rename(
        self: "Emojis", ctx: Context, sticker: Sticker, *, name: str
    ):
        """
        Rename an existing sticker
        """
        if len(name) < 2 or len(name) > 30:
            return await ctx.embed(
                "Name must be between **2** and **30 characters**", "denied"
            )
        await sticker.edit(
            name=name, reason=f"{self.bot.user.name.title()} Utilities[{ctx.author}]"
        )

        return await ctx.embed(f"**Renamed** that sticker to: **{name}**", "approved")

    @sticker.command(
        name="clean",
        aliases=["strip", "cleanse"],
        brief="Remove any vanity links or .gg/ URLs from all sticker names",
        example=",sticker clean",
    )
    @bot_has_permissions(manage_emojis_and_stickers=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def sticker_clean(self: "Emojis", ctx: Context):
        if not ctx.guild.stickers:
            return await ctx.embed("This server has no stickers to clean", "denied")

        cleaned = []
        skipped = []
        failed = []

        async def clean_sticker(sticker):
            try:
                if ".gg/" not in sticker.name:
                    skipped.append(sticker)
                    return None

                name = sticker.name.split(".gg/")[0]

                if len(name.strip()) < 2:
                    skipped.append(sticker)
                    return None

                cleaned_sticker = await sticker.edit(
                    name=name.strip(),
                    reason=f"Cleaned vanity URLs by {str(ctx.author)}",
                )
                cleaned.append(cleaned_sticker)
                return cleaned_sticker

            except Exception as e:
                logger.error(f"Failed to clean sticker {sticker.name}: {str(e)}")
                failed.append(sticker)
                return None

        await gather(*(clean_sticker(s) for s in ctx.guild.stickers))

        embed = discord.Embed(
            title="Sticker Cleanup Results",
            
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Summary",
            value=f"✅ Cleaned: {len(cleaned)}\n↪️ Skipped: {len(skipped)}\n❌ Failed: {len(failed)}",
            inline=False,
        )

        if cleaned:
            cleaned_names = "\n".join(f"• {s.name}" for s in cleaned[:10])
            if len(cleaned) > 10:
                cleaned_names += f"\n+ {len(cleaned)-10} more..."
            embed.add_field(name="Cleaned Stickers", value=cleaned_names, inline=False)

        if failed:
            failed_names = "\n".join(f"• {s.name}" for s in failed[:5])
            if len(failed) > 5:
                failed_names += f"\n+ {len(failed)-5} more..."
            embed.add_field(name="Failed Stickers", value=failed_names, inline=False)

        await ctx.send(embed=embed)

    @sticker.command(
        name="tag",
        brief="Add your vanity link to every sticker name",
        example=",sticker tag",
    )
    @bot_has_permissions(manage_emojis_and_stickers=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def sticker_tag(self: "Emojis", ctx: Context):
        if not ctx.guild.vanity_url_code:
            return await ctx.embed("this guild doesn't have a vanity", "denied")
        if not ctx.guild.stickers:
            return await ctx.embed(
                "There aren't any **stickers** in this server.", "denied"
            )

        async def tag_sticker(sticker):
            if f".gg/{ctx.guild.vanity_url_code}" in sticker.name:
                return

            return await sticker.edit(
                name=sticker.name[: 30 - len(f" .gg/{ctx.guild.vanity_url_code}")]
                + f" .gg/{ctx.guild.vanity_url_code}".strip(),
                reason=f"{self.bot.user.name.title()} Utilities[{ctx.author}]",
            )

        tagged = [await tag_sticker(s) for s in ctx.guild.stickers]

        return await ctx.embed(f"**Tagged** `{len(tagged)}` stickers", "approved")


async def get_file_ext(url: str) -> str:
    if "discord" in url:
        return "png"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            content_type = response.headers.get("Content-Type", "")
            if "image/gif" in content_type:
                return "gif"
            elif "image/png" in content_type:
                return "png"
            elif "image/jpeg" in content_type:
                return "jpg"
            elif "image/webp" in content_type:
                return "webp"
            elif "image/apng" in content_type:
                return "apng"
            else:
                return "png"


async def get_raw_asset(url: str) -> bytes:
    if "discord" not in url:
        url = f"https://proxy.greed.rocks?url={url}"
    await get_file_ext(url) 
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            logger.info(f"asset {url} got a response of {response.status}")
            binary = await response.read()
    return binary
