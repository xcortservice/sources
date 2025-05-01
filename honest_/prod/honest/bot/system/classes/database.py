from __future__ import annotations

import asyncio
from types import TracebackType
from typing import (Any, Iterable, List, Optional, Protocol, Sequence, Type,
                    TypeVar, Union)

import msgspec
import ujson
from asyncpg import Connection, Pool
from asyncpg import Record as DefaultRecord
from asyncpg import create_pool
from data.config import CONFIG
from discord.ext.commands import Context, check
from loguru import logger
from loguru import logger as log
from pydantic import BaseModel


class UserModel(BaseModel):
    user_id: (
        Any  # this is to reduce bottlenecking as the id doesn't need to be validated
    )


class GuildModel(BaseModel):
    guild_id: Any


T = TypeVar("T")


def cast(typ: Union[Type[T], Type[List[T]]], val: Any) -> Any:
    """
    Cast a value to a type.

    If the type is a list of a model, it constructs instances of the model
    for each item in the input list. If the type is a single model, it
    constructs a single instance of the model from the input dictionary.

    Args:
        typ: The type to cast to (e.g., Model or List[Model]).
        val: The value to be cast (e.g., a dictionary or a list of dictionaries).

    Returns:
        An instance of the type or a list of instances of the type.
    """
    if hasattr(typ, "__origin__") and typ.__origin__ is list:
        model_class = typ.__args__[0]
        return [model_class(**d) for d in val]
    else:
        return typ(**val)


def query_limit(table: str, limit: int = 5):
    async def predicate(ctx: Context):
        check = await ctx.bot.db.fetchval(
            f"SELECT COUNT(*) FROM {table} WHERE guild_id = $1", ctx.guild.id
        )
        if check == limit:
            await ctx.fail(f"You cannot create more than **{limit}** {table}s")
            return False
        return True

    return check(predicate)


class Record(DefaultRecord):
    def __getattr__(self: "Record", name: Union[str, Any]) -> Any:
        attr: Any = self[name]
        return attr

    def __dict__(self: "Record") -> dict[str, Any]:
        return dict(self)


class ConnectionContextManager(Protocol):
    async def __aenter__(self) -> Connection: ...

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None: ...


class Database:
    def __init__(self):
        self.uri: str = (
            f"postgres://{CONFIG['database']['user']}:{CONFIG['database']['password']}@localhost:5432/{CONFIG['database']['name']}"
        )
        self.pool: Optional[Pool] = None
        self.cache = {}

    def json_encoder(self, *data: Any):
        return ujson.dumps(data[1])

    def json_decoder(self, *data: Any):
        return ujson.loads(data[1])

    def jsonb_encoder(self, *data: Any):
        return msgspec.json.encode(data[-1]).decode("UTF-8")

    def jsonb_decoder(self, *data: Any):
        return msgspec.json.decode(data[-1])

    async def settings(self, connection: Connection) -> None:
        await connection.set_type_codec(
            "json",
            encoder=self.json_encoder,
            decoder=self.json_decoder,
            schema="pg_catalog",
        )
        await connection.set_type_codec(
            "jsonb",
            encoder=self.jsonb_encoder,
            decoder=self.jsonb_decoder,
            schema="pg_catalog",
            format="text",
        )

    async def create(self) -> Pool:
        pool: Pool = await create_pool(
            dsn=self.uri, init=self.settings, record_class=Record
        )
        log.info(f"Initialized database connection {pool.__hash__()}")
        return pool

    def create_database(
        self, database: str, username: str, password: str, host: str, port: int
    ):
        import psycopg2

        conn = psycopg2.connect(
            dbname="postgres", user=username, password=password, host=host, port=port
        )
        conn.autocommit = True  # Allow immediate execution of CREATE DATABASE

        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE {database};")
            logger.info(f"Database '{database}' created successfully.")

        conn.close()
        return True

    async def connect(self) -> Pool:
        string, database_name = self.uri.replace("postgres://", "").split("/")
        auth, data = string.split("@")
        username, password = auth.split(":")
        host, port = data.split(":")
        try:
            self.pool = await self.create()
        except Exception:
            await asyncio.to_thread(
                self.create_database, database_name, username, password, host, int(port)
            )
            self.pool = await self.create()
        try:
            await self.execute("""CREATE EXTENSION IF NOT EXISTS timescaledb;""")
        except Exception:
            pass
        return self.pool

    async def close(self) -> None:
        if not self.pool:
            return
        await self.pool.close()
        log.info(f"Closed database connection {self.pool.__hash__()}")

    async def delete_cache_entry(self, type: str, sql: str, *args):
        await asyncio.sleep(60)
        try:
            self.cache.pop(f"{type} {sql} {args}")
        except Exception:
            pass

    async def add_to_cache(self, data: Any, type: str, sql: str, *args):
        if "economy" not in sql.lower():
            self.cache[f"{type} {sql} {args}"] = data

    async def search_and_delete(self, table: str):
        for k in self.cache.keys():
            if table.lower() in k.lower():
                self.cache.pop(k)

    async def fetch(self, sql: str, *args, **kwargs):
        cached = kwargs.get("cached", True)
        model = kwargs.pop("model", None)
        if cached:
            if result := self.cache.get(f"fetch {sql} {args}"):
                if model:
                    return cast(List[model], result)
                return result
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetch(sql, *args)
                await self.add_to_cache(data, "fetch", sql, args)
                if model:
                    return cast(List[model], data)
                return data

    async def fetchiter(self, sql: str, *args, **kwargs):
        output = await self.fetch(sql, *args, **kwargs)
        for row in output:
            yield row

    async def fetchrow(self, sql: str, *args, **kwargs):
        cached = kwargs.get("cached", True)
        model = kwargs.pop("model", None)
        if cached:
            if result := self.cache.get(f"fetchrow {sql} {args}"):
                if model:
                    return cast(model, result)
                return result
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetchrow(sql, *args)
                await self.add_to_cache(data, "fetchrow", sql, args)
                if model:
                    return cast(model, data)
                return data

    async def fetchval(self, sql: str, *args, **kwargs):
        cached = kwargs.get("cached", True)
        if cached:
            if result := self.cache.get(f"fetchval {sql} {args}"):
                return result
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetchval(sql, *args)
                await self.add_to_cache(data, "fetchval", sql, args)
                return data

    async def execute(self, sql: str, *args, **kwargs) -> Optional[Any]:
        if "DELETE" in sql and "giveaways" in sql:
            logger.info(f"executing query {sql} with {args}")
        try:
            table = sql.lower().split("from")[1].split("where")[0]
            await self.search_and_delete(table, args)
        except Exception:
            pass
        try:
            if sql.lower().startswith("update"):
                table = sql.lower().split("set")[0].split("update")[1].strip()
                await self.search_and_delete(table, args)
        except Exception:
            pass
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                return await conn.fetchval(sql, *args)

    async def executemany(self, sql: str, args: Iterable[Sequence]) -> Optional[Any]:
        if result := self.cache.get(f"{sql} {args}"):  # noqa: F841
            self.cache.pop(f"{sql} {args}")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                return await conn.executemany(sql, args)

    async def purge_data(self, column_name: str, value: Any):
        tables = [
            t.table_name
            for t in await self.fetch(
                """SELECT table_name FROM information_schema.columns WHERE table_schema = 'public' AND column_name = $1""",
                column_name,
            )
        ]
        tasks = [
            self.execute(f"""DELETE FROM {t} WHERE {column_name} = $1""", value)
            for t in tables
        ]
        return await asyncio.gather(*tasks)
