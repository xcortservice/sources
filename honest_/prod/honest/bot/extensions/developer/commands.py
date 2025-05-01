import os, humanize, aiohttp
from io import StringIO
from typing import Optional, Union
from aiohttp.web_exceptions import HTTPException
from discord import (
    Client, 
    Embed, 
    File, 
    Interaction, 
    Member, 
    SelectOption, 
    User, 
    ui
)
from discord.ext.commands import (
    Cog, 
    CommandError, 
    Converter, 
    GuildID, 
    command, 
    group, 
    is_owner
)
from jishaku.codeblocks import codeblock_converter
from system.classes.builtins import get_error, human_join
from system.patch.checks import is_staff
from system.patch.context import Context
from tools import timeit

def get_directories(path: str = "extensions"):
    return [
        dir_name
        for dir_name in os.listdir(path)
        if os.path.isdir(os.path.join(path, dir_name)) and dir_name != "__pycache__"
    ]


FILES = ["commands", "events"]


class Extension(Converter):
    async def convert(self, ctx: Context, argument: str):
        extensions = []
        directories = get_directories()
        argument = argument.replace("extensions.", "")
        arg = argument.split(".")
        if len(arg) == 1:
            if arg[0] in directories:
                extensions.append(f"extensions.{arg[0]}.commands")
                extensions.append(f"extensions.{arg[0]}.events")
        if len(arg) == 2:
            if arg[0] in directories and arg[1] in FILES:
                extensions.append(f"extensions.{arg[0]}.{arg[1]}")
        return extensions


class Extensions(Converter):
    async def convert(self, ctx: Context, argument: str):
        extensions = []
        argument = argument.replace("extensions.", "")
        directories = get_directories()
        if argument.lower() in ("~", "*", "all"):
            for directory in directories:
                extensions.append(f"extensions.{directory}.commands")
                extensions.append(f"extensions.{directory}.events")
            return extensions
        else:
            if "," in argument:
                for arg in argument.split(","):
                    arg = arg.lstrip().rstrip()
                    if ext := await Extension().convert(ctx, arg):
                        extensions.extend(ext)
                return extensions
            else:
                return await Extension().convert(ctx, argument)


