from typing import Union, Optional, List
from discord import Member, Embed, File
from greed.framework import Greed
from greed.framework.discord import Context
from greed.framework.tools.offload import offloaded
from datetime import datetime, timezone, timedelta
from tools import timeit
import asyncio
import logging
from greed.shared.config import Colors

logger = logging.getLogger("greed/plugins/economy/chart")


def format_large(num: Union[int, float]) -> str:
    if str(num).startswith("-"):
        symbol = "-"
    else:
        symbol = ""
    num = int(float(str(num).replace("-", "")))
    suffixes = [
        "",
        "K",
        "M",
        "B",
        "T",
        "Qa",
        "Qi",
        "Sx",
        "Sp",
        "Oc",
        "No",
        "Dc",
        "Ud",
        "Dd",
        "Td",
        "Qad",
        "Qid",
        "Sxd",
        "Spd",
        "Ocd",
        "Nod",
        "Vg",
        "Uv",
        "Dv",
        "Tv",
        "Qav",
        "Qiv",
        "Sxv",
        "Spv",
        "Ocv",
        "Nov",
        "Tg",
        "Utg",
        "Dtg",
        "Ttg",
        "Qatg",
        "Qitg",
        "Sxtg",
        "Sptg",
        "Octg",
        "Notg",
        "Qng",
    ]
    num = int(float(num))
    num_str = str(num)
    if "." in num_str:
        num_str = num_str[: num_str.index(".")]
    num_len = len(num_str)

    if num_len <= 3:
        return f"{symbol}{num_str}"

    suffix_index = (num_len - 1) // 3

    if suffix_index >= len(suffixes):
        return f"{num} is too large to format."

    scaled_num = int(num_str[: num_len - suffix_index * 3])

    return f"{symbol}{scaled_num}{suffixes[suffix_index]}"


