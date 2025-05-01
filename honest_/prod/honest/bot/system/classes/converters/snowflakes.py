import re
import unicodedata
from typing import Optional, Union

import discord
from data.variables import _ID_REGEX, DISCORD_ID, DISCORD_USER_MENTION
from discord.ext import commands
from fast_string_match import closest_match_distance as cmd
from system.patch.context import Context


class UserConverter(commands.UserConverter):
    async def convert(self, ctx: Context, argument: str):
        member = None
        argument = str(argument)
        if match := DISCORD_ID.match(argument):
            member = ctx.bot.get_user(int(match.group(1)))
            if member is None:
                member = await ctx.bot.fetch_user(int(match.group(1)))
        elif match := DISCORD_USER_MENTION.match(argument):
            member = ctx.bot.get_user(int(match.group(1)))
            if member is None:
                member = await ctx.bot.fetch_user(int(match.group(1)))
        else:
            member = (
                discord.utils.find(
                    lambda m: m.name.lower() == argument.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: argument.lower() in m.name.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: m.name.lower().startswith(argument.lower()),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: m.display_name.lower() == argument.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: argument.lower() in m.display_name.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: m.display_name.lower().startswith(argument.lower()),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: str(m).lower() == argument.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: argument.lower() in str(m).lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: str(m).lower().startswith(argument.lower()),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(
                            m.discriminator
                            if not isinstance(m, discord.ThreadMember)
                            else 0
                        ),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: m.name.lower() == argument.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: argument.lower() in m.name.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: m.name.lower().startswith(argument.lower()),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: m.display_name.lower() == argument.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: argument.lower() in m.display_name.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: m.display_name.lower().startswith(argument.lower()),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: str(m).lower() == argument.lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: argument.lower() in str(m).lower(),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
                or discord.utils.find(
                    lambda m: str(m).lower().startswith(argument.lower()),
                    sorted(
                        ctx.bot.users,
                        key=lambda m: int(m.discriminator),
                        reverse=False,
                    ),
                )
            )
        if not member:
            raise commands.UserNotFound(argument)
        return member


class MemberConverter(commands.MemberConverter):
    async def convert(
        self, ctx: Context, arg: Union[int, str]
    ) -> Optional[discord.Member]:
        _id = _ID_REGEX.match(arg) or re.match(r"<@!?([0-9]{15,20})>$", arg)
        if _id is not None:
            _id = int(_id.group(1))
            if member := ctx.guild.get_member(_id):
                return member
            else:
                raise commands.MemberNotFound(arg)

        # Create a lookup dictionary in one line
        member_lookup = {
            name: member.id
            for member in ctx.guild.members
            for name in filter(
                None,
                [member.global_name, member.nick, member.display_name, member.name],
            )
        }

        # Perform lookup with cmd() function
        final_match = cmd(arg, list(member_lookup.keys()))
        if final_match:
            return ctx.guild.get_member(member_lookup[final_match])

        # Raise exception if no member found
        raise commands.MemberNotFound(arg)


class Emoji(commands.EmojiConverter):
    async def convert(
        self, ctx: "Context", argument: str
    ) -> Optional[Union[discord.Emoji, discord.PartialEmoji]]:
        try:
            return await super().convert_(ctx, argument)

        except commands.EmojiNotFound:
            try:
                unicodedata.name(argument)
            except Exception:
                try:
                    unicodedata.name(argument[0])
                except Exception:
                    raise commands.EmojiNotFound(argument)

            return argument


class SafeMemberConverter(commands.Converter):
    async def convert(self, ctx: Context, argument: str):
        author = ctx.author
        try:
            member = await MemberConverter().convert(ctx, argument)
        except Exception:
            try:
                member = await UserConverter().convert(ctx, argument)
            except Exception as e:
                raise e
        if isinstance(member, discord.User):
            return member

        elif ctx.guild.me.top_role <= member.top_role:
            raise commands.CommandError(
                f"The role of {member.mention} is **higher than wocks**"
            )
        elif ctx.author.id == member.id and not author:
            raise commands.CommandError(
                "You **can not execute** that command on **yourself**"
            )
        elif ctx.author.id == member.id and author:
            return member
        elif ctx.author.id == ctx.guild.owner_id:
            return member
        elif member.id == ctx.guild.owner_id:
            raise commands.CommandError(
                "**Can not execute** that command on the **server owner**"
            )
        elif ctx.author.top_role.is_default():
            raise commands.CommandError(
                "You are **missing permissions to use this command**"
            )
        elif ctx.author.top_role == member.top_role:
            raise commands.CommandError("You have the **same role** as that user")
        elif ctx.author.top_role < member.top_role:
            raise commands.CommandError(
                "You **do not** have a role **higher** than that user"
            )
        else:
            return member
