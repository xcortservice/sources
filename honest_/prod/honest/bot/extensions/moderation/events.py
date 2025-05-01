from datetime import datetime, timedelta
from typing import Any, Literal, Optional, Union

from discord import (Client, Embed, File, Guild, Member, TextChannel, Thread,
                     User)
from discord.abc import GuildChannel
from discord.ext.commands import (Cog, CommandError, command, group,
                                  has_permissions)
from system.patch.context import Context


class ModerationEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    def target_type(
        self, target: Union[User, Member, TextChannel, GuildChannel, Literal["all"]]
    ):
        if isinstance(target, (User, Member)):
            return "**User:**"
        elif isinstance(target, (TextChannel, GuildChannel)):
            return "**Channel:**"
        elif target == "all":
            return ""

    def target_string(
        self, target: Union[User, Member, TextChannel, GuildChannel, Literal["all"]]
    ):
        if target == "all":
            return "**All Channels**"
        elif isinstance(target, (User, Member)):
            return f"{str(target)} (`{target.id}`)"
        else:
            return f"{target.name} (`{target.id}`)"

    @Cog.listener("on_moderation_case")
    async def on_new_case(
        self,
        ctx: Context,
        target: Union[User, Member, TextChannel, GuildChannel, Literal["all"]],
        action: str,
        reason: str,
        **kwargs: Any,
    ):
        case_id = (
            await self.bot.db.fetchval(
                """SELECT count(*) FROM cases WHERE guild_id = $1""", ctx.guild.id
            )
            or 0
        )
        message_created_at = datetime.now()
        if not (
            config := await self.bot.db.fetchval(
                """SELECT channel_id FROM moderation WHERE guild_id = $1""",
                ctx.guild.id,
            )
        ):
            message_id = None
        else:
            if not (channel := self.bot.get_channel(config)):
                message_id = None
            else:

                embed = Embed(
                    title="Information",
                    description=f"**Case #{case_id + 1}** | {ctx.command.qualified_name.title()}\n{self.target_type(target)} {self.target_string(target)}\n**Moderator:** {str(ctx.author)} (`{ctx.author.id}`)\n**Reason:** {reason}",
                    timestamp=datetime.now(),
                )
                embed.set_author(
                    name="Modlog Entry",
                    icon_url=(
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else ctx.bot.user.display_avatar.url
                    ),
                )
                message = await channel.send(embed=embed)
                message_id = message.id
        await self.bot.db.execute(
            "INSERT INTO cases (guild_id, case_id, case_type, message_id, moderator_id, target_id, moderator, target, reason, timestamp)"
            " VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
            ctx.guild.id,
            case_id + 1,
            action.lower(),
            message_id,
            ctx.author.id,
            target.id,
            str(ctx.author),
            str(target),
            reason,
            message_created_at,
        )


async def setup(bot: Client):
    await bot.add_cog(ModerationEvents(bot))
