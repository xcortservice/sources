from typing import Any

from discord.ext.commands import CommandError


class NSFWDetection(CommandError):
    def __init__(self: "NSFWDetection", message: str, **kwargs: Any):
        super().__init__(message)


class ConcurrencyLimit(CommandError):
    def __init__(self: "ConcurrencyLimit", message: str, **kwargs: Any):
        super().__init__(message)


class InvalidSubCommand(CommandError):
    def __init__(self: "InvalidSubCommand", message: str, **kwargs: Any):
        super().__init__(message)


class SnipeError(CommandError):
    def __init__(self: "SnipeError", message: str, **kwargs: Any):
        super().__init__(message)
        self.kwargs = kwargs


class RolePosition(CommandError):
    def __init__(self: "RolePosition", message: str, **kwargs: Any):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class EmbedError(CommandError):
    def __init__(self: "EmbedError", message: str, **kwargs: Any):
        self.message = message
        super().__init__(message, kwargs)


class LastFMError(CommandError):
    def __init__(self: "LastFMError", error_code: int, message: str):
        super().__init__()
        self.error_code = error_code
        self.message = message

    def __str__(self: "LastFMError"):
        return f"LastFM error {self.error_code}"

    def display(self: "LastFMError"):
        return f"LastFM error {self.error_code} : {self.message}"
