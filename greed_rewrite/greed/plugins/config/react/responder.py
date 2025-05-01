from discord.ext.commands import group, Cog, has_permissions
from discord import Embed

from greed.framework import Context, Greed
from greed.framework.discord.command import Argument
from greed.framework.pagination import Paginator

from greed.shared.config import Colors


class ButtonRoles(Cog):
    """
    A class to manage button roles in Discord.
    """

    def __init__(self, bot: Greed):
        self.bot = bot

    @group(
        name="autoresponder",
        aliases=["ar", "autoresponse"],
        invoke_without_command=True,
    )
    @has_permissions(manage_messages=True)
    async def autoresponder(self, ctx: Context):
        """
        Manage automated responses to specific phrases.

        Use subcommands to add, remove, or list auto-responses.
        """
        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command)

    @autoresponder.command(
        name="add",
        aliases=["a", "create"],
        brief="Create a new auto-response",
        example=",autoresponder add hello Hi there! --strict --reply",
    )
    @has_permissions(manage_messages=True)
    async def autoresponder_add(self, ctx: Context, *, arg: Argument):
        """
        Create an auto-responder for a given trigger phrase.

        Flags:
        --strict: Enable strict matching (exact phrase match)
        --reply: Make the bot reply to the trigger message
        """
        trigger = arg.first
        response = arg.second

        strict_flag = False
        reply_flag = False

        flags = []
        if "--strict" in ctx.message.content:
            strict_flag = True
            flags.append("strict matching")
        if "--reply" in ctx.message.content:
            reply_flag = True
            flags.append("with reply")

        response = response.replace("--strict", "").replace("--reply", "").strip()

        if ctx.guild.id in self.bot.cache.autoresponders:
            if trigger in self.bot.cache.autoresponders[ctx.guild.id]:
                self.bot.cache.autoresponders[ctx.guild.id][trigger] = {
                    "response": response,
                    "strict": strict_flag,
                    "reply": reply_flag,
                }
            else:
                self.bot.cache.autoresponders[ctx.guild.id][trigger] = {
                    "response": response,
                    "strict": strict_flag,
                    "reply": reply_flag,
                }
        else:
            self.bot.cache.autoresponders[ctx.guild.id] = {
                trigger: {
                    "response": response,
                    "strict": strict_flag,
                    "reply": reply_flag,
                }
            }

        await self.bot.db.execute(
            """INSERT INTO autoresponder (guild_id, trig, response, strict, reply) 
               VALUES($1, $2, $3, $4, $5) 
               ON CONFLICT (guild_id, trig) 
               DO UPDATE SET response = excluded.response, 
                            strict = excluded.strict,
                            reply = excluded.reply""",
            ctx.guild.id,
            trigger,
            response,
            strict_flag,
            reply_flag,
        )

        flag_text = f" ({', '.join(flags)})" if flags else ""
        await ctx.embed(
            message=f"**Auto-responder** ``{trigger}``{flag_text} applied",
            message_type="approved",
        )

    @autoresponder.command(
        name="remove",
        aliases=["del", "d", "r", "rem"],
        brief="Remove an existing auto-response",
        example=",autoresponder remove hello",
    )
    @has_permissions(manage_messages=True)
    async def autoresponder_remove(self, ctx: Context, *, trigger: str):
        """
        Remove an auto-responder for a given trigger phrase.
        """
        if ctx.guild.id not in self.bot.cache.autoresponders:
            return await ctx.embed(
                message="Auto-Response has not been setup!",
                message_type="warned",
            )

        if trigger not in self.bot.cache.autoresponders[ctx.guild.id]:
            return await ctx.embed(
                message=f"No auto-responder found with trigger **{trigger}**",
                message_type="warned",
            )

        await self.bot.db.execute(
            """
            DELETE FROM autoresponder 
            WHERE guild_id = $1 
            AND trig = $2
            """,
            ctx.guild.id,
            trigger,
        )
        self.bot.cache.autoresponders[ctx.guild.id].pop(trigger)
        return await ctx.embed(
            message=f"Auto-responder with the trigger ``{trigger}`` removed",
            message_type="approved",
        )

    @autoresponder.command(
        name="clear",
        aliases=["cl"],
        brief="Remove all auto-responses",
        example=",autoresponder clear",
    )
    @has_permissions(manage_messages=True)
    async def autoresponder_clear(self, ctx: Context):
        """
        Remove all auto-responders from the server.
        """
        await self.bot.db.execute(
            """DELETE FROM autoresponder WHERE guild_id = $1""", ctx.guild.id
        )
        try:
            self.bot.cache.autoresponders.pop(ctx.guild.id)
        except Exception:
            pass
        return await ctx.embed("**Cleared** all **auto-responders**", "approved")

    @autoresponder.command(
        name="list",
        aliases=["l", "show"],
        brief="Show all auto-responses",
        example=",autoresponder list",
    )
    @has_permissions(manage_messages=True)
    async def autoresponder_list(self, ctx: Context):
        """
        List all auto-responders in the server.

        Shows trigger phrases, responses, and any flags (strict/reply).
        """
        rows = []
        for trig, response, strict, reply in await self.bot.db.fetch(
            """
            SELECT trig, response, strict, reply 
            FROM autoresponder 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        ):
            flag_info = []
            if strict:
                flag_info.append("strict")
            if reply:
                flag_info.append("reply")

            flag_text = f" [{', '.join(flag_info)}]" if flag_info else ""
            rows.append(f"`{trig}`{flag_text} - `{response}`")

        if len(rows) > 0:
            embed = Embed(
                title=f"{ctx.guild.name}'s auto-responders",
                url=self.bot.domain,
                color=Colors().information,
            )
            await Paginator(ctx, rows, embed=embed, per_page=10).start()
        else:
            return await ctx.embed("**Server** has no **auto-responders setup**", "warned")
