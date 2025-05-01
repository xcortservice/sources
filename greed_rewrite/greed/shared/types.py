from abc import ABC
from discord.ext.commands import Cog

from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    TYPE_CHECKING,
    Protocol,
    TypeVar,
    Union,
    Tuple,
    Optional,
)


T = TypeVar("T")

if TYPE_CHECKING:
    from greed.framework import Greed
    from greed.shared.config import Configuration

    from typing_extensions import ParamSpec

    from discord.ext.commands import (
        Bot,
        AutoShardedBot,
        Context,
        Cog,
        CommandError,
    )

    P = ParamSpec("P")
    MaybeAwaitableFunc = Callable[P, "MaybeAwaitable[T]"]
else:
    P = TypeVar("P")
    MaybeAwaitableFunc = Tuple[P, T]


class MixinMeta(ABC):
    bot: "Greed"
    config: "Configuration"


class CompositeMetaClass(type(Cog), type(ABC)):
    """
    This allows the metaclass used for proper type detection to
    coexist with discord.py's metaclass
    """

    pass


_Bot = Union["Bot", "AutoShardedBot"]
Coro = Coroutine[Any, Any, T]
CoroFunc = Callable[..., Coro[Any]]
MaybeCoro = Union[T, Coro[T]]
MaybeAwaitable = Union[T, Awaitable[T]]

CogT = TypeVar("CogT", bound="Optional[Cog]")
UserCheck = Callable[["ContextT"], MaybeCoro[bool]]
Hook = Union[
    Callable[["CogT", "ContextT"], Coro[Any]],
    Callable[["ContextT"], Coro[Any]],
]
Error = Union[
    Callable[
        ["CogT", "ContextT", "CommandError"], Coro[Any]
    ],
    Callable[["ContextT", "CommandError"], Coro[Any]],
]

ContextT = TypeVar("ContextT", bound="Context[Any]")
BotT = TypeVar("BotT", bound=_Bot, covariant=True)

ContextT_co = TypeVar(
    "ContextT_co", bound="Context[Any]", covariant=True
)


class Check(Protocol[ContextT_co]):  # type: ignore # TypeVar is expected to be invariant
    predicate: Callable[
        [ContextT_co], Coroutine[Any, Any, bool]
    ]

    def __call__(self, coro_or_commands: T) -> T: ...


# This is merely a tag type to avoid circular import issues.
# Yes, this is a terrible solution but ultimately it is the only solution.
class _BaseCommand:
    __slots__ = ()
