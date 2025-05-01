from __future__ import annotations

import time

from contextlib import suppress
from datetime import timedelta
from hashlib import sha1
from json import JSONDecodeError, dumps, loads
from logging import getLogger
from types import TracebackType
from typing import Any, List, Literal, Optional, Union
from xxhash import xxh32_hexdigest

from redis.asyncio import Redis as DefaultRedis
from redis.asyncio.connection import BlockingConnectionPool
from redis.asyncio.lock import Lock
from redis.backoff import EqualJitterBackoff
from redis.exceptions import NoScriptError
from redis.retry import Retry
from redis.typing import (
    AbsExpiryT,
    EncodableT,
    ExpiryT,
    FieldT,
    KeyT,
)

log = getLogger("greed/redis")


REDIS_URL = f"redis://localhost:6379"

INCREMENT_SCRIPT = b"""
    local current
    current = tonumber(redis.call("incrby", KEYS[1], ARGV[2]))
    if current == tonumber(ARGV[2]) then
        redis.call("expire", KEYS[1], ARGV[1])
    end
    return current
"""


class Redis(DefaultRedis):
    INCREMENT_SCRIPT_HASH = sha1(
        INCREMENT_SCRIPT
    ).hexdigest()

    async def __aenter__(self) -> "Redis":
        return await self.initialize()

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ):
        log.info("Shutting down the Redis client.")
        await self.close()

    @classmethod
    async def from_url(
        cls,
        url: str = REDIS_URL,
        name: str = "greed",
        attempts: int = 100,
        timeout: int = 120,
        **kwargs,
    ) -> "Redis":
        retry = Retry(
            backoff=EqualJitterBackoff(3, 1),
            retries=attempts,
        )
        connection_pool = BlockingConnectionPool.from_url(
            url,
            timeout=timeout,
            max_connections=100,
            retry=retry,
            decode_responses=True,
            **kwargs,
        )

        client = cls(
            connection_pool=connection_pool,
            auto_close_connection_pool=True,
            retry_on_timeout=True,
            # health_check_interval=5,
            client_name=name,
        )

        try:
            start = time.perf_counter()
            await client.ping()
            latency = time.perf_counter() - start

            log.debug(
                "Established Redis client with %sμs latency.",
                int(latency * 1000000),
            )
        except Exception as e:
            log.error(
                f"Failed to establish Redis connection: {e}"
            )
            raise

        return client

    async def set(
        self,
        name: KeyT,
        value: EncodableT | dict | list | Any,
        ex: Union[ExpiryT, None] = None,
        px: Union[ExpiryT, None] = None,
        nx: bool = False,
        xx: bool = False,
        keepttl: bool = False,
        get: bool = False,
        exat: Union[AbsExpiryT, None] = None,
        pxat: Union[AbsExpiryT, None] = None,
    ) -> bool | Any:
        if isinstance(value, (dict, list)):
            value = dumps(value, separators=(",", ":"))

        return await super().set(
            name,
            value,
            ex,
            px,
            nx,
            xx,
            keepttl,
            get,
            exat,
            pxat,
        )

    async def get(
        self,
        name: str,
        validate: bool = True,
    ) -> Optional[str | int | dict | list]:
        output = await super().get(name)
        if not validate or output is None:
            return output

        if output.isnumeric():
            return int(output)

        with suppress(JSONDecodeError):
            return loads(output)

        return output

    async def getdel(
        self,
        name: KeyT,
        validate: bool = True,
    ) -> Optional[str | int | dict | list]:
        async with self.pipeline() as pipe:
            await pipe.get(name)
            await pipe.delete(name)
            output, _ = await pipe.execute()

        if not validate or output is None:
            return output

        if output.isnumeric():
            return int(output)

        with suppress(JSONDecodeError):
            return loads(output)

        return output

    async def sadd(
        self,
        name: KeyT,
        *values: str,
        ex: Optional[int | timedelta] = None,
    ) -> Optional[int]:
        output = await super().sadd(name, *values)  # type: ignore
        if ex:
            await super().expire(name, ex)

        return output

    async def srem(
        self,
        name: KeyT,
        *values: str,
    ) -> Optional[int]:
        return await super().srem(name, *values)  # type: ignore

    async def sget(
        self,
        name: str,
    ) -> List:
        output = await super().smembers(name)  # type: ignore
        result = []

        for value in output:
            value = value.decode("utf-8")

            if value.isnumeric():
                result.append(int(value))
                continue

            with suppress(JSONDecodeError):
                result.append(loads(value))
                continue

            result.append(value)

        return result

    async def sismember(
        self, name: str, value: str
    ) -> Literal[0, 1]:
        return await super().sismember(name, value)  # type: ignore

    async def smembers(self, name: str) -> List[str]:
        output = await super().smembers(name)  # type: ignore
        return [
            value
            if isinstance(value, str)
            else value.decode("utf-8")
            for value in output
        ]

    async def rpush(
        self,
        name: str,
        *values: FieldT,
    ) -> int:
        return await super().rpush(name, *values)  # type: ignore

    async def ltrim(
        self,
        name: str,
        start: int,
        end: int,
    ) -> bool:
        return await super().ltrim(name, start, end)  # type: ignore

    async def llen(
        self,
        name: str,
    ) -> int:
        return await super().llen(name)  # type: ignore

    async def lrange(
        self,
        name: str,
        start: int,
        end: int,
    ) -> List:
        return await super().lrange(name, start, end)  # type: ignore

    async def ratelimited(
        self,
        resource: str,
        limit: int,
        timespan: int = 60,
        increment: int = 1,
    ) -> bool:
        key = f"rl:{xxh32_hexdigest(resource)}"

        try:
            current_usage = await self.evalsha(
                self.INCREMENT_SCRIPT_HASH,
                1,
                key,
                timespan,
                increment,
            )
        except NoScriptError:
            self.INCREMENT_SCRIPT_HASH = (
                await self.script_load(INCREMENT_SCRIPT)
            )
            current_usage = await self.evalsha(
                self.INCREMENT_SCRIPT_HASH,
                1,
                key,
                timespan,
                increment,
            )

        return int(current_usage) > limit

    def get_lock(
        self,
        name: KeyT,
        timeout: float = 500.0,
        sleep: float = 0.2,
        blocking: bool = True,
        blocking_timeout: Optional[float] = None,
        thread_local=True,
    ) -> Lock:
        name = f"rlock:{xxh32_hexdigest(name)}"

        return self.lock(
            name=name,
            timeout=timeout,
            sleep=sleep,
            blocking=blocking,
            blocking_timeout=blocking_timeout,
            thread_local=thread_local,
        )
