import sys
import logging

from asyncio import run
from cashews import cache
from os import getenv, environ

from discord.utils import setup_logging

from greed.framework import Greed
from greed.framework.cluster import Cluster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("greed.log"),
    ],
)

logger = logging.getLogger("greed")

cache.setup(getenv("REDIS_URL", "redis://localhost:6379/5"))
# cache.setup("mem://")

environ["JISHAKU_NO_UNDERSCORE"] = "True"
environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
environ["JISHAKU_HIDE"] = "True"
environ["JISHAKU_FORCE_PAGINATOR"] = "True"
environ["JISHAKU_RETAIN"] = "True"


async def startup() -> None:
    """
    Starts either a cluster manager or individual bot instance
    """
    try:
        logger.info("Starting Greed...")

        if len(sys.argv) > 1:
            cluster_id = int(sys.argv[1])
            logger.info(f"Starting cluster {cluster_id}")

            async with Greed(cluster_id=cluster_id) as bot:
                setup_logging()
                await bot.start()
        else:
            logger.info("Starting cluster manager")
            cluster = Cluster()
            await cluster.start()
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)

    except KeyboardInterrupt:
        logger.info("Shutdown requested")


if __name__ == "__main__":
    try:
        run(startup())

    except KeyboardInterrupt:
        logger.info("Shutdown complete")
