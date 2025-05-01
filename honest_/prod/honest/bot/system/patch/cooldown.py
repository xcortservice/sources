import asyncio
import time
from collections import deque
from typing import (TYPE_CHECKING, Any, Callable, Deque, Dict, Generic,
                    Optional, TypeVar, Union)

from discord.abc import PrivateChannel
from discord.app_commands import Cooldown as Cooldown
from discord.enums import Enum

from .context import Context
from .errors import MaxConcurrencyReached

if TYPE_CHECKING:
    from typing_extensions import Self

    from ...message import Message

T_contra = TypeVar("T_contra", contravariant=True)


class BucketType(Enum):
    default = 0
    user = 1
    guild = 2
    channel = 3
    member = 4
    category = 5
    role = 6

    def get_key(self, msg: Union[Message, Context[Any]]) -> Any:
        if self is BucketType.user:
            return msg.author.id
        elif self is BucketType.guild:
            return (msg.guild or msg.author).id
        elif self is BucketType.channel:
            return msg.channel.id
        elif self is BucketType.member:
            return ((msg.guild and msg.guild.id), msg.author.id)
        elif self is BucketType.category:
            return (getattr(msg.channel, "category", None) or msg.channel).id
        elif self is BucketType.role:
            return (
                msg.channel
                if isinstance(msg.channel, PrivateChannel)
                else msg.author.top_role
            ).id

    def __call__(self, msg: Union[Message, Context[Any]]) -> Any:
        return self.get_key(msg)


class CooldownMapping(Generic[T_contra]):
    def __init__(
        self,
        original: Optional[Cooldown],
        type: Callable[[T_contra], Any],
    ) -> None:
        if not callable(type):
            raise TypeError("Cooldown type must be a BucketType or callable")

        self._cache: Dict[Any, Cooldown] = {}
        self._cooldown: Optional[Cooldown] = original
        self._type: Callable[[T_contra], Any] = type

    def copy(self) -> CooldownMapping[T_contra]:
        ret = CooldownMapping(self._cooldown, self._type)
        ret._cache = self._cache.copy()
        return ret

    @property
    def valid(self) -> bool:
        return self._cooldown is not None

    @property
    def type(self) -> Callable[[T_contra], Any]:
        return self._type

    @classmethod
    def from_cooldown(
        cls, rate: float, per: float, type: Callable[[T_contra], Any]
    ) -> Self:
        return cls(Cooldown(rate, per), type)

    def _bucket_key(self, msg: T_contra) -> Any:
        return self._type(msg)

    def _verify_cache_integrity(self, current: Optional[float] = None) -> None:
        current = current or time.time()
        dead_keys = [k for k, v in self._cache.items() if current > v._last + v.per]
        for k in dead_keys:
            del self._cache[k]

    def create_bucket(self, message: T_contra) -> Cooldown:
        return self._cooldown.copy()

    def get_bucket(
        self, message: T_contra, current: Optional[float] = None
    ) -> Optional[Cooldown]:
        if self._type is BucketType.default:
            return self._cooldown

        self._verify_cache_integrity(current)
        key = self._bucket_key(message)
        if key not in self._cache:
            bucket = self.create_bucket(message)
            if bucket is not None:
                self._cache[key] = bucket
        else:
            bucket = self._cache[key]

        return bucket

    def update_rate_limit(
        self, message: T_contra, current: Optional[float] = None, tokens: int = 1
    ) -> Optional[float]:
        bucket = self.get_bucket(message, current)
        if bucket is None:
            return None
        return bucket.update_rate_limit(current, tokens=tokens)


class DynamicCooldownMapping(CooldownMapping[T_contra]):
    def __init__(
        self,
        factory: Callable[[T_contra], Optional[Cooldown]],
        type: Callable[[T_contra], Any],
    ) -> None:
        super().__init__(None, type)
        self._factory: Callable[[T_contra], Optional[Cooldown]] = factory

    def copy(self) -> DynamicCooldownMapping[T_contra]:
        ret = DynamicCooldownMapping(self._factory, self._type)
        ret._cache = self._cache.copy()
        return ret

    @property
    def valid(self) -> bool:
        return True

    def create_bucket(self, message: T_contra) -> Optional[Cooldown]:
        return self._factory(message)


class _Semaphore:
    __slots__ = ("value", "loop", "_waiters")

    def __init__(self, number: int) -> None:
        self.value: int = number
        self.loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._waiters: Deque[asyncio.Future] = deque()

    def __repr__(self) -> str:
        return f"<_Semaphore value={self.value} waiters={len(self._waiters)}>"

    def locked(self) -> bool:
        return self.value == 0

    def is_active(self) -> bool:
        return len(self._waiters) > 0

    def wake_up(self) -> None:
        while self._waiters:
            future = self._waiters.popleft()
            if not future.done():
                future.set_result(None)
                return

    async def acquire(self, *, wait: bool = False) -> bool:
        if not wait and self.value <= 0:
            return False

        while self.value <= 0:
            future = self.loop.create_future()
            self._waiters.append(future)
            try:
                await future
            except:
                future.cancel()
                if self.value > 0 and not future.cancelled():
                    self.wake_up()
                raise

        self.value -= 1
        return True

    def release(self) -> None:
        self.value += 1
        self.wake_up()


class MaxConcurrency:
    __slots__ = ("number", "per", "wait", "_mapping")

    def __init__(self, number: int, *, per: BucketType, wait: bool) -> None:
        self._mapping: Dict[Any, _Semaphore] = {}
        self.per: BucketType = per
        self.number: int = number
        self.wait: bool = wait

        if number <= 0:
            raise ValueError("max_concurrency 'number' cannot be less than 1")

        if not isinstance(per, BucketType):
            raise TypeError(
                f"max_concurrency 'per' must be of type BucketType not {type(per)!r}"
            )

    def copy(self) -> Self:
        return self.__class__(self.number, per=self.per, wait=self.wait)

    def __repr__(self) -> str:
        return (
            f"<MaxConcurrency per={self.per!r} number={self.number} wait={self.wait}>"
        )

    def get_key(self, message: Union[Message, Context[Any]]) -> Any:
        return self.per.get_key(message)

    async def acquire(self, message: Union[Message, Context[Any]]) -> None:
        key = self.get_key(message)
        sem = self._mapping.setdefault(key, _Semaphore(self.number))
        acquired = await sem.acquire(wait=self.wait)
        if not acquired:
            raise MaxConcurrencyReached(self.number, self.per)

    async def release(self, message: Union[Message, Context[Any]]) -> None:
        key = self.get_key(message)
        sem = self._mapping.get(key)
        if sem:
            sem.release()
            if sem.value >= self.number and not sem.is_active():
                del self._mapping[key]


import discord
from discord.ext import commands

# Assuming CooldownMapping, DynamicCooldownMapping, MaxConcurrency, and BucketType are already defined above.

# Override default classes
commands.CooldownMapping = CooldownMapping
commands.DynamicCooldownMapping = DynamicCooldownMapping
commands.MaxConcurrency = MaxConcurrency
commands.BucketType = BucketType
