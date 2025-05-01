from __future__ import annotations

from asyncio import (AbstractEventLoop, CancelledError, Future, LifoQueue,
                     Lock, Task, ensure_future, gather, get_running_loop)
from collections.abc import Coroutine
from contextlib import suppress
from typing import AnyStr as String
from typing import Dict, Union

from loguru import logger

try:
    from asyncio import timeout
except ImportError:
    try:
        from async_timeout import timeout
    except ImportError:
        raise ImportError(
            "Neither asyncio.timeout nor async_timeout.timeout is available."
        )


class TaskMap:
    def __init__(self, name: str) -> None:
        self.lock = Lock()
        self.name = name
        self.tasks = {}

    @classmethod
    def create(cls, name: str) -> TaskMap:
        return TaskMap(name)


class Guard:
    def __init__(self) -> None:
        self.tasks: Dict[str, Future] = {}
        self.tasks: LifoQueue = LifoQueue()
        self.control: Lock = Lock()
        self.num_cancelled: int = 0
        self.num_failed: int = 0
        self.tm_locks: Dict[str, Lock] = {}
        self.loop: AbstractEventLoop = get_running_loop()

    def __str__(self: Guard) -> str:
        return f"<Guard task-count={len(self.tasks)} failed={self.num_failed} cancelled={self.num_cancelled}>"

    def incr_f(self: Guard) -> None:
        self.num_failed += 1

    def incr_c(self: Guard) -> None:
        self.num_cancelled += 1

    async def recycler(self: Guard) -> None:
        while True:
            task: Future = await self.tasks.get()
            if not task.cancelled():
                task.exception()

    async def get_lock(self: Guard, name: str) -> Lock:
        async with self.control:
            if not self.tm_locks.get(name):
                self.tm_locks[name] = Lock()
            return self.tm_locks[name]

    def loop_del(self: Guard, key: str) -> None:
        with suppress(KeyError, AttributeError):
            del self.tasks[key]

    def remove_result(self: Guard, task: Future) -> None:
        try:
            if not task.cancelled():
                with logger.catch(exclude=CancelledError, onerror=self.incr_f):
                    task.result()
            else:
                self.incr_c()
        finally:
            self.loop.call_soon(self.loop_del, task.key)

    async def spawn(
        self: Guard, task: Union[Coroutine, Future, Task], identity: String
    ) -> Union[Future, Task, Coroutine]:
        identity = str(identity)
        async with await self.get_lock(identity):
            factory = ensure_future(task, loop=self.loop)
            factory.key = f"{identity}-{id(task)}"
            self.tasks[factory.key] = factory
            self.tasks[factory.key].add_done_callback(self.remove_result)
            return factory

    async def shutdown(self: Guard, identity: String) -> int:
        identity = str(identity)
        async with await self.get_lock(identity):
            tasks = [
                t.cancel()
                for key, t in self.tasks.items()
                if key.startswith(str(identity))
            ]
            if tasks:
                async with timeout(10):
                    await gather(*tasks, return_exceptions=True)
            return len(tasks)
