from __future__ import annotations

import asyncio
import os
import logging
import psutil
from contextlib import suppress
from functools import partial
from typing import Awaitable, Callable, TypeVar, TYPE_CHECKING, Dict, Any, Optional, List, Union
from typing_extensions import ParamSpec

import distributed.client
from tornado import gen
import dill
import cloudpickle
import logging
from io import BytesIO

logger = logging.getLogger("greed/tools/offload")

from greed.shared.clients.dask import DaskClient, get_dask, start_dask

if TYPE_CHECKING:
    from greed.framework import Greed

P = ParamSpec("P")
T = TypeVar("T")

DEBUG = os.getenv("DEBUG", "OFF").lower() in ("on", "true", "1", "yes")
MAX_RETRIES = int(os.getenv("DASK_MAX_RETRIES", "3"))
BACKOFF_FACTOR = float(os.getenv("DASK_BACKOFF_FACTOR", "1.5"))
MAX_CONCURRENT_TASKS = int(os.getenv("DASK_MAX_CONCURRENT_TASKS", "32"))
DASK_TIMEOUT = int(os.getenv("DASK_TIMEOUT", "30"))
DASK_SCHEDULER_URL = os.getenv("DASK_SCHEDULER_URL", "tcp://localhost:8786")
DASK_SCHEDULER_FILE = os.getenv("DASK_SCHEDULER_FILE", "scheduler.json")
DASK_WORKERS = int(os.getenv("DASK_WORKERS", "12"))
DASK_THREADS_PER_WORKER = int(os.getenv("DASK_THREADS_PER_WORKER", "4"))

_task_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

_dask_clients: Dict[str, DaskClient] = {}

@gen.coroutine
def cascade_future(future: distributed.Future, cf_future: asyncio.Future):
    """
    Cascade a Dask future to an asyncio future.
    
    Args:
        future: The Dask future
        cf_future: The asyncio future to set
    """
    result = yield future._result(raiseit=False)
    status = future.status
    
    if status == "finished":
        with suppress(asyncio.InvalidStateError):
            cf_future.set_result(result)
    elif status == "cancelled":
        cf_future.cancel()
        cf_future.set_running_or_notify_cancel()
    else:
        try:
            typ, exc, tb = result
            raise exc.with_traceback(tb)
        except BaseException as exc:
            cf_future.set_exception(exc)


def cf_callback(future):
    """
    Callback for Dask futures to handle cancellation.
    
    Args:
        future: The Dask future
    """
    cf_future = future._cf_future
    if cf_future.cancelled() and future.status != "cancelled":
        asyncio.ensure_future(future.cancel())


async def get_or_create_dask_client(name: str = "greed") -> DaskClient:
    """
    Get an existing Dask client or create a new one.
    
    Args:
        name: The name of the client
        
    Returns:
        A Dask client instance
    """
    logger.info(f"Attempting to get/create Dask client '{name}'")
    
    if name in _dask_clients:
        client = _dask_clients[name]
        logger.info(f"Found existing client with status: {client.status}")
        
        if client.status == "running":
            logger.info("Reusing existing running client")
            return client
        else:
            logger.warning(f"Client in state: {client.status}, creating new client")
            del _dask_clients[name]
    
    try:
        port_in_use = any(conn.laddr.port == 8787 for conn in psutil.net_connections())
        logger.info(f"Port 8787 status: {'in use' if port_in_use else 'available'}")
        
        if port_in_use:
            logger.info("Connecting to existing scheduler...")
            client = await start_dask(name, DASK_SCHEDULER_FILE)
            _dask_clients[name] = client
            return client
        else:
            logger.info("Starting new Dask client...")
            client = await start_dask(
                name, 
                DASK_SCHEDULER_URL,
                dashboard_address="0.0.0.0:8787",
                n_workers=DASK_WORKERS,
                threads_per_worker=DASK_THREADS_PER_WORKER,
                direct_to_workers=True
            )
            _dask_clients[name] = client
            return client
    except Exception as e:
        logger.error(f"Failed to create Dask client: {e}")
        raise


