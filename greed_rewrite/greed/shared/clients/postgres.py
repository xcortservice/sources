from json import dumps, loads
from logging import getLogger
from typing import Any, List, Optional, Union

from asyncpg import Connection, Pool
from asyncpg import Record as DefaultRecord
from asyncpg import create_pool

log = getLogger("greed/db")


def ENCODER(self: Any) -> str:
    return dumps(self)


def DECODER(self: bytes) -> Any:
    return loads(self)


class Record(DefaultRecord):
    def __getattr__(
        self: "Record", name: Union[str, Any]
    ) -> Any:
        attr: Any = self[name]
        return attr

    def __setitem__(
        self, name: Union[str, Any], value: Any
    ) -> None:
        self.__dict__[name] = value

    def to_dict(self: "Record") -> dict[str, Any]:
        return dict(self)


class Database(Pool):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._statement_cache = {}

    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> str:
        if query not in self._statement_cache:
            self._statement_cache[
                query
            ] = await self.prepare(query)
        stmt = self._statement_cache[query]
        return await stmt.execute(*args, timeout=timeout)

    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> List[Record]: ...

    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> Optional[Record]: ...

    async def fetchval(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> Optional[str | int]: ...


async def init(connection: Connection):
    await connection.set_type_codec(
        "JSONB",
        schema="pg_catalog",
        encoder=ENCODER,
        decoder=DECODER,
    )

    # with open("vesta/shared/schemas/vesta.sql", "r", encoding="UTF-8") as buffer:
    #     schema = buffer.read()
    # await connection.execute(schema)


async def connect() -> Database:
    pool = await create_pool(
        "postgres://postgres:admin@localhost/rewrite",
        record_class=Record,
        init=init,
        min_size=10,
        max_size=20,
        max_queries=50000,
        max_inactive_connection_lifetime=300.0,
        command_timeout=60.0,
    )
    if not pool:
        raise RuntimeError(
            "Connection to PostgreSQL server failed!"
        )

    log.debug(
        "Connection to PostgreSQL has been established."
    )
    return pool  # type: ignore


__all__ = "Database"
