import asyncio
from core import Botfucker


async def main():
    bot = Botfucker()

    async with bot:
        await bot.start()


if __name__ == "__main__":
        asyncio.run(main())
