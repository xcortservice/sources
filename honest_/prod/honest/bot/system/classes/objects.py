import asyncio
from datetime import datetime
from typing import Any, Optional, Tuple, Union

from xxhash import xxh64_hexdigest as hash_

SET = set()


class RedisMock:
    def __init__(self, bot=None) -> None:
        self.bot = bot
        self._dict = {}
        self._rl = {}
        self._delete = {}
        self._futures = {}

    async def do_expiration(self, key: str, expiration: int) -> None:
        """
        Removes an item from the dictionary after a specified expiration time.

        Parameters:
            key (str): The key of the item to be removed.
            expiration (int): The time in seconds after which the item should be removed.
        """

        await asyncio.sleep(expiration)

        if key in self._dict:
            del self._dict[key]

    async def set(self, key: Any, value: Any, expiration: Optional[int] = None) -> int:
        """
        Set the value of the given key in the dictionary.

        Parameters:
            key (Any): The key to set the value for.
            value (Any): The value to set.
            expiration (Optional[int], optional): The expiration time in seconds. Defaults to None.

        Returns:
            int: The number of items in the dictionary after setting the value.
        """

        self._dict[key] = value

        if expiration is not None:
            if key in self._futures:
                self._futures[key].cancel()

            self._futures[key] = asyncio.ensure_future(
                self.do_expiration(key, expiration)
            )

        return 1

    async def sadd(self, key: Any, *values: Any) -> int:
        """
        Add one or more values to a set stored under a given key.

        Parameters:
            key (Any): The key under which the set is stored.
            *values (Any): The values to add to the set.

        Returns:
            int: The number of values that were successfully added to the set.

        Raises:
            AssertionError: If the provided key is already in the cache as another type.
        """

        if key not in self._dict:
            self._dict[key] = set()

        assert isinstance(
            self._dict[key], set
        ), "The provided key is already in the cache as another type."

        to_add = set()

        for value in values:
            if value not in self._dict[key]:
                to_add.add(value)

        for value in to_add:
            self._dict[key].add(value)

        return len(to_add)

    async def smembers(self, key: Any) -> Tuple[Any]:
        """
        Return a set of values associated with the given key.

        Parameters:
            key (Any): The key to retrieve the values for.

        Returns:
            set: A set of values associated with the key.

        Raises:
            AssertionError: If the key belongs to a different type.
        """

        assert isinstance(
            self._dict.get(key, SET), set
        ), "That key belongs to another type."

        return tuple(self._dict.get(key, SET))

    async def scard(self, key: Any) -> int:
        """
        Retrieve the cardinality of a set in the cache.

        Parameters:
            key (Any): The key associated with the set.

        Returns:
            int: The number of elements in the set.

        Raises:
            AssertionError: If the set does not exist in the cache or if it belongs to another type.
        """

        assert isinstance(
            self._dict.get(key), set
        ), "There is no such set in this cache, or that belongs to another type."

        return len(self._dict[key])

    async def srem(self, key: Any, *members: Any) -> int:
        """
        Remove the specified members from the set stored at key.
        If a member does not exist in the set, it is ignored.

        Parameters:
            key (Any): The key of the set in the cache.
            *members (Any): The members to remove from the set.

        Returns:
            int: The number of members that were successfully removed from the set.

        Raises:
            AssertionError: If the value associated with key is not a set.
        """

        assert isinstance(
            self._dict.get(key), set
        ), "There is no such set in this cache, or that belongs to another type."

        try:
            return len(
                tuple(
                    self._dict[key].remove(member)
                    for member in members
                    if member in self._dict[key]
                )
            )

        finally:
            if not self._dict[key]:
                del self._dict[key]

    async def delete(self, *keys: Any, pattern: Optional[str] = None) -> int:
        """
        Delete one or more keys from the dictionary.

        Parameters:
            *keys (Any): The keys to be deleted.
            pattern (Optional[str], optional): A pattern to filter the keys by. Defaults to None.

        Returns:
            int: The number of keys deleted.
        """

        if not keys and pattern is not None:
            keys = tuple(filter(lambda k: pattern.rstrip("*") in k, self._dict.keys()))

        return len(tuple(self._dict.pop(key) for key in keys if key in self._dict))

    async def get(self, key: Any) -> Any:
        """
        Get the value associated with the given key from the dictionary.

        Parameters:
            key (Any): The key to search for in the dictionary.

        Returns:
            Any: The value associated with the given key. Returns None if the key is not found.
        """

        return self._dict.get(key, None)

    async def keys(self, pattern: Optional[str] = None) -> Tuple[Any]:
        """
        Retrieves all keys from the dictionary that match the given pattern.

        Parameters:
            pattern (Optional[str]): A string pattern to match keys against. Defaults to None.

        Returns:
            Tuple[Any]: A tuple containing all the keys that match the pattern.
        """

        if pattern:
            return tuple(filter(lambda k: pattern.rstrip("*") in k, self._dict.keys()))

        return tuple(self._dict.keys())

    def is_ratelimited(self, key: Any, hashing_needed: Optional[bool] = True) -> bool:
        """
        Check if the given key is rate limited.

        Parameters:
            key (Any): The key to check for rate limiting.

        Returns:
            bool: True if the key is rate limited, False otherwise.
        """
        if hashing_needed:
            key = hash_(key)
        if key in self._dict:
            if self._dict[key] >= self._rl[key]:
                return True

        return False

    def time_remaining(self, key: Any, hashing_needed: Optional[bool] = True) -> int:
        """
        Calculates the time remaining for the given key in the cache.

        Parameters:
            key (Any): The key to check the remaining time for.

        Returns:
            int: The time remaining in seconds. Returns 0 if the key does not exist in the cache.
        """
        if hashing_needed:
            key = hash_(key)
        if key in self._dict and key in self._delete:
            if not self._dict[key] >= self._rl[key]:
                return 0

            return (
                self._delete[key]["last"] + self._delete[key]["bucket"]
            ) - datetime.now().timestamp()

        return 0

    async def ratelimited(self, key: str, amount: int, bucket: int) -> int:
        """
        Check if a key is rate limited and return the remaining time until the next request is allowed.

        Parameters:
            key (str): The key to check for rate limiting.
            amount (int): The maximum number of requests allowed within the rate limit window.
            bucket (int): The duration of the rate limit window in seconds.

        Returns:
            int: The remaining time in seconds until the next request is allowed. Returns 0 if the key is not rate limited.
        """
        key = hash_(key)

        current_time = datetime.now().timestamp()
        self._rl[key] = amount
        if key not in self._dict:
            self._dict[key] = 1

            if key not in self._delete:
                self._delete[key] = {"bucket": bucket, "last": current_time}

            return 0

        try:
            if self._delete[key]["last"] + bucket <= current_time:
                self._dict[key] = 0
                self._delete[key]["last"] = current_time

            self._dict[key] += 1

            if self._dict[key] > self._rl[key]:
                return round((bucket - (current_time - self._delete[key]["last"])), 3)

            return 0

        except Exception:
            return self.ratelimited(key, amount, bucket)
