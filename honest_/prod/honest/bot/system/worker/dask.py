import asyncio
from typing import Callable

import distributed
import psutil

GLOBAL_DASK = {}


def get_dask() -> distributed.Client:
    return GLOBAL_DASK.get("client")


async def sstart_dask(bot, address: str) -> distributed.Client:
    client = await distributed.Client(
        distributed.LocalCluster(
            dashboard_address=address,
            asynchronous=True,
            processes=True,
            threads_per_worker=2,
            n_workers=5,
        ),
        direct_to_workers=True,
        asynchronous=True,
        name=bot.cluster_name,
    )
    GLOBAL_DASK["client"] = client
    return client


async def start_dask(bot, address: str) -> distributed.Client:
    from loguru import logger

    # Check if port 8787 is already in use
    port_in_use = any(conn.laddr.port == 8787 for conn in psutil.net_connections())
    if not port_in_use:
        logger.info("port not in use starting scheduler")
    client = await distributed.Client(
        distributed.LocalCluster(
            dashboard_address=address,
            asynchronous=True,
            threads_per_worker=2,
            n_workers=5,
        ),
        direct_to_workers=True,
        asynchronous=True,
    )

    logger.info("Dask successfully sinked and loaded!")
    GLOBAL_DASK["client"] = client
    return client


def submit_coroutine(func: Callable, *args, **kwargs):
    worker_loop: asyncio.AbstractEventLoop = distributed.get_worker().loop.asyncio_loop
    task = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), loop=worker_loop)
    return task.result()
