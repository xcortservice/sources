from __future__ import annotations

import socket
import psutil
import asyncio

from typing import Optional, Any, ClassVar
from types import TracebackType
from logging import getLogger
from distributed import (
    Client as DefaultClient,
    LocalCluster,
    Security,
)

log = getLogger("greed/dask")


DASK_SCHEDULER_URL = "tcp://localhost:8786"


def find_free_port() -> int:
    """
    Find a free port to use for the dashboard.
    """
    with socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    ) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


class DaskClient(DefaultClient):
    """
    Greed Dask client for distributed computing operations
    Provides connection management and common distributed operations
    """
    _instance: ClassVar[Optional["DaskClient"]] = None
    _local_cluster: ClassVar[Optional[LocalCluster]] = None
    _scheduler_port: ClassVar[int] = 8786
    _dashboard_port: ClassVar[int] = 8787
    _closing: ClassVar[bool] = False

    async def __aenter__(self) -> "DaskClient":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        log.info("Shutting down the Dask client.")
        await self.close()

    @classmethod
    async def from_url(
        cls,
        url: str = "tcp://localhost:8786",
        name: str = "greed",
        timeout: int = 30,
        security: Optional[Security] = None,
        **kwargs,
    ) -> "DaskClient":
        """
        Creates or retrieves a shared Dask client instance
        """
        if cls._instance is not None:
            if cls._instance.status == "running":
                log.info("Reusing existing running client")
                return cls._instance
            else:
                log.warning(f"Client in state: {cls._instance.status}, creating new client")
                await cls._instance.close()
                cls._instance = None

        try:
            client = cls(
                address=url,
                name=name,
                timeout=timeout,
                security=security,
                asynchronous=True,
                **kwargs,
            )
            cls._instance = client
            return client
        except Exception:
            if cls._local_cluster is None:
                log.info("No existing Dask scheduler found, starting local cluster")
                cls._local_cluster = LocalCluster(
                    n_workers=12,
                    threads_per_worker=4,
                    memory_limit="4GB",
                    scheduler_port=cls._scheduler_port,
                    dashboard_address=f"127.0.0.1:{cls._dashboard_port}",
                    asynchronous=True,
                    processes=True,
                )
                await cls._local_cluster

            client = cls(
                address=cls._local_cluster,
                name=name,
                timeout=timeout,
                security=security,
                asynchronous=True,
                **kwargs,
            )
            cls._instance = client
            log.info(f"Started Dask cluster on port {cls._scheduler_port}")
            return client

    async def close(self) -> None:
        """Ensure proper cleanup of Dask resources"""
        if self._closing:
            return

        self._closing = True
        try:
            if self._instance is not None:
                try:
                    await DefaultClient.close(self)
                except Exception as e:
                    log.error(f"Error closing DefaultClient: {e}")
                self._instance = None

            if self._local_cluster is not None:
                try:
                    await self._local_cluster.close(timeout=5)
                except Exception as e:
                    log.error(f"Error closing local cluster: {e}")
                self._local_cluster = None
                log.info("Shut down local Dask cluster")

            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

        except Exception as e:
            log.error(f"Error closing Dask client: {e}")
        finally:
            self._closing = False

    async def submit_task(
        self,
        func: Any,
        *args,
        key: Optional[str] = None,
        workers: Optional[list[str]] = None,
        **kwargs,
    ):
        """
        Submits a task to the Dask cluster
        """
        future = await self.submit(
            func,
            *args,
            key=key,
            workers=workers,
            **kwargs,
        )
        return await future

    async def map_tasks(
        self,
        func: Any,
        *iterables,
        key: Optional[str] = None,
        workers: Optional[list[str]] = None,
        **kwargs,
    ):
        """
        Maps multiple tasks across the Dask cluster
        """
        futures = await self.map(
            func,
            *iterables,
            key=key,
            workers=workers,
            **kwargs,
        )
        return await self.gather(futures)

    async def get_cluster_status(self):
        """
        Returns current cluster status including workers and memory
        """
        return {
            "workers": len(
                self.scheduler_info()["workers"]
            ),
            "memory": self.scheduler_info()["memory"],
            "processing": len(self.processing()),
            "pending": len(self.pending),
        }


async def get_dask(name: str = "greed") -> DaskClient:
    """
    Get an existing Dask client instance or create a new one.
    
    Args:
        name: The name of the client
        
    Returns:
        A Dask client instance
    """
    if DaskClient._instance is not None:
        return DaskClient._instance
        
    return await start_dask(name)


async def start_dask(
    name: str = "greed",
    url: str = DASK_SCHEDULER_URL,
    dashboard_address: str = "0.0.0.0:8787",
    n_workers: int = 12,
    threads_per_worker: int = 4,
    memory_limit: str = "4GB",
    **kwargs,
) -> DaskClient:
    """
    Start a new Dask client with the specified configuration.
    """
    if DaskClient._instance is not None:
        return DaskClient._instance

    log.info("Starting Dask client initialization")
    
    if DaskClient._local_cluster is None:
        log.info("Starting local Dask cluster")
        DaskClient._local_cluster = LocalCluster(
            n_workers=n_workers,
            threads_per_worker=threads_per_worker,
            memory_limit=memory_limit,
            scheduler_port=DaskClient._scheduler_port,
            dashboard_address=dashboard_address,
            asynchronous=True,
            processes=True,
        )
        await DaskClient._local_cluster
        log.info(f"Local cluster started with dashboard at {dashboard_address}")

    client = await DaskClient.from_url(
        url=url,
        name=name,
        **kwargs,
    )
    
    try:
        log.info("Waiting for workers to connect...")
        await asyncio.sleep(1)
        await client.wait_for_workers(1)
        log.info("Workers connected successfully")
        return client
    except Exception as e:
        log.error(f"Error waiting for workers: {e}")
        if not client._closing:
            await client.close()
        raise


__all__ = ("DaskClient", "get_dask", "start_dask")
