import asyncio, discord_ios
from system.honest import Honest

bot = Honest()

async def main():
    try:
        await bot.run()
    except KeyboardInterrupt:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())