class EconomyCharts:
    def __init__(self, bot: Greed):
        self.bot = bot
        self._chart_cache = {}
        self._cache_lock = asyncio.Lock()

    async def _get_cached_chart(self, user_id: int, color: str) -> Optional[File]:
        async with self._cache_lock:
            cache_key = f"{user_id}_{color}"
            if cache_key in self._chart_cache:
                cached_time, file = self._chart_cache[cache_key]
                if datetime.now(timezone.utc) - cached_time < timedelta(minutes=5):
                    return file
                del self._chart_cache[cache_key]
            return None

    async def _cache_chart(self, user_id: int, color: str, file: File):
        async with self._cache_lock:
            self._chart_cache[f"{user_id}_{color}"] = (datetime.now(timezone.utc), file)

    async def _get_transactions(self, member: Member) -> List[tuple]:
        try:
            transactions = await self.bot.db.fetch(
                """
                SELECT amount, timestamp 
                FROM economy_transactions 
                WHERE user_id = $1 
                AND timestamp > NOW() - INTERVAL '24 hours'
                ORDER BY timestamp
                """,
                member.id,
            )
            if not transactions:
                return [
                    (0, datetime.now(timezone.utc) - timedelta(hours=i))
                    for i in range(24, 0, -1)
                ]
            return transactions
        except Exception as e:
            logger.error(f"Error fetching transactions for user {member.id}: {e}")
            return []

    async def _process_transactions(
        self, transactions: List[tuple]
    ) -> tuple[List[str], List[float]]:
        hourly_data = {}
        for amount, timestamp in transactions:
            hour = timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_data[hour] = hourly_data.get(hour, 0) + float(amount)

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        for i in range(24):
            hour = now - timedelta(hours=i)
            if hour not in hourly_data:
                hourly_data[hour] = 0

        sorted_hours = sorted(hourly_data.keys())
        return [hour.strftime("%H:00") for hour in sorted_hours], [
            hourly_data[hour] for hour in sorted_hours
        ]

    async def _get_user_stats(self, member: Member) -> tuple:
        try:
            balance, bank, wins, total = await self.bot.db.fetchrow(
                """SELECT balance, bank, wins, total FROM economy WHERE user_id = $1""",
                member.id,
            )
            rank = await self.bot.db.fetchval(
                """SELECT COUNT(*) + 1 FROM economy WHERE earnings > (SELECT earnings FROM economy WHERE user_id = $1)""",
                member.id,
            )
            return balance, bank, wins, total, rank
        except Exception as e:
            logger.error(f"Error fetching stats for user {member.id}: {e}")
            return 0, 0, 0, 0, 0

    def format_large_number(self, number_str: Union[float, str, int]):
        number_str = str(number_str)
        if number_str.startswith("-"):
            sign = "-"
            number_str = number_str[1:]
        else:
            sign = ""
        reversed_number = number_str[::-1]
        chunks = [reversed_number[i : i + 3] for i in range(0, len(reversed_number), 3)]
        formatted_number = ",".join(chunks)[::-1]
        if ",." in formatted_number:
            formatted_number = formatted_number.replace(",.", ".")
        return sign + formatted_number

    def format_int(self, n: Union[float, str, int], up_down: Optional[bool] = True):
        emoji = None
        bal = None
        if isinstance(n, float):
            n = "{:.2f}".format(n)
        if isinstance(n, str):
            if "." in n:
                try:
                    amount, decimal = n.split(".")
                    n = f"{amount}.{decimal[:2]}"
                except Exception:
                    n = f"{n.split('.')[0]}.00"
        n_ = str(n).split(".")[0]
        if len(str(n_)) >= 10:
            if str(n_).startswith("-"):
                emoji = "<:1F53B_color:1302403663821668523>"
            else:
                emoji = "<:1F53A_color:1302403786718838904>"
            if up_down:
                return f"{emoji} {format_large(float(n))}"
            else:
                return str(format_large(float(n)))
        n = str(n).replace("-0.00", "0")
        n = self.format_large_number(n)
        if n.startswith("-"):
            emoji = "<:1F53B_color:1302403663821668523>"
        else:
            emoji = "<:1F53A_color:1302403786718838904>"
        if up_down:
            return f"{emoji} {n}"
        else:
            return str(n)

    def get_percent(self, amount: int, total: int):
        if not amount > 0:
            return "0"
        else:
            return int(amount / total * 100)

    async def chart_earnings(self, ctx: Context, member: Member):
        try:
            color = (
                await self.bot.db.fetchval(
                    """SELECT color FROM graph_color WHERE user_id = $1""",
                    ctx.author.id,
                )
                or "lime"
            )

            cached_file = await self._get_cached_chart(member.id, color)
            if cached_file:
                return await self._send_chart_response(
                    ctx, member, cached_file, [], 0, 0, 0, 0, 0
                )

            transactions = await self._get_transactions(member)
            labels, profits = await self._process_transactions(transactions)
            balance, bank, wins, total, rank = await self._get_user_stats(member)

            @offloaded
            def make_chart(
                labels: List[str], profits: List[float], color: Optional[str] = None
            ):
                from io import BytesIO
                import plotly.graph_objects as go
                import pandas as pd

                buffer = BytesIO()
                df = pd.DataFrame({"Earnings": profits})

                fig = go.Figure(
                    data=go.Scatter(x=df.index, y=df["Earnings"], mode="lines")
                )
                fig.update_traces(line=dict(color=color))

                fig.update_layout(
                    title="Earnings Graph",
                    xaxis_title="TimeFrame",
                    yaxis_title="Price",
                    width=1200,
                    plot_bgcolor="black",
                    paper_bgcolor="black",
                    margin=dict(l=100, r=100, t=100, b=100),
                    yaxis=dict(showgrid=False),
                    font=dict(color="white"),
                    xaxis=dict(
                        tickmode="array",
                        tickvals=df.index,
                        tickangle=0,
                        showgrid=False,
                        ticktext=labels,
                    ),
                )
                fig.update_layout(
                    {
                        "plot_bgcolor": "rgba(0, 0, 0, 0)",
                        "paper_bgcolor": "rgba(0, 0, 0, 0)",
                    }
                )
                fig.write_image(buffer, format="png")
                buffer.seek(0)
                return buffer

            async with timeit():
                chart = await make_chart(labels, profits, color)
            file = File(fp=chart, filename="chart.png")
            await self._cache_chart(member.id, color, file)

            return await self._send_chart_response(
                ctx, member, file, profits, balance, bank, wins, total, rank
            )
        except Exception as e:
            logger.error(f"Error generating chart for user {member.id}: {e}")
            return await ctx.send("An error occurred while generating the chart.")

    async def _send_chart_response(
        self,
        ctx: Context,
        member: Member,
        file: File,
        profits: List[float],
        balance: float,
        bank: float,
        wins: int,
        total: int,
        rank: int,
    ):
        percentage = self.get_percent(int(wins), int(total))
        return await ctx.send(
            embed=Embed(title=f"{member.name}'s profit", color=Colors().information)
            .set_image(url=f"attachment://{file.filename}")
            .add_field(
                name="Earnings", value=self.format_int(sum(profits)), inline=True
            )
            .add_field(
                name="Recent Earned", value=self.format_int(profits[-1]), inline=True
            )
            .add_field(name="W/L", value=f"{percentage}%", inline=True)
            .add_field(
                name="Balance", value=self.format_int(float(balance)), inline=True
            )
            .add_field(name="Bank", value=self.format_int(float(bank)), inline=True)
            .add_field(
                name="Rank", value=f"{rank if rank > 0 else 'unranked'}", inline=True
            ),
            file=file,
        )
