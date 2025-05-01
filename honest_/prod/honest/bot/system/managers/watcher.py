import asyncio
import logging
import os
import sys
import typing
from asyncio.subprocess import PIPE
from functools import wraps
from pathlib import Path
from typing import List, Optional, Union

import discord
from watchfiles import Change, awatch  # type: ignore


def decide_prefix(
    message: discord.Message, prefixes: typing.Any, default_prefix: str
) -> str:
    if isinstance(prefixes, dict):
        for prefix_type, prefix in prefixes.items():
            if message.content.strip().startswith(prefix):
                return {prefix_type: prefix}
    else:
        for prefix in prefixes:
            if message.content.strip().startswith(prefix):
                return prefix
    return default_prefix


try:
    from discord.ext import commands
except ImportError:
    from nextcord.ext import commands  # type: ignore


logger = logging.getLogger("RebootRunner")
logger.addHandler(logging.NullHandler())
# prevents log events bubbling up to the parent and duplicating output
logger.propagate = False


async def auto_commit():
    return
    await asyncio.create_subprocess_shell(
        "cd .. ; git init ; git add * ; git commit -m 'auto push' ; git push",
        stdout=PIPE,
    )
    return True


class RebootRunner:
    """The core cogwatch class -- responsible for starting up watchers and managing cogs.

    Attributes
        :client: A Bot client.
        :path: Root name of the cogs directory; cogwatch will only watch within
        this directory -- recursively.
        :debug: Whether to run the bot only when the debug flag is True.
        Defaults to True.
        :loop: Custom event loop. If not specified, will use the current running
        event loop.
        :default_logger: Whether to use the default logger (to sys.stdout) or
        not. Defaults to True.
        :preload: Whether to detect and load all found cogs on startup. Defaults
        to False.
        :colors: Whether to use colorized terminal outputs or not. Defaults to
        True.
    """

    def __init__(
        self,
        client: commands.Bot,
        path: Union[str, List[str]] = "commands",
        debug: bool = True,
        loop: asyncio.BaseEventLoop = None,
        default_logger: bool = True,
        preload: bool = False,
        auto_commit: bool = True,
        colors: bool = True,
    ):
        self.client = client
        self.path = path
        self.debug = debug
        self.auto_commit = auto_commit
        self.loop = loop
        self.started = False
        self.default_logger = default_logger
        self.preload = preload
        self.colors = colors

        if self.colors:
            self.CEND = "\33[0m"
            self.CBOLD = "\33[1m"
            self.CGREEN = "\33[32m"
            self.CRED = "\33[31m"
        else:
            self.CEND, self.CBOLD, self.CGREEN, self.CRED = "", "", "", ""

        if default_logger:
            watch_log = logging.getLogger("RebootRunner")
            watch_log.setLevel(logging.INFO)
            watch_handler = logging.StreamHandler(sys.stdout)
            watch_handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
            watch_log.addHandler(watch_handler)

    @staticmethod
    def get_cog_name(path: str) -> str:
        """Returns the cog file name without .py appended to it."""
        _path = os.path.normpath(path)
        return _path.split(os.sep)[-1:][0][:-3]

    def humanize_paths(self) -> str:
        if isinstance(self.path, str):
            return self.path
        return ", ".join(p for p in self.path)

    def get_path(self):
        if isinstance(self.path, list):
            for path in self.path:
                if not Path(Path.cwd() / path).exists():
                    return path
        if isinstance(self.path, str):
            if not Path(Path.cwd() / self.path).exists():
                return self.path

    def get_dotted_cog_path(self, path: str, directory: Optional[str] = None) -> str:
        """Returns the full dotted path that discord.py uses to load cog files."""
        _path = os.path.normpath(path)
        tokens = _path.split(os.sep)
        reversed_tokens = list(reversed(tokens))

        # iterate over the list backwards in order to get the first occurrence in cases where a duplicate
        # name exists in the path (ie. example_proj/example_proj/commands)
        try:
            root_index = (
                reversed_tokens.index(
                    directory.split("/")[0] or self.path.split("/")[0]
                )
                + 1
            )
        except ValueError:
            raise ValueError("Use forward-slash delimiter in your `path` parameter.")

        return ".".join([token for token in tokens[-root_index:-1]])

    async def _start(self):
        """Starts a watcher, monitoring for any file changes and dispatching event-related methods appropriately."""
        while self.dir_exists():
            if isinstance(self.path, list):
                for path in self.path:
                    await self.check(path)
            else:
                await self.check(self.path)

    async def check(self, path: str):
        if self.dir_exists():
            try:
                async for changes in awatch(Path.cwd() / path):
                    self.validate_dir()

                    reverse_ordered_changes = sorted(changes, reverse=True)

                    for change in reverse_ordered_changes:
                        change_type = change[0]
                        change_path = change[1]

                        filename = self.get_cog_name(change_path)

                        new_dir = self.get_dotted_cog_path(change_path, path)
                        cog_dir = (
                            f"{new_dir}.{filename}" if new_dir else f"{path}.{filename}"
                        )

                        if change_type == Change.deleted:
                            if cog_dir in self.client.extensions:
                                await self.unload(cog_dir)
                        elif change_type == Change.added:
                            if cog_dir not in self.client.extensions:
                                await self.load(cog_dir)
                        elif change_type == Change.modified and change_type != (
                            Change.added or Change.deleted
                        ):
                            if cog_dir in self.client.extensions:
                                await self.reload(cog_dir)
                            else:
                                await self.load(cog_dir)
                        await auto_commit()
            except FileNotFoundError:
                return

            else:
                await asyncio.sleep(1)

        else:
            await self.start()

    def check_debug(self):
        """Determines if the watcher should be added to the event loop based on debug flags."""
        return any([(self.debug and __debug__), not self.debug])

    def dir_exists(self):
        """Predicate method for checking whether the specified dir exists."""
        if isinstance(self.path, list):
            for path in self.path:
                if not Path(Path.cwd() / path).exists():
                    return False
            return True
        else:
            return Path(Path.cwd() / self.path).exists()

    def validate_dir(self):
        """Method for raising a FileNotFound error when the specified directory does not exist."""
        if not self.dir_exists():
            raise FileNotFoundError
        return True

    async def start(self):
        """Checks for a user-specified event loop to start on, otherwise uses current running loop."""
        _check = False
        if self.started is True:
            return
        while not self.dir_exists():
            if not _check:
                logger.error(f"One of the pathes dont not exist. {self.get_path()}")
                _check = True

        else:
            logger.info(f"Found {self.CBOLD}{self.humanize_paths()}{self.CEND}!")
            if self.preload:
                await self._preload()

            if self.check_debug():
                if self.loop is None:
                    self.loop = asyncio.get_event_loop()

                logger.info(
                    f"Watching for file changes in {self.CBOLD}{self.humanize_paths()}{self.CEND}..."
                )
                self.loop.create_task(self._start())
        self.started = True

    async def commit(self) -> str:
        process = await asyncio.create_subprocess_shell(
            "git add * ; git commit -m 'auto commit'; git push --force", stderr=PIPE
        )
        output = await process.communicate()
        _ = [i for i in output if i is not None]
        return _[0]

    async def load(self, cog_dir: str):
        """Loads a cog file into the client."""
        try:
            await self.client.load_extension(cog_dir)
        except commands.ExtensionAlreadyLoaded:
            logger.info(f"Cannot reload {cog_dir} because it is not loaded.")
        except commands.NoEntryPointError:
            logger.info(
                f"{self.CBOLD}{self.CRED}[Error]{self.CEND} Failed to load {self.CBOLD}{cog_dir}{self.CEND}; no entry point found."
            )
        except Exception as exc:
            self.cog_error(exc)
        else:
            logger.info(f"{self.CBOLD}{self.CGREEN}[Cog Loaded]{self.CEND} {cog_dir}")

    async def unload(self, cog_dir: str):
        """Unloads a cog file into the client."""
        try:
            await self.client.unload_extension(cog_dir)
        except commands.ExtensionNotLoaded:
            logger.info(f"Cannot reload {cog_dir} because it is not loaded.")
        except Exception as exc:
            self.cog_error(exc)
        else:
            logger.info(f"{self.CBOLD}{self.CRED}[Cog Unloaded]{self.CEND} {cog_dir}")

    async def reload(self, cog_dir: str):
        """Attempts to atomically reload the file into the client."""
        if self.auto_commit is not False:
            await self.commit()
        try:
            await self.client.reload_extension(cog_dir)
        except commands.NoEntryPointError:
            logger.info(
                f"{self.CBOLD}{self.CRED}[Error]{self.CEND} Failed to reload {self.CBOLD}{cog_dir}{self.CEND}; no entry point found."
            )
        except commands.ExtensionNotLoaded:
            logger.info(f"Cannot reload {cog_dir} because it is not loaded.")
        except Exception as exc:
            self.cog_error(exc)
        else:
            logger.info(f"{self.CBOLD}{self.CGREEN}[Cog Reloaded]{self.CEND} {cog_dir}")

    @staticmethod
    def cog_error(exc: Exception):
        """Logs exceptions. TODO: Need thorough exception handling."""
        if isinstance(exc, (commands.ExtensionError, SyntaxError)):
            logging.exception(exc)

    async def _preload(self):
        logger.info("Preloading cogs...")
        for cog in {
            (file.stem, file) for file in Path(Path.cwd() / self.path).rglob("*.py")
        }:
            new_dir = self.get_dotted_cog_path(cog[1])
            await self.load(".".join([new_dir, cog[0]]))


def watch(**kwargs):
    """Instantiates a watcher by hooking into a Bot client methods' `self` attribute."""

    def decorator(function):
        @wraps(function)
        async def wrapper(client):
            cw = RebootRunner(client, **kwargs)
            await cw.start()
            ret_val = await function(client)
            return ret_val

        return wrapper

    return decorator