class ReloadSelect(ui.Select):
    def __init__(self, bot, data: dict):
        self.bot = bot
        self.data = data
        options = [
            SelectOption(label=k, description=k, value=k) for k, v in data.items()
        ]
        super().__init__(
            custom_id="Reload:Select",
            placeholder="Failed Reloads...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: Interaction):
        value = self.values[0]
        tb = self.data.get(value)
        await interaction.response.send_message(
            file=File(fp=StringIO(tb), filename="traceback.txt"), ephemeral=True
        )
        self.values.clear()
        return await interaction.message.edit(view=self.view)


class ReloadView(ui.View):
    def __init__(self, bot, data):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(ReloadSelect(self.bot, data))


class Developer(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @command(
        name="python",
        aliases=["py", "eval", "evaluate"],
        description="execute python code",
    )
    @is_owner()
    async def python(self, ctx: Context, *, argument: codeblock_converter):
        async with timeit() as timer:
            await ctx.invoke(self.bot.get_command("jishaku python"), argument=argument)

        return await ctx.send(
            content=f"took {humanize.naturaldelta(timer.elapsed, minimum_unit='microseconds')}"
        )

    @group(
        name="system",
        aliases=["sys"],
        description="control payment and authorizations with the bot",
        invoke_without_command=True,
    )
    @is_staff()
    async def system(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @system.command(
        name="reload",
        description="reload an extension or all extensions",
        example=",system reload antinuke",
    )
    @is_owner()
    async def system_reload(self, ctx: Context, *, extension: Extensions):
        embed = Embed(title="Reloads").set_author(
            name=str(ctx.author), icon_url=ctx.author.display_avatar.url
        )
        good = []
        bad = {}
        for ext in extension:
            try:
                await self.bot.reload_extension(ext)
                good.append(ext)
            except Exception as e:
                bad[ext] = get_error(e)
        if len(bad) > 0:
            bad_str = human_join([f"`{i}`" for i in list(bad.keys())], final="and ")
            view = ReloadView(self.bot, bad)
            bad_str = f", \nfailed to load {bad_str}"
            kwargs = {"view": view}
        else:
            bad_str = ""
            kwargs = {}
        successfully_str = human_join([f"`{i}`" for i in good], final="and")

        embed.description = f"successfully reloaded {successfully_str}{bad_str}"
        return await ctx.send(embed=embed, **kwargs)

    @system.command(
        name="whitelist",
        aliases=["authorize", "auth", "wl"],
        description="whitelist or unwhitelist a guild",
        example=",system whitelist 2737373",
    )

    @is_staff()
    async def system_whitelist(self, ctx: Context, guild_id: GuildID):
        if not await self.bot.db.fetchrow(
            """SELECT * FROM authorizations WHERE guild_id = $1""", guild_id
        ):
            await self.bot.db.execute(
                """DELETE FROM authorizations WHERE guild_id = $1""", guild_id
            )
            return await ctx.success(f"removed the authorization from {guild_id}")
        else:
            await self.bot.db.execute(
                """INSERT INTO authorizations (guild_id, creator) VALUES($1, $2)""",
                guild_id,
                ctx.author.id,
            )
            return await ctx.success(f"successfully authorized {guild_id}")

    @system.command(
        name="transfer",
        aliases=["tr"],
        description="transfer a whitelist",
        example=",system transfer 273737 373636366",
    )
    @is_staff()
    async def system_transfer(self, ctx: Context, current: GuildID, new: GuildID):
        try:
            await self.bot.db.execute(
                """UPDATE authorizations SET guild_id = $1, transfers = 1 WHERE guild_id = $2""",
                new,
                current,
            )
            return await ctx.success("successfully transferred that whitelist")
        except Exception:
            return await ctx.fail("that whitelist has already been transferred")

    @system.command(
        name="donator",
        description="remove or add donator to a user",
        example=",system donator @jon",
    )
    @is_staff()
    async def system_donator(self, ctx: Context, *, user: Union[Member, User]):
        if await self.bot.db.fetchrow(
            """SELECT * FROM donators WHERE user_id = $1""", user.id
        ):
            await self.bot.db.execute(
                """DELETE FROM donators WHERE user_id = $1""", user.id
            )
            return await ctx.success(
                f"successfully removed donator from **{str(user)}**"
            )
        else:
            await self.bot.db.execute(
                """INSERT INTO donators (user_id, creator) VALUES($1, $2)""",
                user.id,
                ctx.author.id,
            )
            return await ctx.success(f"successfully gave donator to **{str(user)}**")

    @system.command(
        name="globalban",
        aliases=["glb"],
        description="ban or unban a user globally",
        example=",system globalban @jonathan",
    )
    @is_owner()
    async def system_globalban(self, ctx: Context, user: Union[Member, User]):
        if await self.bot.db.fetchrow(
            """SELECT * FROM global_ban WHERE user_id = $1""", user.id
        ):
            await self.bot.db.execute(
                """DELETE FROM global_ban WHERE user_id = $1""", user.id
            )
            message = f"successfully **UNBANNED** {str(user)} globally"
        else:
            await self.bot.db.execute(
                """INSERT INTO global_ban (user_id, author) VALUES($1, $2)""",
                user.id,
                ctx.author.id,
            )
            message = f"successfully **BANNED** {str(user)} globally"
        return await ctx.success(message)

    @system.command(
        name="blacklist",
        description="blacklist or unblacklist a guild or user",
        example=",system blacklist @jon",
        parameters={
            "reason": {"converter": str, "default": "No reason provided"},
        },
    )
    @is_staff()
    async def system_blacklist(
        self, ctx: Context, snowflake: Union[Member, User, GuildID]
    ):
        reason = f"Blacklisted by {str(ctx.author)} with No Reason Provided"
        if isinstance(snowflake, (User, Member)):
            if not await self.bot.db.fetchrow(
                """SELECT * FROM blacklists WHERE object_id = $1 AND object_type = $2""",
                snowflake.id,
                "user",
            ):
                await self.bot.db.execute(
                    """INSERT INTO blacklists (object_id, object_type, creator, reason) VALUES($1, $2, $3, $4)""",
                    snowflake.id,
                    "user",
                    ctx.author.id,
                    reason,
                )
                message = f"successfully blacklisted the **user** {str(snowflake)}"
            else:
                await self.bot.db.execute(
                    """DELETE FROM blacklists WHERE object_id = $1 AND object_type = $2""",
                    snowflake.id,
                    "user",
                )
                message = f"successfully unblacklisted the **user** {str(snowflake)}"
        else:
            if not await self.bot.db.fetchrow(
                """SELECT * FROM blacklists WHERE object_id = $1 AND object_type = $2""",
                snowflake,
                "guild",
            ):
                await self.bot.db.execute(
                    """INSERT INTO blacklists (object_id, object_type, creator, reason) VALUES($1, $2, $3, $4)""",
                    snowflake,
                    "guild",
                    ctx.author.id,
                    reason,
                )
                message = f"successfully blacklisted the **guild** {str(snowflake)}"
            else:
                await self.bot.db.execute(
                    """DELETE FROM blacklists WHERE object_id = $1 AND object_type = $2""",
                    snowflake,
                    "guild",
                )
                message = f"successfully unblacklisted the **guild** {str(snowflake)}"
        return await ctx.success(message)

    @command(name="traceback", aliases=["tb", "trace"])
    @is_owner()
    async def traceback(self, ctx: Context, code: Optional[str] = None):
        if reference := await self.bot.get_reference(ctx.message):
            if reference.author.id == self.bot.user.id:
                if reference.content.startswith("`"):
                    code = code.split("`")[1]
        if not code:
            raise CommandError("no code was provided")
        data = await self.bot.db.fetchrow(
            """SELECT * FROM traceback WHERE error_code = $1""", code
        )
        if not data:
            return await ctx.fail(f"no error under code **{code}**")
        self.bot.get_guild(data.guild_id)  # type: ignore
        self.bot.get_channel(data.channel_id)  # type: ignore
        self.bot.get_user(data.user_id)  # type: ignore
        if len(data.error_message) > 2000:
            return await ctx.send(
                file=File(fp=StringIO(data.error_message), filename="tb.txt")
            )
        embed = Embed(
            title=f"Error Code {code}", description=f"```{data.error_message}```"
        )
        embed.add_field(name="Context", value=f"`{data.content}`", inline=False)
        return await ctx.send(embed=embed)

    @command(
        name="setpfp", 
        description="Change the bot's profile picture",
        example=",system setpfp <file> or <url>"
    )
    @is_owner()
    async def setpfp(self, ctx: Context, *, image: str = None):
        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif image:
            image_url = image
        else:
            return await ctx.warn(f"Please provide an image URL or upload an image.")

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    return await ctx.deny(f"Failed to fetch the image.")
                data = await resp.read()

        try:
            await self.bot.user.edit(avatar=data)
            await ctx.approve(f"Changed my **pfp** successfully!")
        except HTTPException as e:
            await ctx.deny(f"Failed to change profile picture: {e}")

    @command(
        name="setbanner", 
        description="Change the bot's banner",
        example=",system setbanner <file> or <url>"
    )
    @is_owner()
    async def setbanner(self, ctx: Context, *, image: str = None):
        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif image:
            image_url = image
        else:
            return await ctx.warn(f"Please provide an image URL or upload an image.")

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    return await ctx.deny(f"Failed to fetch the image.")
                data = await resp.read()

        try:
            await self.bot.user.edit(banner=data)
            await ctx.success(f"Changed my **banner** successfully!")
        except HTTPException as e:
            await ctx.fail(f"Failed to change banner: {e}")


async def setup(bot: Client):
    await bot.add_cog(Developer(bot))
