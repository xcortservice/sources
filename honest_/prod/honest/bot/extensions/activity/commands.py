from asyncio import Lock, gather, sleep
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, Union

import msgspec
from discord import (ActivityType, Client, ClientUser, Embed, File, Guild,
                     Member, User)
from discord.ext import tasks
from discord.ext.commands import Cog, CommandError, command, group
from loguru import logger
from system.classes.builtins import get_error
from system.patch.context import Context
from system.worker import offloaded
from tools import thread


def Percent(first: int, second: int, integer: bool = True) -> Union[float, int]:
    try:
        percentage = first / second * 100
        if integer is True:
            return round(float(percentage), 2)
        return percentage
    except Exception:
        return 0


def convert_seconds(duration_seconds: int) -> str:
    duration = timedelta(seconds=duration_seconds)
    minutes, seconds = divmod(duration.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    duration_text = ""
    if duration.days > 0:
        if duration.days == 1:
            duration_text += f"{duration.days} day, "
        else:
            duration_text += f"{duration.days} days, "
    if hours > 0:
        if hours == 1:
            duration_text += f"{hours} hour, "
        else:
            duration_text += f"{hours} hours, "
    if minutes > 0:
        if minutes == 1:
            duration_text += f"{minutes} minute, "
        else:
            duration_text += f"{minutes} minutes, "
    if seconds > 0:
        if seconds == 1:
            duration_text += f"{seconds} second"
        else:
            duration_text += f"{seconds} seconds"
    if duration_text == "":
        duration_text = "0 seconds, "
    return duration_text.rstrip(", ")


@thread
def GenerateChart(dataset: list, names: list):
    from io import BytesIO

    import plotly.express as px

    px.defaults.width = 829  # image width
    px.defaults.height = 625  # image height
    fig = px.pie(
        values=dataset,
        hole=0.68,
        names=names,
        color=names,
        color_discrete_map={
            names[0]: "#43b581",
            names[1]: "#faa61a",
            names[2]: "#f04747",
            names[3]: "#747f8d",
            names[4]: "#583594",
        },
    )
    fig.update_traces(textinfo="none")
    fig.update_layout(
        paper_bgcolor="rgba(0, 0, 255, 0)",
        legend_font_color="#FFFFFF",
        legend_font_size=24,
        legend_tracegroupgap=15,
    )
    buffer = BytesIO()
    fig.write_image(buffer, format="png")
    buffer.seek(0)
    return buffer.getvalue()


class Screentime(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self.locks = defaultdict(Lock)
        self.data = {}

    async def cog_load(self):
        data = await self.bot.redis.get("screentime_data")
        self.data = msgspec.json.decode(data) if data else {}

        for user in self.bot.users:
            if user.id != self.bot.user.id and str(user.id) not in self.data:
                self.data[str(user.id)] = int(datetime.now().timestamp())

        await self.bot.db.execute(
            """
			CREATE TABLE IF NOT EXISTS screentime (
				user_id BIGINT PRIMARY KEY,
				online BIGINT DEFAULT 1,
				offline BIGINT DEFAULT 1,
				idle BIGINT DEFAULT 1,
				dnd BIGINT DEFAULT 1,
				streaming BIGINT DEFAULT 1
			);
		"""
        )

    def update_members(self):
        for user in self.bot.users:
            user_id = str(user.id)
            if user_id not in self.data:
                self.data[user_id] = int(datetime.now().timestamp())

    def get_member(self, user_id: int):
        user = self.bot.get_user(user_id)
        return (
            next((m for m in user.mutual_guilds if m.get_member(user.id)), None)
            if user
            else None
        )

    async def write_usage(
        self, before: Union[Member, User], after: Union[Member, User]
    ):
        async with self.locks[before.id]:
            with suppress(KeyError):
                if isinstance(before, ClientUser):
                    return

                before_member = self.get_member(before.id)
                if not before_member:
                    self.data.pop(str(after.id), None)
                    return

                elapsed = int(datetime.now().timestamp()) - self.data[str(before.id)]
                status_durations = {
                    "online": 0,
                    "offline": 0,
                    "idle": 0,
                    "dnd": 0,
                    "streaming": 0,
                }
                if before.activity and before.activity.type == ActivityType.streaming:
                    status_durations["streaming"] += elapsed
                elif str(before.status) in status_durations:
                    status_durations[str(before.status)] += elapsed

                await self.bot.db.execute(
                    """
					INSERT INTO screentime (user_id, online, offline, idle, dnd, streaming)
					VALUES ($1, $2, $3, $4, $5, $6)
					ON CONFLICT (user_id)
					DO UPDATE SET
						online = screentime.online + EXCLUDED.online,
						offline = screentime.offline + EXCLUDED.offline,
						idle = screentime.idle + EXCLUDED.idle,
						dnd = screentime.dnd + EXCLUDED.dnd,
						streaming = screentime.streaming + EXCLUDED.streaming;
				""",
                    before.id,
                    *status_durations.values(),
                )

                self.data[str(before.id)] = int(datetime.now().timestamp())

    @Cog.listener()
    async def on_presence_update(self, before: Member, after: Member):
        if before.id != self.bot.user.id:
            await self.write_usage(before, after)

    @group(name="screentime", aliases=["screen", "st"], invoke_without_command=True)
    async def screentime(self, ctx: Context, *, member: Optional[Member] = None):
        member = member or ctx.author
        end = "'" if str(member).endswith("s") else "'s"
        data = await self.bot.db.fetchrow(
            "SELECT online, idle, dnd, offline, streaming FROM screentime WHERE user_id = $1",
            member.id,
        )

        if not data:
            raise CommandError("you haven't had any presence changes recorded yet")
        async with self.locks[member.id]:
            dataset = [
                int(data.online),
                int(data.idle),
                int(data.dnd),
                int(data.offline),
                int(data.streaming),
            ]
            now = int(datetime.now().timestamp())

            if str(member.id) in self.data:
                status = str(member.status)
                if status in ["online", "idle", "dnd"]:
                    dataset[["online", "idle", "dnd"].index(status)] += (
                        now - self.data[str(member.id)]
                    )
                elif member.activity and member.activity.type == ActivityType.streaming:
                    dataset[4] += now - self.data[str(member.id)]
                else:
                    dataset[3] += now - self.data[str(member.id)]

            dataset = [
                max(d, 60) for d in dataset
            ]  # Ensure no duration is less than 60 seconds
            online = dataset[0]
            idle = dataset[1]
            dnd = dataset[2]
            offline = dataset[3]
            streaming = dataset[4]
            dataset = [online, idle, dnd, offline, streaming]
            total_ = sum(dataset)
            names = [
                f"Online<br>{convert_seconds(online)}<br>{Percent(dataset[0], total_)}%",
                f"Idle<br>{convert_seconds(idle)}<br>{Percent(dataset[1], total_)}%",
                f"DND<br>{convert_seconds(dnd)}<br>{Percent(dataset[2], total_, True)}%",
                f"Offline<br>{convert_seconds(offline)}<br>{Percent(dataset[3], total_)}%",
                f"Streaming<br>{convert_seconds(streaming)}<br>{Percent(dataset[4], total_)}%",
            ]
            chart = await GenerateChart(dataset, names)
            file = File(fp=BytesIO(chart), filename="chart.png")
            await ctx.send(
                file=file,
                embed=Embed(
                    title=f"""{'your' if member == ctx.author else f"{str(member)}{end}"} activity""",
                    url=member.url,
                )
                .set_image(url="attachment://chart.png")
                .set_author(
                    name=str(ctx.author), icon_url=ctx.author.display_avatar.url
                ),
            )
        return

    @screentime.command(name="clear", aliases=["cl"])
    async def screentime_clear(self, ctx: Context):
        await self.bot.db.execute(
            "DELETE FROM screentime WHERE user_id = $1", ctx.author.id
        )
        await ctx.success("your screentime data has been **CLEARED**")

    @tasks.loop(hours=1)
    async def update_screentime(self):
        if not self.data:
            await sleep(3)

        self.update_members()
        self.data.pop(str(self.bot.user.id), None)

        async def update_user(u: int):
            user = self.bot.get_user(u)
            if user:
                await self.write_usage(user, user)

        try:
            await gather(*[update_user(int(u)) for u in self.data])
        except Exception as e:
            logger.info(f"update_screentime loop raised: {get_error(e)}")

        await self.bot.redis.set("screentime_data", msgspec.json.encode(self.data))


async def setup(bot: Client):
    await bot.add_cog(Screentime(bot))