async def _submit_to_dask(
    func: Callable,
    args: tuple,
    kwargs: dict,
    loop: asyncio.AbstractEventLoop,
    name: str = "greed",
    retries: int = MAX_RETRIES,
    backoff_factor: float = BACKOFF_FACTOR,
) -> Any:
    """
    Submit a task to Dask with retry logic.
    """
    for attempt in range(retries):
        try:
            dask = await get_or_create_dask_client(name)
            
            if dask.status != "running":
                if attempt == retries - 1:
                    raise RuntimeError(f"Dask client is in {dask.status} state")
                await asyncio.sleep(backoff_factor ** attempt)
                continue
                
            logger.info(f"Original args types: {[type(arg) for arg in args]}")
            
            processed_args = []
            for i, arg in enumerate(args):
                logger.info(f"Processing arg {i}: type={type(arg)}")
                if isinstance(arg, BytesIO):
                    processed_args.append(arg.getvalue())
                elif isinstance(arg, list):
                    processed_args.append([str(x) if not isinstance(x, (str, int, float, bool)) else x for x in arg])
                else:
                    processed_args.append(arg)
                    
            processed_kwargs = {}
            for key, value in kwargs.items():
                logger.info(f"Processing kwarg {key}: type={type(value)}")
                if isinstance(value, BytesIO):
                    processed_kwargs[key] = value.getvalue()
                elif isinstance(value, dict):
                    processed_kwargs[key] = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v for k, v in value.items()}
                else:
                    processed_kwargs[key] = value
                
            logger.info(f"Processed args types: {[type(arg) for arg in processed_args]}")
            
            serialized_func = cloudpickle.dumps(func)
            serialized_args = dill.dumps(tuple(processed_args))
            serialized_kwargs = dill.dumps(processed_kwargs)
            
            def execute_task():
                try:
                    logger.info("Starting task execution")
                    f = cloudpickle.loads(serialized_func)
                    a = dill.loads(serialized_args)
                    k = dill.loads(serialized_kwargs)
                    
                    logger.info(f"Deserialized args types: {[type(arg) for arg in a]}")
                    
                    processed_a = []
                    for i, arg in enumerate(a):
                        logger.info(f"Processing deserialized arg {i}: type={type(arg)}")
                        if isinstance(arg, bytes):
                            processed_a.append(BytesIO(arg))
                        elif isinstance(arg, list):
                            processed_a.append(arg)
                        else:
                            processed_a.append(arg)
                            
                    processed_k = {}
                    for key, value in k.items():
                        logger.info(f"Processing deserialized kwarg {key}: type={type(value)}")
                        if isinstance(value, bytes):
                            processed_k[key] = BytesIO(value)
                        elif isinstance(value, dict):
                            processed_k[key] = value
                        else:
                            processed_k[key] = value
                    
                    logger.info(f"Final processed args types: {[type(arg) for arg in processed_a]}")
                    
                    result = f(*processed_a, **processed_k)
                    logger.info("Task completed successfully")
                    return result
                except Exception as e:
                    logger.error(f"Error in execute_task: {str(e)}", exc_info=True)
                    raise
            
            future = dask.submit(execute_task, pure=False)
            logger.info("Task submitted to Dask")
            
            try:
                result = await asyncio.get_event_loop().run_in_executor(None, future.result, DASK_TIMEOUT)
                logger.info("Task result retrieved")
                return result
            except asyncio.TimeoutError:
                logger.error("Task timed out")
                future.cancel()
                raise TimeoutError(f"Task timed out after {DASK_TIMEOUT} seconds")
            except Exception as e:
                logger.error(f"Error waiting for task result: {str(e)}", exc_info=True)
                raise
            
        except Exception as e:
            logger.error(f"Error in _submit_to_dask: {str(e)}", exc_info=True)
            if attempt == retries - 1:
                raise
            await asyncio.sleep(backoff_factor ** attempt)
            continue


def submit_coroutine(func: Callable, *args, **kwargs):
    """
    Submit a coroutine to run on a Dask worker.
    
    Args:
        func: The coroutine function to execute
        *args: Positional arguments for the coroutine
        **kwargs: Keyword arguments for the coroutine
        
    Returns:
        The result of the coroutine
    """
    worker_loop: asyncio.AbstractEventLoop = distributed.get_worker().loop.asyncio_loop
    task = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), loop=worker_loop)
    return task.result()


def offloaded(
    f: Callable[P, T],
    batch_size: Optional[int] = None,
    name: str = "greed",
    timeout: int = DASK_TIMEOUT,
) -> Callable[P, Awaitable[T]]:
    """
    Offload a function to run on Dask cluster with optional batching support.
    
    Args:
        f: Function to offload
        batch_size: Optional batch size for processing multiple items at once
        name: Name of the Dask client to use
        timeout: Timeout for the Dask client
        
    Returns:
        An async function that offloads the computation to Dask
    """
    async def offloaded_task(*a: P.args, **ka: P.kwargs) -> T:
        loop = asyncio.get_running_loop()
        
        if batch_size and a and isinstance(a[-1], (list, tuple)):
            data = a[-1]
            other_args = a[:-1]
            
            batches = [
                data[i : i + batch_size] for i in range(0, len(data), batch_size)
            ]
            
            async def process_batch(batch):
                args = (*other_args, batch)
                async with _task_semaphore:
                    return await _submit_to_dask(f, args, ka, loop, name)
            
            results = await asyncio.gather(*[process_batch(batch) for batch in batches])
            return [item for batch in results for item in batch]
        
        async with _task_semaphore:
            return await _submit_to_dask(f, a, ka, loop, name)
    
    return offloaded_task


async def offload_many(
    func: Callable,
    items: List[Any],
    batch_size: Optional[int] = None,
    name: str = "greed",
    timeout: int = DASK_TIMEOUT,
) -> List[Any]:
    """
    Offload multiple items to Dask for processing.
    
    Args:
        func: Function to apply to each item
        items: List of items to process
        batch_size: Optional batch size for processing
        name: Name of the Dask client to use
        timeout: Timeout for the Dask client
        
    Returns:
        List of processed items
    """
    if not items:
        return []
        
    if batch_size is None:
        async def process_item(item):
            return await offloaded(func)(item)
            
        return await asyncio.gather(*[process_item(item) for item in items])
    else:
        return await offloaded(func, batch_size=batch_size)(items)


def clear_dask_clients():
    """
    Clear all Dask client instances.
    """
    _dask_clients.clear() 