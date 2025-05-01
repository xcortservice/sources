from typing import Optional, Union

from discord import Member, User

from ..classes.database import Record


async def config(self: Union[Member, User]) -> Optional[Record]:
    bot = self._state._get_client()
    return await bot.db.fetchrow(
        """SELECT * FROM user_config WHERE user_id = $1""", self.id
    )


async def is_donator(self: Union[Member, User]):
    bot = self._state._get_client()
    if await bot.db.fetchrow("""SELECT * FROM donators WHERE user_id = $1""", self.id):
        return True
    return False


async def worker_badges(self: Union[Member, User]):
    bot = self._state._get_client()
    raise NotImplementedError("Dont know how you want this done etc")


@property
def url(self: Union[Member, User]) -> str:
    return f"https://discord.com/users/{self.id}"
