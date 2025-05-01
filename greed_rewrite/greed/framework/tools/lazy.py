from __future__ import annotations

import asyncio
import functools
import inspect
import warnings
import graphviz
import logging

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union
from typing_extensions import ParamSpec
from dataclasses import dataclass, field

logger = logging.getLogger("greed/tools/lazy")

P = ParamSpec("P")
T = TypeVar("T")

GLOBAL_DELAYED_CACHE: Dict[str, Any] = {}


@dataclass
class TaskNode:
    """Represents a node in the task graph."""

    func: Callable
    args: tuple
    kwargs: dict
    key: str
    pure: bool = True
    computed: bool = False
    result: Any = None
    dependencies: Set[TaskNode] = field(default_factory=set)
    _hash_cache: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.func, LazyResult):
            raise ValueError(
                "Cannot create a delayed task from an already computed result. "
                "Use the function itself with lazy decorator instead."
            )


class LazyResult:
    """
    Represents a lazy computation result.

    Best Practices:
    1. Always call lazy on functions, not on their results
    2. Collect multiple computations and compute them at once
    3. Avoid mutating input data
    4. Avoid global state
    5. Always ensure your lazy computations are eventually computed
    6. Break computations into appropriate-sized tasks (not too big, not too small)

    Example:
        @lazy
        def process_data(x):
            return x + 1

        results = []
        for x in range(10):
            y = process_data(x)
            results.append(y)

        final_results = await compute_many(*results)
    """

    def __init__(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        key: Optional[str] = None,
        pure: bool = True,
        batch_size: Optional[int] = None,
    ):
        if isinstance(func, LazyResult):
            raise ValueError(
                "Cannot create a lazy computation from an already lazy result. "
                "Use the original function with the @lazy decorator instead."
            )

        self.task = TaskNode(
            func=func,
            args=args,
            kwargs=kwargs,
            key=key or f"{func.__name__}_{id(self)}",
            pure=pure,
        )
        self._graph: Dict[str, TaskNode] = {self.task.key: self.task}
        self.batch_size = batch_size
        self._build_graph()

    def _build_graph(self):
        """Builds the task graph by identifying dependencies."""
        for arg in self.task.args:
            if isinstance(arg, LazyResult):
                self.task.dependencies.add(arg.task)
                self._graph.update(arg._graph)

        for arg in self.task.kwargs.values():
            if isinstance(arg, LazyResult):
                self.task.dependencies.add(arg.task)
                self._graph.update(arg._graph)

    async def compute(self) -> Any:
        """
        Computes the result of this lazy computation.

        Returns:
            The computed result

        Note:
            For better performance, use compute_many when computing multiple results.
        """
        if self.task.computed:
            return self.task.result

        if self.task.pure:
            cache_key = self._get_cache_key()
            if cache_key in GLOBAL_DELAYED_CACHE:
                self.task.result = GLOBAL_DELAYED_CACHE[cache_key]
                self.task.computed = True
                return self.task.result

        dep_results = []
        for dep in self.task.dependencies:
            if isinstance(dep, TaskNode):
                if not dep.computed:
                    dep_result = await self._compute_node(dep)
                else:
                    dep_result = dep.result
                dep_results.append(dep_result)

        args = []
        for arg in self.task.args:
            if isinstance(arg, LazyResult):
                args.append(await arg.compute())
            else:
                args.append(deepcopy(arg) if self._should_copy(arg) else arg)

        kwargs = {}
        for key, value in self.task.kwargs.items():
            if isinstance(value, LazyResult):
                kwargs[key] = await value.compute()
            else:
                kwargs[key] = deepcopy(value) if self._should_copy(value) else value

        try:
            if inspect.iscoroutinefunction(self.task.func):
                result = await self.task.func(*args, **kwargs)
            else:
                result = self.task.func(*args, **kwargs)

            self.task.result = result
            self.task.computed = True

            if self.task.pure:
                cache_key = self._get_cache_key()
                GLOBAL_DELAYED_CACHE[cache_key] = result

            return result
        except Exception as e:
            logger.error(f"Error computing task {self.task.key}: {str(e)}")
            raise

    def _should_copy(self, value: Any) -> bool:
        """Determines if a value should be copied to prevent mutations."""
        return hasattr(value, "__copy__") or hasattr(value, "__deepcopy__")

    def _get_cache_key(self) -> str:
        """Generates a cache key for the task based on function and inputs."""
        if not self.task.pure:
            return None

        key_parts = [
            f"{self.task.func.__module__}.{self.task.func.__name__}",
            *(str(arg) for arg in self.task.args),
            *(f"{k}={v}" for k, v in sorted(self.task.kwargs.items())),
        ]
        return "|".join(key_parts)

    async def _compute_node(self, node: TaskNode) -> Any:
        """Computes a single node in the task graph."""
        if node.computed:
            return node.result

        if node.pure:
            cache_key = self._get_cache_key()
            if cache_key in GLOBAL_DELAYED_CACHE:
                node.result = GLOBAL_DELAYED_CACHE[cache_key]
                node.computed = True
                return node.result

        args = []
        for arg in node.args:
            if isinstance(arg, LazyResult):
                args.append(await arg.compute())
            else:
                args.append(deepcopy(arg) if self._should_copy(arg) else arg)

        kwargs = {}
        for key, value in node.kwargs.items():
            if isinstance(value, LazyResult):
                kwargs[key] = await value.compute()
            else:
                kwargs[key] = deepcopy(value) if self._should_copy(value) else value

        try:
            if inspect.iscoroutinefunction(node.func):
                result = await node.func(*args, **kwargs)
            else:
                result = node.func(*args, **kwargs)

            node.result = result
            node.computed = True

            if node.pure:
                cache_key = self._get_cache_key()
                GLOBAL_DELAYED_CACHE[cache_key] = result

            return result
        except Exception as e:
            logger.error(f"Error computing node {node.key}: {str(e)}")
            raise

    def visualize(self, filename: str = "task_graph") -> None:
        """
        Visualizes the task graph using graphviz.

        Args:
            filename: The name of the output file (without extension)
        """
        dot = graphviz.Digraph(comment="Task Graph")
        dot.attr(rankdir="LR")

        for node in self._graph.values():
            label = f"{node.func.__name__}\n{node.key}"
            dot.node(node.key, label)

        for node in self._graph.values():
            for dep in node.dependencies:
                dot.edge(dep.key, node.key)

        dot.render(filename, view=True, format="png")


