from discord.ext.commands import Cog
from collections import defaultdict
from typing import Dict
from asyncio import Lock

from greed.framework import Greed

from .security.antinuke import AntiNuke
from .security.antiraid import AntiRaid
from .giveaways import Giveaway
from .automod import Automod
from .miscs import Miscs
from .confessions import Confessions
from .wordstats import WordStats
from .autopfp import autopfp
from .emojis import Emojis
from .boosterrole import boosterrole
from .logging import Logging
from .levels import Levels
from .reactionrole import reactionrole
from .react import AntiSelfReact, ButtonRoles
from .alias import alias
from .system import System

import logging

logger = logging.getLogger("greed/plugins/config")

class Config(
    AntiNuke,
    AntiRaid,
    Giveaway,
    Automod,
    Miscs,
    Confessions,
    WordStats,
    autopfp,
    Emojis,
    boosterrole,
    Logging,
    Levels,
    reactionrole,
    AntiSelfReact,
    ButtonRoles,
    alias,
    System,
    Cog,
):
    """
    Load all the configuration cogs into one cog.
    """

    def __init__(self, bot: Greed):
        self.bot = bot
        self._locks = defaultdict(Lock)
        self.entry_updating = False
        logger.info("Initializing Config cog")
        
        Cog.__init__(self)
        
        AntiNuke.__init__(self, bot)
        AntiRaid.__init__(self, bot)
        Giveaway.__init__(self, bot)
        Automod.__init__(self, bot)
        Miscs.__init__(self, bot)
        Confessions.__init__(self, bot)
        WordStats.__init__(self, bot)
        autopfp.__init__(self, bot)
        Emojis.__init__(self, bot)
        boosterrole.__init__(self, bot)
        Logging.__init__(self, bot)
        Levels.__init__(self, bot)
        reactionrole.__init__(self, bot)
        AntiSelfReact.__init__(self, bot)
        ButtonRoles.__init__(self, bot)
        alias.__init__(self, bot)
        System.__init__(self, bot)
        logger.info("Config cog initialized")

    @property
    def locks(self) -> Dict[str, Lock]:
        if not hasattr(self, '_locks'):
            self._locks = defaultdict(Lock)
        return self._locks

    @locks.setter
    def locks(self, value: Dict[str, Lock]) -> None:
        self._locks = value

    async def cog_load(self) -> None:
        logger.info("Config cog load hook triggered")
        await Giveaway.setup_hook(self)
        await autopfp.setup_hook(self)
        logger.info("Config cog load complete")


async def setup(bot: "Greed") -> None:
    logger.info("Setting up Config cog")
    cog = Config(bot)
    await bot.add_cog(cog)
    logger.info("Config cog setup complete")
