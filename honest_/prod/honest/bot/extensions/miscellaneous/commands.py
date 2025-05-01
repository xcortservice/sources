from asyncio import gather, sleep
from datetime import datetime
#
from io import BytesIO
from typing import List, Optional, Union

import arrow
from aiohttp import ClientSession
from discord import (Client, Color, Embed, FFmpegPCMAudio, File, Member,
                     Message, Role, TextChannel, User, app_commands, utils)
from discord.ext.commands import (Author, Cog, ColorConverter, CommandError,
                                  CurrentChannel, EmbedConverter, Emoji, check,
                                  command, group, has_permissions,
                                  hybrid_command)
from loguru import logger
from system.classes.database import Record
from system.classes.embed import embed_to_code
from system.patch.context import Context
from system.worker import offloaded

from .utils import tts


@offloaded
def collage_(_images: List[bytes]) -> List[bytes]:
    from io import BytesIO
    from math import sqrt

    from PIL import Image

    def _collage_paste(image: Image, x: int, y: int, background: Image):
        background.paste(
            image,
            (
                x * 256,
                y * 256,
            ),
        )

    if not _images:
        return None

    def open_image(image: bytes):
        return Image.open(BytesIO(image)).convert("RGBA").resize((300, 300))

    images = [open_image(i) for i in _images]
    rows = int(sqrt(len(images)))
    columns = (len(images) + rows - 1) // rows

    background = Image.new(
        "RGBA",
        (
            columns * 256,
            rows * 256,
        ),
    )
    for i, image in enumerate(images):
        _collage_paste(image, i % columns, i // columns, background)

    buffer = BytesIO()
    background.save(
        buffer,
        format="png",
    )
    buffer.seek(0)

    background.close()
    for image in images:
        image.close()
    return buffer.getvalue()


def is_booster():
    async def predicate(ctx: Context):
        if ctx.author.premium_since:
            return True
        if ctx.author.id in ctx.bot.owner_ids:
            return True
        if ctx.author.id == ctx.guild.owner_id:
            return True
        raise CommandError("you are not a guild booster")

    return check(predicate)


class Miscellaneous(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @command(
        name="tts",
        aliases=["speech", "texttospeech", "speak"],
        description="Convert text to audio",
        example=",tts join .gg/believe",
    )
    async def texttospeech(self, ctx: Context, *, text: str):
        speech_bytes = await tts(text)
        buffer = BytesIO(speech_bytes)
        if not ctx.author.voice and not ctx.guild.voice_client:
            return await ctx.send(file=File(fp=buffer, filename="tts.mp3"))
        if ctx.guild.voice_client:
            raise CommandError("i'm already connected to a voice channel")
        voice = await ctx.author.voice.channel.connect(self_deaf=True)
        audio = FFmpegPCMAudio(buffer, pipe=True)
        voice.play(audio)
        await ctx.send("TTS Output:")
        while voice.is_playing():
            await sleep(1)
        return await voice.disconnect()

    @hybrid_command(
        name="topcommands",
        aliases=["topcmds"],
        description="view the top commands on honest",
        with_app_command=True,
    )
    async def topcommands(self, ctx: Context):
        return

    @hybrid_command(
        with_app_command=True,
        name="topavatars",
        description="Get a leaderboard with the users that have the most avatar changes",
    )
    async def topavatars(self, ctx: Context):
        return

    async def get_avatars(self, avatars: List[Record]):
        async def get_avatar(row: Record):
            async with ClientSession() as session:
                async with session.get(row.url) as response:
                    data = await response.read()
            return data

        data = [await get_avatar(r) for r in avatars]
        # i would gather but that would disorganize the list
        return data

    @hybrid_command(
        with_app_command=True,
        aliases=["avatars", "avh"],
        name="avatarhistory",
        description="get a user's avatar changes that have been recorded by the bot",
        example=",avatarhistory @aiohttp",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def avatarhistory(
        self, ctx: Context, *, user: Optional[Union[Member, User]] = Author
    ):
        events_cog = self.bot.get_cog("MiscellaneousEvents")
        if not events_cog:
            raise CommandError("not currently tracking avatar changes")
        user_avatars = await events_cog.get_user_avatars(user)
        if not user_avatars:
            raise CommandError(f"no avatars tracked for **{str(user)}**")
        total = len(user_avatars)
        useable_avatars = user_avatars[:35]
        embed = Embed(
            title=f"Avatar History for {str(user)}",
            description=f"Viewing `{len(useable_avatars)}` out of `{total}` avatars",
        )
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        avatar_data = await self.get_avatars(useable_avatars)
        avatar_collage = await collage_(avatar_data)
        file = File(fp=BytesIO(avatar_collage), filename="collage.png")
        embed.set_image(url="attachment://collage.png")
        return await ctx.send(file=file, embed=embed)

    @hybrid_command(
        name="clearavatars",
        aliases=["clavs", "clavatars", "clav"],
        description="reset your recorded avatar changes",
        with_app_command=True,
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def clearavatars(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM avatars WHERE user_id = $1""", ctx.author.id
        )
        return await ctx.success("successfully cleared your **avatars**")

    @hybrid_command(
        name="guildnames",
        aliases=["gnames"],
        description="view recorded guild name changes",
        with_app_command=True,
    )
    async def guildnames(self, ctx: Context):
        guild_id = ctx.guild.id
        if not (
            history := await self.bot.db.fetch(
                """SELECT name, ts FROM guild_names WHERE user_id = $1 ORDER BY ts DESC""",
                guild_id,
            )
        ):
            raise CommandError("That server has no **name** history")
        embed = Embed(title="Guild Name history").set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
        )
        rows = [
            f"`{i}` \"{t.name}\" ({utils.format_dt(t.ts, style='R')})"
            for i, t in enumerate(history, start=1)
        ]
        return await ctx.paginate(embed, rows, type="name", plural_type="names")

    @hybrid_command(
        name="namehistory",
        aliases=["usernames", "pastnames", "pastusernames", "names"],
        description="get a user's name changes that have been recorded by the bot",
        example=",names @aiohttp",
        with_app_command=True,
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def namehistory(
        self, ctx: Context, *, member: Optional[Union[Member, User]] = Author
    ):
        if not (
            history := await self.bot.db.fetch(
                """SELECT username, type, ts FROM names WHERE user_id = $1 ORDER BY ts DESC""",
                member.id,
            )
        ):
            raise CommandError(
                f"{'You have' if member == ctx.author else f'{member.mention} has'} no **name** history"
            )
        embed = Embed(title="Name history").set_author(
            name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
        )
        rows = [
            f"`{i}{t.type[0].upper()}` \"{t.username}\" ({utils.format_dt(t.ts, style='R')})"
            for i, t in enumerate(history, start=1)
        ]
        return await ctx.paginate(embed, rows, type="name", plural_type="names")

    @hybrid_command(
        name="clearnamehistory",
        aliases=["clearnames", "cln"],
        description="clear your recorded username history",
        with_app_command=True,
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def clearnamehistory(self, ctx: Context):
        await self.bot.db.execute(
            """DELETE FROM names WHERE user_id = $1""", ctx.author.id
        )
        return await ctx.success("successfully cleared your **name history**")

    @hybrid_command(
        name="firstmessage",
        aliases=["firstmsg", "first"],
        description="get the channel's first message",
        with_app_command=True,
    )
    async def firstmessage(
        self, ctx: Context, *, channel: TextChannel = CurrentChannel
    ):
        # you never flatten an asynchronous iterator thats just retarded lol
        async for message in channel.history(limit=1, oldest_first=True):
            embed = Embed(
                title=f"First message in #{channel}",
                url=message.jump_url,
                description=(
                    message.content
                    if message.content != ""
                    else "This message contains only an attachment, embed or sticker"
                ),
                timestamp=message.created_at,
            ).set_author(
                name=str(ctx.author),
                icon_url=ctx.author.display_avatar.url,
                url=ctx.author.url,
            )
            _ = await ctx.send(embed=embed)
            break
        return _

    @command(
        name="afk",
        description="let the server members know you are away",
        example=",afk zzz",
    )
    async def afk(self, ctx: Context, *, status: Optional[str] = "AFK"):
        status = status.shorten(100)
        await self.bot.db.execute(
            """
            INSERT INTO afk (
                user_id,
                status
            ) VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO NOTHING;
            """,
            ctx.author.id,
            status,
        )

        await ctx.success(f"You're now AFK with the status: **{status}**")

    @command(
        name="createembed",
        aliases=["ce"],
        example=",createembed {embed}{description: whats up}",
        description="Create an embed using an embed code",
    )
    @has_permissions(manage_messages=True)
    async def createembed(self, ctx: Context, *, code: EmbedConverter):
        from system.classes.exceptions import EmbedError  # type: ignore

        try:
            await self.bot.send_embed(ctx.channel, code, user=ctx.author)
        except EmbedError as e:
            raise e
        except Exception as e:
            raise e

    @command(
        name="embedcode",
        description="get the code of an already existing embed",
        example=",embedcode .../channels/...",
    )
    @has_permissions(manage_messages=True)
    async def embedcode(self, ctx: Context, message: Message):
        code = embed_to_code(message)
        return await ctx.success(
            f"**Successfully copied the embed code**\n```{code}```"
        )

    @command(
        name="purgesnipe",
        aliases=["ps"],
        description="Snipe the most recent purged messages",
        example=",purgesnipe 1",
    )
    @has_permissions(manage_messages=True)
    async def purgesnipe(self, ctx: Context, index: Optional[int] = 1):
        rows = await self.bot.db.fetch(
            """SELECT id FROM message_logs WHERE guild_id = $1 AND channel_id = $2 ORDER BY created_at DESC""",
            ctx.guild.id,
            ctx.channel.id,
        )
        logger.info(len(rows))
        if not rows:
            raise CommandError(f"theres no **purge snipe** at index `{index}`")
        if index <= 0:
            index = 1
        index -= 1
        row = rows[index]
        return await ctx.success(
            f"[here is your **purge snipe**](https://logs.coffin.bot/raw/{row.id})"
        )

    @command(
        name="snipe",
        aliases=["s"],
        description="Snipe a recently deleted message",
        example=",snipe 1",
    )
    async def snipe(self, ctx: Context, index: Optional[int] = 1):
        if not (
            snipe := await self.bot.snipes.get_entry(
                ctx.channel, type="snipe", index=index
            )
        ):
            raise CommandError(f"theres no **snipe** at index `{index}`")
        total = snipe[1]
        snipe = snipe[0]
        embed = Embed(
            color=self.bot.color,
            description=(
                snipe.get("content")
                or (
                    snipe["embeds"][0].get("description") if snipe.get("embeds") else ""
                )
            ),
            timestamp=datetime.fromtimestamp(snipe.get("timestamp")),
        )

        embed.set_author(
            name=snipe.get("author").get("name"),
            icon_url=snipe.get("author").get("avatar"),
        )

        if att := snipe.get("attachments"):
            embed.set_image(url=att[0])

        elif sticks := snipe.get("stickers"):
            embed.set_image(url=sticks[0])

        embed.set_footer(
            text=f"Deleted {arrow.get(snipe.get('timestamp')).humanize()} | {index}/{total}"
        )

        return await ctx.send(embed=embed)

    @command(
        name="editsnipe",
        aliases=["es", "edits"],
        description="snipe a recently editted message",
        example=",editsnipe 1",
    )
    async def editsnipe(self, ctx: Context, index: Optional[int] = 1):
        if not (
            snipe := await self.bot.snipes.get_entry(
                ctx.channel, type="editsnipe", index=index
            )
        ):
            raise CommandError(f"theres no **editsnipe** at index `{index}`")

        total = snipe[1]
        snipe = snipe[0]
        embed = Embed(
            color=self.bot.color,
            description=(
                snipe.get("content")
                or ("Message contains an embed" if snipe.get("embeds") else "")
            ),
            timestamp=datetime.fromtimestamp(snipe.get("timestamp")),
        )

        embed.set_author(
            name=snipe.get("author").get("name"),
            icon_url=snipe.get("author").get("avatar"),
        )

        if att := snipe.get("attachments"):
            embed.set_image(url=att[0])

        elif sticks := snipe.get("stickers"):
            embed.set_image(url=sticks[0])

        embed.set_footer(
            text=f"Edited {arrow.get(snipe.get('timestamp')).humanize()} | {index}/{total}",
            icon_url=ctx.author.display_avatar,
        )

        return await ctx.send(embed=embed)

    @command(
        name="reactionsnipe",
        aliases=["reactsnipe", "rs"],
        description="snipe a recently removed reaction",
        example=",reactionsnipe 1",
    )
    async def reactionsnipe(self, ctx: Context, index: Optional[int] = 1):
        if not (
            snipe := await self.bot.snipes.get_entry(
                ctx.channel, type="reactionsnipe", index=index
            )
        ):
            raise CommandError(f"theres no **reactionsnipe** at index `{index}`")
        total = snipe[1]  # type: ignore
        snipe = snipe[0]
        embed = Embed(
            color=self.bot.color,
            description=(
                f"""**{str(snipe.get('author').get('name'))}** reacted with {snipe.get('reaction')
                if not snipe.get('reaction').startswith('https://cdn.discordapp.com/')
                else str(snipe.get('reaction'))} <t:{int(snipe.get('timestamp'))}:R>"""
            ),
        ).set_footer(text=f"{index}/{total}")

        return await ctx.send(embed=embed)

    @command(
        name="clearsnipe",
        aliases=["cs"],
        description="Clear all deleted messages from wock",
        example=",clearsnipe",
    )
    @has_permissions(manage_messages=True)
    async def clearsnipes(self, ctx: Context):
        await self.bot.snipes.clear_entries(ctx.channel)
        return await ctx.success(f"**Cleared** snipes for {ctx.channel.mention}")

    @group(
        name="boosterrole",
        aliases=["boosterroles", "br"],
        description="make your own role as a reward for boosting the server",
        invoke_without_command=True,
    )
    async def boosterrole(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @boosterrole.command(
        name="base",
        aliases=["baserole"],
        description="set the role that you want the booster roles to be underneath",
        example=",boosterrole base @custom",
    )
    @has_permissions(manage_roles=True)
    async def boosterrole_base(self, ctx: Context, *, role: Role):
        await self.bot.db.execute(
            """INSERT INTO config (guild_id, booster_base) VALUES($1, $2) ON CONFLICT(guild_id) DO UPDATE SET booster_base = excluded.booster_base""",
            ctx.guild.id,
            role.id,
        )
        roles = await self.bot.db.fetch(
            """SELECT role_id FROM booster_roles WHERE guild_id = $1""", ctx.guild.id
        )
        delete = []
        if role >= ctx.guild.me.top_role:
            raise CommandError(f"{role.mention} is higher than I am in the hierarchy")
        for role_id in roles:
            if not (role := ctx.guild.get_role(role_id)):
                delete.append(role_id)
                continue
            await role.edit(position=(role.position - 1).minimum(0))
        if len(delete) > 0:
            await self.bot.db.execute(
                """DELETE FROM booster_roles WHERE guild_id = $1 AND role_id = ANY($2::BIGINT[])""",
                ctx.guild.id,
                delete,
            )
        return await ctx.success(
            f"successfully set the **base booster role** as {role.mention}"
        )

    async def get_base(self, ctx: Context):
        base = await self.bot.db.fetchval(
            """SELECT booster_base FROM config WHERE guild_id = $1""", ctx.guild.id
        )
        if not base:
            return None
        if not (base_role := ctx.guild.get_role(base)):
            return None
        return (base_role.position - 1).minimum(0)

    @boosterrole.command(
        name="create",
        aliases=["c"],
        description="create a new booster role",
        example=",boosterrole create {role_name} {emoji}",
    )
    @is_booster()
    async def boosterrole_create(
        self, ctx: Context, color: ColorConverter, *, name: str
    ):
        if await self.bot.db.fetchval(
            """SELECT role_id FROM booster_roles WHERE guild_id = $1""", ctx.guild.id
        ):
            raise CommandError("you already have a booster role")
        base = await self.get_base(ctx)
        kwargs = {"position": base} if base else {}
        role = await ctx.guild.create_role(name=name, color=color, **kwargs)
        await self.bot.db.execute(
            """INSERT INTO booster_roles (guild_id, user_id, role_id) VALUES ($1, $2, $3)""",
            ctx.guild.id,
            ctx.author.id,
            role.id,
        )
        return await ctx.success(
            f"successfully assigned you {role.mention} as your booster role"
        )

    @boosterrole.command(
        name="color",
        description="change the color of your booster role",
        example=",boosterrole color purple",
    )
    async def boosterrole_color(self, ctx: Context, *, color: ColorConverter):
        if not (
            role := await self.bot.db.fetchval(
                """SELECT role_id FROM booster_roles WHERE guild_id = $1 AND user_id = $2""",
                ctx.guild.id,
                ctx.author.id,
            )
        ):
            raise CommandError("you dont have a booster role")
        await ctx.guild.get_role(role).edit(color=color)
        return await ctx.success(f"successfully re-colored your role to {str(color)}")

    @boosterrole.command(
        name="share",
        description="share your booster roles with other users",
        example=",boosterrole share @aiohttp",
    )
    async def boosterrole_share(self, ctx: Context, *, member: Member):
        if not (
            role_id := await self.bot.db.fetchval(
                """SELECT role_id FROM booster_roles WHERE guild_id = $1 AND user_id = $2""",
                ctx.guild.id,
                ctx.author.id,
            )
        ):
            raise CommandError("you dont have a booster role")
        if not (role := ctx.guild.get_role(role_id)):
            raise CommandError("your booster role has been **DELETED**")
        if member.id == ctx.author.id:
            raise CommandError("you cannot share your booster role to yourself.")
        await member.add_roles(role, reason="Booster Role Shared")
        return await ctx.success(
            f"successfully shared your booster role with {member.mention}"
        )

    @boosterrole.command(name="cleanup", description="cleanup unused booster roles")
    @has_permissions(manage_roles=True)
    async def boosterrole_cleanup(self, ctx: Context):
        if not (
            roles := await self.bot.db.fetchval(
                """SELECT role_id FROM booster_roles WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            raise CommandError("there are no booster roles")
        delete = []
        cleanable_roles = []
        for role_id in roles:
            if not (role := ctx.guild.get_role(role_id)):
                delete.append(role_id)
                continue
            members = [m for m in role.members if m.premium_since]
            if len(members) == 0:
                cleanable_roles.append(role)
                delete.append(role_id)
        if len(cleanable_roles) == 0:
            raise CommandError("there are no unused booster roles")
        for role in cleanable_roles:
            await role.delete(reason="Booster Role Cleanup")
        try:
            await self.bot.db.execute(
                """DELETE FROM booster_roles WHERE guild_id = $1 AND role_id = ANY($2::BIGINT[]))""",
                ctx.guild.id,
                delete,
            )
        except Exception:
            pass
        return await ctx.success(
            f"successfully cleaned up `{len(cleanable_roles)}` **booster roles**"
        )

    @boosterrole.command(
        name="icon",
        description="set an icon on your booster role",
        example=",boosterrole icon <:sup:12312312321>",
    )
    async def boosterrole_icon(
        self, ctx: Context, *, icon: Optional[Union[Emoji, str]] = None
    ):
        if not (
            role := await self.bot.db.fetchval(
                """SELECT role_id FROM booster_roles WHERE guild_id = $1 AND user_id = $2""",
                ctx.guild.id,
                ctx.author.id,
            )
        ):
            raise CommandError("you dont have a booster role")
        data = None
        if not ctx.guild.premium_subscription_count >= 7:
            raise CommandError(
                "you need to have 7+ boosts to set an icon on your booster"
            )
        if not icon:
            if len(ctx.message.attachments) == 0:
                raise CommandError("an Emoji, URL, or Attachment is required")
            data = await ctx.message.attachments[0].read()
        elif isinstance(icon, str):
            if not icon.startswith("http"):
                raise CommandError("that is not a valid URL")
            async with ClientSession() as session:
                async with session.get(icon) as response:
                    data = await response.read()
        else:
            if icon.is_custom_emoji():
                data = await icon.read()
            else:
                data = icon
        if not data:
            raise CommandError("no valid icon was found in your input")
        await ctx.guild.get_role(role).edit(display_icon=data)
        return await ctx.success("successfully changed your booster role icon")

    @boosterrole.command(
        name="name",
        description="rename your booster role",
        example=",boosterrole name xD",
    )
    async def boosterrole_name(self, ctx: Context, *, name: str):
        if not (
            role := await self.bot.db.fetchval(
                """SELECT role_id FROM booster_roles WHERE guild_id = $1 AND user_id = $2""",
                ctx.guild.id,
                ctx.author.id,
            )
        ):
            raise CommandError("you dont have a booster role")
        await ctx.guild.get_role(role).edit(name=name)
        return await ctx.success(
            f"successfully renamed your booster role to **{name}**"
        )


async def setup(bot: Client):
    await bot.add_cog(Miscellaneous(bot))
