from __future__ import annotations

from enum import StrEnum, auto

from greed.framework import Greed, Context


class LogType(StrEnum):
    MESSAGE = auto()
    MEMBER = auto()
    ROLE = auto()
    CHANNEL = auto()
    INVITE = auto()
    MODERATION = auto()
    VOICE = auto()
    EMOJI = auto()
    STICKER = auto()

    @classmethod
    def all(cls):
        return list(cls)

    @classmethod
    def all_but(cls, *excluded):
        return [e for e in cls.all() if e not in excluded]

    def __str__(self):
        return self.name.lower()

    @classmethod
    def from_str(cls, string: str):
        return cls[string.upper()]

    @classmethod
    def from_list(cls, list_: list[str]):
        return [cls.from_str(string) for string in list_]

    @classmethod
    async def convert(
        cls, ctx: Context, argument: str
    ) -> LogType:
        """Converts a string to a LogType enum."""

        try:
            return cls.from_str(argument)
        except KeyError:
            raise ValueError(
                "The provided argument is not a valid log type"
            )