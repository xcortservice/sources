from __future__ import annotations

import typing
import re
import inspect
from typing import TYPE_CHECKING, Optional, Union
import aiohttp
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord.ext.commands import Context, Converter
from discord import Color
from greed.framework.pagination import Paginator
from greed.shared.config import Colors

if TYPE_CHECKING:
    from greed.framework import Greed

logger = logging.getLogger("greed/plugins/config/boosterrole")


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
        url = f"https://proxy.rival.rocks?url={url}"
    await get_file_ext(url)  # type: ignore
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            logger.info(f"asset {url} got a response of {response.status}")
            binary = await response.read()
    return binary


class BadColorArgument(commands.BadArgument):
    def __init__(self, argument: str):
        self.argument = argument
        super().__init__(f'Color "{argument}" not found.')


class ColorPicker:
    def __init__(self):
        self.colors = {}

    async def setup(self):
        self.colors = {
            "red": "#FF0000",
            "green": "#00FF00",
            "blue": "#0000FF",
            "yellow": "#FFFF00",
            "purple": "#800080",
            "orange": "#FFA500",
            "pink": "#FFC0CB",
            "brown": "#A52A2A",
            "black": "#000000",
            "white": "#FFFFFF",
            "gray": "#808080",
            "cyan": "#00FFFF",
            "magenta": "#FF00FF",
            "lime": "#00FF00",
            "maroon": "#800000",
            "navy": "#000080",
            "olive": "#808000",
            "teal": "#008080",
            "silver": "#C0C0C0",
        }

    async def search(self, query: str) -> Optional[dict]:
        query = query.lower()
        for name, hex_code in self.colors.items():
            if query in name:
                return {"name": name, "hex": hex_code}
        return None


def check_guild_boost_level():
    async def predicate(ctx: Context) -> bool:
        if ctx.command.qualified_name == "help":
            return True
        if not ctx.author.premium_since and not ctx.author.guild.owner:
            raise commands.CommandError(
                "You need to be a **Booster** to use this command"
            )
        if ctx.guild:
            if ctx.guild.premium_tier >= 2:
                return True
            else:
                raise commands.CommandError(
                    f"This guild is not **level 3 ** boosted\n > (**Current level: ** `{ctx.guild.premium_tier}`)"
                )

    return commands.check(predicate)


def check_br_status():
    async def predicate(ctx: Context) -> bool:
        if ctx.command.qualified_name == "help":
            return True
        if ctx.guild.premium_tier < 2:
            raise commands.CommandError(
                f"This guild is **not ** currently level ** {ctx.guild.premium_tier} ** and must be ** level 2 ** to use this."
            )
        if not await ctx.bot.db.fetchval(
            "SELECT status FROM br_status WHERE guild_id = $1", ctx.guild.id
        ):
            raise commands.CommandError(
                "**Booster roles** are **not** enabled in this guild."
            )
        if not ctx.author.premium_since and ctx.author.id not in ctx.bot.owner_ids:
            raise commands.CommandError(
                "You need to be a **Booster** to use this command."
            )
        return True

    return commands.check(predicate)


class ColorConverter(Converter[Color]):
    async def convert(self, ctx: Context, argument: str):
        if argument == "black":
            argument = "010101"
        if hex_match := re.match(r"#?[a-f0-9]{6}", argument.lower()):
            return f"0x{argument.lower().strip('#')}"
        if not hasattr(ctx.bot, "colorpicker"):
            ctx.bot.colorpicker = ColorPicker()
            await ctx.bot.colorpicker.setup()
        if match := await ctx.bot.colorpicker.search(argument):
            if self.as_object is True:
                return match
            else:
                return Color.from_str(match.hex)
        try:
            is_method = False
            arg = argument.lower().replace(" ", "_")
            method = getattr(Color, arg, None)
            if (
                arg.startswith("from_")
                or method is None
                or not inspect.ismethod(method)
            ):
                is_method = False
            else:
                is_method = True
            if is_method is True:
                return method()
        except Exception:
            pass
        raise BadColorArgument(argument)


class Role(Converter[discord.Role]):
    async def convert(self, ctx: Context, argument: str) -> discord.Role:
        try:
            return await commands.RoleConverter().convert(ctx, argument)
        except commands.BadArgument:
            raise commands.BadArgument(f"Role {argument} not found.")


