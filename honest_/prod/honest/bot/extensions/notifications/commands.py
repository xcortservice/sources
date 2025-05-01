from discord import (Client, Embed, File, Guild, Member, TextChannel, Thread,
                     User)
from discord.ext.commands import (Cog, CommandError, EmbedConverter, command,
                                  group, has_permissions)
from system.classes.database import Record
from system.patch.context import Context


class Notifications(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @group(
        name="stickymessage",
        aliases=["sticky", "stickymsg"],
        description="add a message that will be sent every time someone messages",
        invoke_without_command=True,
    )
    async def stickymessage(self, ctx: Context):
        return await ctx.send_help(ctx.command)

    @stickymessage.command(
        name="add",
        description="add a sticky message",
        aliases=["msg", "create", "a", "c", "m"],
        example=",stickymessage add #text {embed}{description: you are black}",
    )
    @has_permissions(manage_guild=True)
    async def stickymessage_add(
        self, ctx: Context, channel: TextChannel, *, code: EmbedConverter
    ):
        await self.bot.db.execute(
            """INSERT INTO sticky_message (guild_id, channel_id, code) VALUES($1, $2, $3) ON CONFLICT(guild_id, channel_id) DO UPDATE SET code = excluded.code""",
            ctx.guild.id,
            channel.id,
            code,
        )
        return await ctx.success(f"Added a **sticky message** to {channel.mention}")

    @stickymessage.command(
        name="remove",
        aliases=["rem", "r", "delete", "d", "del"],
        description="remove a stickymessage that was previously set",
        example=",stickymessage remove #text",
    )
    @has_permissions(manage_guild=True)
    async def stickymessage_remove(self, ctx: Context, *, channel: TextChannel):
        await self.bot.db.execute(
            "DELETE FROM sticky_message WHERE guild_id = $1 AND channel_id = $2" "",
            ctx.guild.id,
            channel.id,
        )
        return await ctx.success(f"Removed a **sticky message** from {channel.mention}")

    @stickymessage.command(
        name="list",
        aliases=["view", "show", "ls"],
        description="view all sticky messages",
    )
    @has_permissions(manage_guild=True)
    async def stickymessage_list(self, ctx: Context):
        if not (
            messages := await self.bot.db.fetch(
                "SELECT channel_id, code FROM sticky_message WHERE guild_id = $1" "",
                ctx.guild.id,
            )
        ):
            raise CommandError("No **sticky messages** found")

        def get_message(row: Record) -> str:
            if channel := ctx.guild.get_channel(row["channel_id"]):
                return f"[**{channel.name}**]({channel.jump_url})"
            else:
                return f"[**Unknown**](https://discord.com/channels/{ctx.guild.id}/{row['channel_id']})"

        return await ctx.paginate(
            Embed(title="Sticky Messages").set_author(
                name=str(ctx.author), icon_url=ctx.author.display_avatar.url
            ),
            [
                f"`{i}` {get_message(message)}"
                for i, message in enumerate(messages, start=1)
            ],
        )

    @stickymessage.command(
        name="reset",
        aliases=["clear", "cl", "rs"],
        description="remove all sticky messages in the server",
    )
    @has_permissions(administrator=True)
    async def stickymessage_reset(self, ctx: Context):
        await self.bot.db.execute(
            "DELETE FROM sticky_message WHERE guild_id = $1" "", ctx.guild.id
        )
        return await ctx.success("Removed all **sticky messages** from this server")


async def setup(bot: Client):
    await bot.add_cog(Notifications(bot))