def lazy(
    func: Optional[Callable[P, T]] = None,
    pure: bool = True,
    key: Optional[str] = None,
    batch_size: Optional[int] = None,
) -> Union[Callable[P, LazyResult], LazyResult]:
    """
    Decorator that creates a lazy version of a function.

    Args:
        func: The function to make lazy
        pure: Whether the function is pure (same inputs always give same outputs)
        key: Optional key to identify the task
        batch_size: Optional batch size for processing large sequences

    Returns:
        A wrapped function that returns a LazyResult instead of computing immediately

    Example:
        @lazy
        def process_data(x):
            return x + 1

        result = process_data(5)

        value = await result.compute()
    """

    def decorator(f: Callable[P, T]) -> Callable[P, LazyResult]:
        @functools.wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> LazyResult:
            if any(isinstance(arg, LazyResult) for arg in args) or any(
                isinstance(arg, LazyResult) for arg in kwargs.values()
            ):
                warnings.warn(
                    "Creating a lazy task with LazyResult arguments. "
                    "Consider restructuring your code to avoid nesting lazy computations.",
                    stacklevel=2,
                )

            return LazyResult(
                func=f,
                args=args,
                kwargs=kwargs,
                key=key or f"{f.__name__}_{id(wrapper)}",
                pure=pure,
                batch_size=batch_size,
            )

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


async def compute_many(*tasks: LazyResult) -> List[Any]:
    """
    Compute multiple lazy results efficiently.

    Args:
        *tasks: LazyResult objects to compute

    Returns:
        List of computed results

    Example:
        results = []
        for x in range(10):
            y = process_data(x)
            results.append(y)

        values = await compute_many(*results)
    """
    return await asyncio.gather(*(task.compute() for task in tasks))


def clear_cache() -> None:
    """Clears the global computation cache."""
    GLOBAL_DELAYED_CACHE.clear() 