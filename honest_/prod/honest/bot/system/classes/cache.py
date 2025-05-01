import functools
from typing import Any, Callable, Coroutine

from cashews import cache

cache.setup("mem://")