class RateLimitError(commands.CommandError):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(
            f"Please wait {retry_after:.1f} seconds before using this command again."
        )


class RoleLimitError(commands.CommandError):
    def __init__(self, limit: int):
        super().__init__(
            f"This server has reached the maximum number of booster roles ({limit})."
        )


class boosterrole(commands.Cog, name="BoosterRole"):
    def __init__(self, bot: "Greed"):
        self.bot = bot
        self._role_creation_locks = {}
        self._last_role_edit = {}

    async def check_rate_limit(
        self, ctx: Context, key: str, limit: int, window: int
    ) -> None:
        now = datetime.utcnow()
        if key not in self._last_role_edit:
            self._last_role_edit[key] = []

        self._last_role_edit[key] = [
            t for t in self._last_role_edit[key] if now - t < timedelta(seconds=window)
        ]

        if len(self._last_role_edit[key]) >= limit:
            retry_after = (
                self._last_role_edit[key][0] + timedelta(seconds=window) - now
            ).total_seconds()
            raise RateLimitError(retry_after)

        self._last_role_edit[key].append(now)

    async def get_role_limit(self, ctx: Context) -> int:
        if ctx.guild.premium_tier == 3:
            return 250
        elif ctx.guild.premium_tier == 2:
            return 150
        elif ctx.guild.premium_tier == 1:
            return 100
        else:
            return 50

    @commands.group(
        name="boosterroles",
        aliases=["br", "boosterrole"],
        brief="Commands for setting up and using booster roles in your guild",
        example=",boosterroles",
    )
    async def br(self, ctx: Context):
        if ctx.subcommand_passed is not None:
            return
        return await ctx.send_help(ctx.command.qualified_name)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        if not (
            role_id := await self.bot.db.fetchval(
                "SELECT role_id FROM br WHERE role_id = $1", role.id
            )
        ):
            return

        await self.bot.db.execute("DELETE FROM br WHERE role_id = $1", role_id)

    @commands.Cog.listener("on_member_remove")
    async def br_deletion(self, member: discord.Member):
        if role_id := await self.bot.db.fetchval(
            """SELECT role_id FROM br WHERE guild_id = $1 AND user_id = $2""",
            member.guild.id,
            member.id,
        ):
            if role := member.guild.get_role(role_id):
                await role.delete(reason="boost role auto cleanup")

    @br.command(
        name="setup",
        aliases=("enable",),
        brief="Allow users to create their own role after boosting the guild",
        example=",boosterroles enable",
    )
    @commands.bot_has_permissions(administrator=True)
    @commands.has_permissions(manage_guild=True)
    @check_guild_boost_level()
    async def br_enable(self, ctx: Context) -> discord.Message:
        if await self.bot.db.fetchval(
            "SELECT status FROM br_status WHERE guild_id = $1", ctx.guild.id
        ):
            return await ctx.embed(
                "**Booster roles** are already **enabled** in this guild", "warned"
            )

        await self.bot.db.execute(
            "INSERT INTO br_status (guild_id, status) VALUES ($1, $2)",
            ctx.guild.id,
            True,
        )
        return await ctx.embed("**Enabled booster roles** for this guild", "approved")

    @br.command(
        name="disable",
        aliases=("reset",),
        brief="Disable booster roles in the guild",
        example=",boosterroles disable",
    )
    @commands.bot_has_permissions(administrator=True)
    @commands.has_permissions(manage_guild=True)
    async def br_disable(self, ctx: Context) -> discord.Message:
        if not await self.bot.db.fetchval(
            "SELECT status FROM br_status WHERE guild_id = $1", ctx.guild.id
        ):
            return await ctx.embed(
                "**Booster roles** are already **disabled** in this guild", "warned"
            )

        await self.bot.db.execute(
            "DELETE FROM br_status WHERE guild_id = $1", ctx.guild.id
        )
        return await ctx.embed("**Disabled booster roles** for this guild", "approved")

    async def cleanup_boostroles(self, ctx: Context):
        for r in await self.bot.db.fetch(
            """SELECT role_id FROM br WHERE guild_id = $1""", ctx.guild.id
        ):
            if role := ctx.guild.get_role(r):
                try:
                    await role.delete(reason="boost role cleanup")
                except Exception:
                    await self.bot.db.execute(
                        """DELETE FROM br WHERE guild_id = $1 AND role_id = $2""",
                        ctx.guild.id,
                        r,
                    )
        await self.bot.db.execute(
            """DELETE FROM br WHERE guild_id = $1""", ctx.guild.id
        )
        return True

    async def edit_position(self, ctx: Context, role: discord.Role):
        if base := await self.bot.db.fetchval(
            """SELECT role_id FROM br_base WHERE guild_id = $1""", ctx.guild.id
        ):
            if base_role := ctx.guild.get_role(base):

                booster_roles = await self.bot.db.fetch(
                    """SELECT role_id FROM br WHERE guild_id = $1""", ctx.guild.id
                )

                valid_roles = []
                for r_id in booster_roles:
                    if r := ctx.guild.get_role(r_id):
                        valid_roles.append(r)

                valid_roles.sort(key=lambda x: x.position, reverse=True)

                await role.edit(position=base_role.position - 1)

                for i, r in enumerate(valid_roles):
                    if r.id != role.id:
                        try:
                            await r.edit(position=base_role.position - (i + 2))
                        except discord.HTTPException:
                            continue
            else:
                return await ctx.embed(
                    f"**Base role** must have been **deleted**: `{base}`", "warned"
                )
        else:
            return await ctx.embed("**No base role** set for this guild", "warned")

    async def bulk_edit_boostroles(self, ctx: Context):
        for r in await self.bot.db.fetch(
            """SELECT role_id FROM br WHERE guild_id = $1""", ctx.guild.id
        ):
            if role := ctx.guild.get_role(r):
                await self.edit_position(ctx, role)

    @br.command(
        name="base",
        aliases=["baserole"],
        brief="Set a base role for booster roles to be created under",
        example=",boosterroles base @members",
    )
    @commands.bot_has_permissions(administrator=True)
    @commands.has_permissions(manage_roles=True)
    async def br_base(self, ctx: Context, *, role: Role = None):
        if role is None:
            await self.bot.db.execute(
                """DELETE FROM br_status WHERE guild_id = $1""", ctx.guild.id
            )
            await self.bot.db.execute(
                """DELETE FROM br_base WHERE guild_id = $1""", ctx.guild.id
            )
            await self.cleanup_boostroles(ctx)
            return await ctx.embed(
                "disabled `boost roles` and cleaned up the roles", "approved"
            )
        else:
            role = role[0]
            if role.position >= ctx.guild.me.top_role.position:
                return await ctx.embed(
                    "**Base role** is **higher** then my **top role**", "warned"
                )
            if not await self.bot.db.fetch(
                """SELECT * FROM br_status WHERE guild_id = $1""", ctx.guild.id
            ):
                await self.bot.db.execute(
                    """INSERT INTO br_status (guild_id, status) VALUES($1,$2)""",
                    ctx.guild.id,
                    True,
                )
            await self.bot.db.execute(
                """INSERT INTO br_base (guild_id, role_id) VALUES($1,$2) ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id""",
                ctx.guild.id,
                role.id,
            )
            roles = await self.bot.db.fetch(
                """SELECT role_id FROM br WHERE guild_id = $1""", ctx.guild.id
            )
            if roles:
                msg = await ctx.embed(
                    "changing all boost role positions... this may take a while...",
                    "approved",
                )
                for rr in roles:
                    if ctx.guild.get_role(rr):
                        await role.edit(position=role.position - 1)
                await msg.edit(
                    embed=discord.Embed(
                        description=f"**Base role** set to <@&{role.id}>",
                        
                    )
                )
            else:
                return await ctx.embed(
                    f"**Base role** set to {role.mention}", "approved"
                )

    @br.command(
        "sync",
        brief="Sync all existing booster roles to the correct position based on the base role",
        example=",boosterroles sync",
    )
    @commands.bot_has_permissions(administrator=True)
    @commands.has_permissions(manage_roles=True)
    async def br_sync(self, ctx: Context) -> discord.Message:
        if not await self.bot.db.fetchval(
            """SELECT role_id FROM br_base WHERE guild_id = $1""", ctx.guild.id
        ):
            return await ctx.embed(
                "**No base role** set for this guild. Set one with `,br base @role` first",
                "warned",
            )

        roles = await self.bot.db.fetch(
            """SELECT role_id FROM br WHERE guild_id = $1""", ctx.guild.id
        )
        if not roles:
            return await ctx.embed("No booster roles found to sync", "warned")

        msg = await ctx.embed(
            "Syncing all booster roles... this may take a while...", "approved"
        )
        synced = 0
        failed = 0

        valid_roles = []
        for role_id in roles:
            if role := ctx.guild.get_role(role_id):
                valid_roles.append(role)

        if not valid_roles:
            return await msg.edit(
                embed=discord.Embed(
                    description="No valid booster roles found to sync",
                    
                )
            )

        valid_roles.sort(key=lambda x: x.position, reverse=True)

        base_role_id = await self.bot.db.fetchval(
            """SELECT role_id FROM br_base WHERE guild_id = $1""", ctx.guild.id
        )
        base_role = ctx.guild.get_role(base_role_id)

        for i, role in enumerate(valid_roles):
            try:
                await role.edit(position=base_role.position - (i + 1))
                synced += 1
            except discord.HTTPException:
                failed += 1
                continue

        await msg.edit(
            embed=discord.Embed(
                description=f"**Synced** {synced} booster roles{f' ({failed} failed)' if failed > 0 else ''}",
                
            )
        )

    @br.command(
        "share",
        aliases=("give",),
        brief="Share your booster role with another user or remove it if they already have it",
        example=",boosterroles share @66adam",
    )
    @commands.bot_has_permissions(administrator=True)
    @check_br_status()
    async def br_share(self, ctx: Context, *, member: discord.Member):
        if data := await self.bot.db.fetchval(
            """SELECT role_id FROM br WHERE user_id = $1 AND guild_id = $2""",
            ctx.author.id,
            ctx.guild.id,
        ):
            if role := ctx.guild.get_role(data):
                if role in member.roles:
                    await member.remove_roles(role)
                    action = "removed from"
                else:
                    await member.add_roles(role)
                    action = "shared with"
            else:
                return await ctx.embed("your booster role **doesn't exist**", "warned")
        else:
            return await ctx.embed("your booster role **doesn't exist**", "warned")

        return await ctx.embed(
            f"**Booster role** has been **{action}** {member.mention}", "approved"
        )

    @br.command(
        "create",
        aliases=("make",),
        brief="Create a custom booster role for boosting the guild",
        example=",boosterroles create topG",
    )
    @check_br_status()
    @commands.bot_has_permissions(administrator=True)
    async def br_create(
        self, ctx: Context, *, name: str, color: int = 3447003
    ) -> discord.Message:
        try:
            await self.check_rate_limit(ctx, f"create:{ctx.author.id}", 3, 300)

            author: discord.Member = typing.cast(discord.Member, ctx.author)
            rolename = f"{name}"

            if len(rolename) < 2 or len(rolename) > 100:
                return await ctx.embed(
                    "Role name must be between 2 and 100 characters", "denied"
                )

            exists = await self.bot.db.fetchval(
                "SELECT role_id FROM br WHERE user_id = $1 AND guild_id = $2",
                author.id,
                ctx.guild.id,
            )
            if exists:
                return await ctx.embed(
                    "You already have a **booster role** in this guild", "warned"
                )

            role_limit = await self.get_role_limit(ctx)
            if len(ctx.guild.roles) >= role_limit:
                raise RoleLimitError(role_limit)

            role = await ctx.guild.create_role(
                name=rolename,
                color=discord.Color(color),
                hoist=True,
                mentionable=True,
                reason=f"Booster role created by {author}",
            )

            if base := await self.bot.db.fetchval(
                """SELECT role_id FROM br_base WHERE guild_id = $1""", ctx.guild.id
            ):
                if base_role := ctx.guild.get_role(base):
                    await role.edit(position=base_role.position - 1)

            await author.add_roles(role, reason="BoosterRole")
            await self.bot.db.execute(
                "INSERT INTO br (user_id, role_id, guild_id) VALUES ($1, $2, $3)",
                author.id,
                role.id,
                ctx.guild.id,
            )

            embed = discord.Embed(
                title="Booster Role Created",
                description=f"**Created** your own **booster role**: {role.mention}",
                
            )
            embed.add_field(name="Color", value=f"`{hex(color)}`", inline=True)
            embed.add_field(name="Position", value=f"`{role.position}`", inline=True)
            embed.set_footer(text=f"ID: {role.id}")

            return await ctx.send(embed=embed)

        except RateLimitError as e:
            return await ctx.embed(str(e), "denied")
        except RoleLimitError as e:
            return await ctx.embed(str(e), "denied")
        except discord.HTTPException as e:
            logger.error(f"Failed to create booster role: {e}", exc_info=True)
            return await ctx.embed("Failed to create booster role", "denied")

    @br.command(
        "delete",
        aliases=("remove", "del", "rm"),
        brief="Remove your custom booster role from the guild",
        example=",boosterroles remove",
    )
    @commands.bot_has_permissions(administrator=True)
    @check_br_status()
    async def br_delete(self, ctx: Context) -> Optional[discord.Message]:
        author: discord.Member = typing.cast(discord.Member, ctx.author)
        if not (
            role := await self.bot.db.fetchval(
                "SELECT role_id FROM br WHERE user_id = $1 AND guild_id = $2",
                author.id,
                ctx.guild.id,
            )
        ):
            return await ctx.embed(
                "You **do not** have a **booster role** in this guild", "warned"
            )

        role = ctx.guild.get_role(int(role))
        if role:
            await role.delete(reason="BoosterRole")
            await self.bot.db.execute(
                "DELETE FROM br WHERE user_id = $1 AND guild_id = $2",
                author.id,
                ctx.guild.id,
            )
            return await ctx.embed(
                "**Deleted** your **booster role** in this guild", "approved"
            )

    @br.command(
        "rename",
        aliases=("name",),
        brief="Rename your custom booster role in this guild",
        example=",boosterroles rename littleG",
    )
    @commands.bot_has_permissions(administrator=True)
    @check_br_status()
    async def br_rename(self, ctx: Context, name: str) -> Optional[discord.Message]:
        author: discord.Member = typing.cast(discord.Member, ctx.author)
        if not (
            role := await self.bot.db.fetchval(
                "SELECT role_id FROM br WHERE user_id = $1 AND guild_id = $2",
                author.id,
                ctx.guild.id,
            )
        ):
            return await ctx.embed(
                "You **do not** have a **booster role** in this guild", "warned"
            )

        role = ctx.guild.get_role(int(role))
        if role:
            await role.edit(
                name=f"{name}",
                reason="BoosterRole",
            )
            return await ctx.embed(
                f"**Renamed** your **booster role** to {role.mention}", "approved"
            )

    @br.command(
        "color",
        aliases=("colour",),
        brief="Change the color or recolor your custom booster role in this guild",
        example=",boosterroles color #ffffff",
    )
    @commands.bot_has_permissions(administrator=True)
    @check_br_status()
    async def br_color(
        self, ctx: Context, *, color: ColorConverter
    ) -> Optional[discord.Message]:
        try:
            await self.check_rate_limit(ctx, f"color:{ctx.author.id}", 5, 60)

            author: discord.Member = typing.cast(discord.Member, ctx.author)
            if not (
                role := await self.bot.db.fetchval(
                    "SELECT role_id FROM br WHERE user_id = $1 AND guild_id = $2",
                    author.id,
                    ctx.guild.id,
                )
            ):
                return await ctx.embed(
                    "You **do not** have a **booster role** in this guild", "warned"
                )

            role = ctx.guild.get_role(int(role))
            if role:
                old_color = role.color
                await role.edit(color=color, reason="BoosterRole")

                embed = discord.Embed(
                    title="Booster Role Color Changed",
                    description=f"**Changed** your **booster role's color**",
                    
                )
                embed.add_field(name="Old Color", value=f"`{old_color}`", inline=True)
                embed.add_field(name="New Color", value=f"`{color}`", inline=True)
                embed.set_footer(text=f"ID: {role.id}")

                return await ctx.send(embed=embed)

        except RateLimitError as e:
            return await ctx.embed(str(e), "denied")
        except discord.HTTPException as e:
            logger.error(f"Failed to change role color: {e}", exc_info=True)
            return await ctx.embed("Failed to change role color", "denied")

    async def get_icon(
        self, url: Optional[Union[discord.Emoji, discord.PartialEmoji, str]] = None
    ):
        if url is None:
            return None
        if isinstance(url, discord.Emoji):
            return await url.read()
        elif isinstance(url, discord.PartialEmoji):
            return await url.read()
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.read()
            return data

    @br.command(
        "icon",
        aliases=("icn",),
        brief="Set or Change the current icon you have set for your custom booster role in this guild",
        example=",boosterroles icon :blunt:",
    )
    @commands.bot_has_permissions(administrator=True)
    @check_br_status()
    async def br_icon(
        self,
        ctx,
        *,
        icon: Optional[Union[discord.Emoji, discord.PartialEmoji, str]] = None,
    ) -> discord.Message:
        if isinstance(icon, str):
            if not icon.startswith("https://"):
                return await ctx.embed("that is not a valid URL", "warned")
        author = ctx.author
        if not (
            role := await self.bot.db.fetchval(
                "SELECT role_id FROM br WHERE user_id = $1 AND guild_id = $2",
                author.id,
                ctx.guild.id,
            )
        ):
            return await ctx.embed(
                "You **do not** have a **booster role** in this guild", "warned"
            )
        role = ctx.guild.get_role(role)
        icon = await self.get_icon(icon)
        if icon is None:
            if not role.display_icon:
                return await ctx.embed(
                    "Your **booster role** does not have an **icon** set", "warned"
                )
        await role.edit(display_icon=icon, reason="BoosterRole")
        if icon:
            return await ctx.embed("**Booster role icon changed**", "approved")
        else:
            return await ctx.embed(
                "**Booster roles icon** has been **reset** for this guild", "approved"
            )

    @br.command(
        "list",
        aliases=("all",),
        brief="List all the booster roles in this guild",
        example=",boosterroles list",
    )
    @commands.has_permissions(manage_guild=True)
    async def br_list(self, ctx: Context):
        rows = []
        data = await self.bot.db.fetch(
            """SELECT user_id, role_id FROM br WHERE guild_id = $1""", ctx.guild.id
        )
        if not data:
            return await ctx.embed("No booster roles found in this guild.", "warned")

        for i, record in enumerate(data, start=1):
            user = ctx.guild.get_member(record["user_id"])
            role = ctx.guild.get_role(record["role_id"])
            if user and role:
                rows.append(f"`{i}` {role.mention} - Owned by {user.mention}")
            elif role:
                rows.append(f"`{i}` {role.mention} - Owner not found")
            else:
                rows.append(f"`{i}` Role not found - User ID: {record['user_id']}")

        embed = discord.Embed(
            title=f"Booster Roles in {ctx.guild.name}",
            color=Colors().information
        )
        await Paginator(ctx, rows, embed=embed, per_page=10).start()

    @br.command(
        "include",
        aliases=("bypass",),
        brief="Include a user in the booster role list",
        example=",boosterroles include @role @user",
    )
    @commands.bot_has_permissions(administrator=True)
    @commands.has_permissions(manage_roles=True)
    async def br_include(self, ctx: Context, role: Role, user: discord.Member):
        """
        Include a user in the booster role list by associating them with a specific role.
        """
        role = role[0]
        if not ctx.guild.get_role(role.id):
            return await ctx.embed(
                "The specified role does not exist in this guild.", "warned"
            )

        if await self.bot.db.fetchval(
            """SELECT role_id FROM br WHERE role_id = $1 AND guild_id = $2""",
            role.id,
            ctx.guild.id,
        ):
            return await ctx.embed(
                "This role is already associated with a booster.", "warned"
            )

        await self.bot.db.execute(
            """INSERT INTO br (user_id, role_id, guild_id) VALUES ($1, $2, $3)""",
            user.id,
            role.id,
            ctx.guild.id,
        )
        return await ctx.embed(
            f"**Included** {user.mention} as the owner of the booster role {role.mention}.",
            "approved",
        )


async def setup(bot):
    await bot.add_cog(boosterrole(bot))
