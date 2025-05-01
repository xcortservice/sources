import asyncio
import logging
import math
import multiprocessing
import os
import signal
import sys
from typing import Optional, Dict, Set
from time import perf_counter

logger = logging.getLogger("greed/cluster")


class ShardCoordinator:
    def __init__(self):
        self.connected_shards: Set[int] = set()
        self.lock = asyncio.Lock()
        self.start_time = perf_counter()

    async def wait_for_shard(self, shard_id: int, max_wait: float = 5.0) -> None:
        """
        Wait for a shard to be ready to connect, ensuring no conflicts with other shards.
        """
        async with self.lock:
            if shard_id in self.connected_shards:
                return

            elapsed = perf_counter() - self.start_time
            delay = min(0.1 * shard_id, 0.5)  
            
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
            
            self.connected_shards.add(shard_id)


def run_cluster(cluster_id: int, shard_ids: list[int], total_shards: int):
    """
    Run a single cluster in its own process.
    """
    from greed.framework import Greed

    def handle_signal(signum, frame):
        logger.info(f"Cluster {cluster_id} received shutdown signal")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        bot = Greed(
            cluster_id=cluster_id,
            shard_ids=shard_ids,
            shard_count=total_shards
        )
        asyncio.run(bot.start())
    except Exception as e:
        logger.error(f"Error in cluster {cluster_id}: {e}")
        sys.exit(1)


class Cluster:
    """
    Manages multiple bot instances across system processes
    """

    def __init__(self):
        self.total_shards = 4
        self.cluster_count = 2
        self.shards_per_cluster = math.ceil(
            self.total_shards / self.cluster_count
        )
        self.processes = []
        self.dask_client = None
        self.coordinator = ShardCoordinator()

    async def start(self) -> None:
        """
        Starts all bot clusters in separate processes
        """
        logger.info(
            f"Starting {self.cluster_count} clusters ({self.total_shards} shards) across {multiprocessing.cpu_count()} CPUs..."
        )

        try:
            from greed.shared.clients.dask import start_dask
            self.dask_client = await start_dask()
            logger.info("Dask client initialized")

            process_tasks = []
            for cluster_id in range(self.cluster_count):
                shard_ids = self.get_shard_ids(cluster_id)
                logger.info(
                    f"Preparing Cluster #{cluster_id} (Shards {shard_ids})"
                )

                process = multiprocessing.Process(
                    target=run_cluster,
                    args=(cluster_id, shard_ids, self.total_shards),
                    daemon=True
                )
                process.start()
                process_tasks.append(process)
                self.processes.append(process)
                
                await asyncio.sleep(0.1)

            while any(p.is_alive() for p in self.processes):
                for process in self.processes:
                    if not process.is_alive():
                        logger.error(f"Cluster process {process.pid} died unexpectedly")
                        await self.cleanup()
                        sys.exit(1)
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """
        Cleanup all processes and resources.
        """
        logger.info("Cleaning up clusters...")
        
        if self.dask_client:
            await self.dask_client.close()
            self.dask_client = None

        for process in self.processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()

    def get_shard_ids(self, cluster_id: int) -> list[int]:
        """
        Get shard IDs for this cluster.
        """
        start_shard = cluster_id * self.shards_per_cluster
        end_shard = min(
            (cluster_id + 1) * self.shards_per_cluster,
            self.total_shards,
        )
        return list(range(start_shard, end_shard))
