import asyncio
import hashlib
import socket
from datetime import datetime
from logging import getLogger
from math import ceil
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import aiohttp
import loguru
from data.config import CONFIG
from discord import Embed
from munch import DefaultMunch, Munch
from pydantic import BaseModel as NiggerModel
from system.classes.database import Record
from system.classes.exceptions import LastFMError
from system.patch.context import Context
from yarl import URL

from .client import CS, BaseModel, ClientSession

logger = getLogger(__name__) and loguru.logger


class LastfmProfileInformation(NiggerModel):
    registered: datetime
    country: Optional[str] = "Unknown"
    age: int
    pro: bool


class LastfmProfileLibrary(NiggerModel):
    scrobbles: int
    artists: int
    albums: int
    tracks: int


class LastfmProfile(NiggerModel):
    url: str
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    information: LastfmProfileInformation
    library: LastfmProfileLibrary


secret = CONFIG["Authorization"]["lastfm"]["secret"]


class Client(CS):
    def __init__(self: "Client", *args, **kwargs):
        super().__init__(
            base_url="http://ws.audioscrobbler.com",
            *args,
            **kwargs,
        )

    async def request(
        self: "Client", slug: Optional[str] = None, **params: Any
    ) -> Munch:
        data: Munch = await super().request(
            "/2.0/",
            params={
                "api_key": CONFIG["Authorization"]["lastfm"]["default"],
                "format": "json",
                **params,
            },
            slug=slug,
        )
        return data


def ya(data):
    keys = sorted(data.keys())
    param = [k + data[k] for k in keys]
    param = "".join(param) + secret
    api_sig = hashlib.md5(param.encode()).hexdigest()
    return api_sig


def hashRequest(obj, secretKey):
    string = ""
    items = tuple(obj.keys())
    for i in items:
        string += i
        string += obj[i]
    string += secretKey
    stringToHash = string.encode("utf8")
    requestHash = hashlib.md5(stringToHash).hexdigest()
    return requestHash


def sign(method, token):
    string = (
        "api_key"
        + CONFIG["Authorization"]["lastfm"]["login"]
        + "method"
        + method
        + "token"
        + token
        + secret
    )
    return hashlib.md5(string.encode("utf-8")).hexdigest()


async def request(
    session: ClientSession,
    payload: Dict,
    slug: str = None,
    **kwargs,
) -> BaseModel:
    attempts = 0
    payload.pop("autocorrect", 0)
    payload.update(
        {
            "api_key": payload.get("api_key")
            or CONFIG["Authorization"]["lastfm"]["default"],
            "format": "json",
        }
    )
    data = None
    error = None
    while not data:
        try:
            data = await session.request(
                "GET",
                f"http://ws.audioscrobbler.com/2.0/",
                params=payload,
                **kwargs,
            )
            if data:
                break
            else:
                raise ValueError()
        except Exception as e:
            logger.info(f"request attempt {attempts+1} returned {data}")
            error = e
            attempts += 1
            if attempts > 5:
                raise error
            await asyncio.sleep(3)

    if not slug:
        return data
    else:
        return getattr(data, slug, None)


def url(value: str) -> URL:
    return URL(f"https://last.fm/music/{value}")


async def api_request(params: dict, slug: str = None, ignore_errors: bool = False):
    """Get json data from the lastfm api."""
    url = "http://ws.audioscrobbler.com/2.0/"
    params["api_key"] = CONFIG["Authorization"]["lastfm"]["default"]
    params["format"] = "json"
    tries = 0
    max_tries = 2
    while True:
        con = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=con) as session:
            async with session.get(url, params=params, verify_ssl=False) as response:
                try:
                    content = await response.json()
                    # logger.info(content)
                except aiohttp.client_exceptions.ContentTypeError:
                    if ignore_errors:
                        return None
                    else:
                        text = await response.text()
                        # logger.info(text)
                        raise LastFMError(error_code=response.status, message=text)

                if content is None:
                    pass
                if response.status == 200 and content.get("error") is None:
                    return content

                else:
                    if int(content.get("error")) == 8:
                        tries += 1
                        if tries < max_tries:
                            continue

                    if ignore_errors:
                        return None
                    else:
                        raise LastFMError(
                            error_code=content.get("error"),
                            message=content.get("message"),
                        )


async def index(
    ctx: Context, user: Union[Munch, Record, str]
) -> AsyncGenerator[Tuple[str, Any], None]:
    session = ClientSession()
    if isinstance(user, Record):
        user = await request(
            session=session,
            payload={
                "method": "user.getinfo",
                "username": user.username if not isinstance(user, str) else user,
            },
            slug="user",
        )

    for library in ("artists", "albums", "tracks"):
        #        pages = ceil(int(getattr(user, f"{library[:-1]}_count", 0)) / 1000)
        #       if pages < 1: page = 1
        # logger.info(pages)
        # logger.info(library)
        items = await api_request(
            params={
                "method": f"user.gettop{library}",
                "limit": 1000,
                "period": "overall",
                "username": user.username if not isinstance(user, str) else user,
            }
        )
        pages = int(items[f"top{library}"]["@attr"]["totalPages"])
        items = items[f"top{library}"][library[:-1]]
        for i, page in enumerate(range(2, pages + 1), start=0):
            p = None
            attempts = 0
            while True:
                p = await api_request(
                    params={
                        "method": f"user.gettop{library}",
                        "username": (
                            user.username if not isinstance(user, str) else user
                        ),
                        "limit": 1000,
                        "page": i + 1,
                        "period": "overall",
                    }
                )
                p = p[f"top{library}"][library.rstrip("s")]
                await asyncio.sleep(5)
                attempts += 1
                if attempts >= 5:
                    break
                if p:
                    break
            if not p:
                p = await api_request
            items.extend(p)

        yield library, items


async def login(session: ClientSession, ctx: Context):
    key = CONFIG["Authorization"]["lastfm"]["login"]
    user_id = ctx.author.id
    token = await request(
        session,
        payload={"method": "auth.getToken", "api_key": key},
        slug="token",
        raise_for={
            404: f"[**{ctx.author.display_name}**]({URL(f'https://last.fm/user/{user_id}')}) is not a valid **Last.fm** account"
        },
    )
    link = f"https://www.last.fm/api/auth?api_key={key}&token={token}&cb=https://api.honest.rocks/lastfm?user_id={user_id}"
    try:
        message = await ctx.author.send(
            embed=Embed(
                color=0xD31F27,
                description=f"""Authorize **honest** to use your Last.fm account [here]({link}). Your library's data will be indexed to power the whoknows commands and other commands.\n\nIf you want to remove your account with **honest**, run `lastfm logout` and visit your settings on [Last.fm](https://last.fm/settings/applications/) to unauthorize our application""",
            )
        )
    except:
        await ctx.send("i cant dm u gang open ur dms plz")
        return False
    signature = sign("auth.getSession", token)
    for attempt in range(3):
        await asyncio.sleep(20)
        try:
            if data := await request(
                session,
                payload={
                    "method": "auth.getSession",
                    "token": token,
                    "api_key": key,
                    "api_sig": signature,
                    "format": "json",
                },
                slug="session",
            ):
                logger.info(data)
                await ctx.bot.db.execute(
                    """INSERT INTO lastfm_data (user_id, username, key, token) VALUES($1, $2, $3, $4) ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, key = excluded.key, token = excluded.token""",
                    ctx.author.id,
                    data.name,
                    data.key,
                    token,
                )
                await ctx.bot.db.execute(
                    """
                    INSERT INTO lastfm.config (user_id, username) 
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE
                    SET username = EXCLUDED.username
                    """,
                    ctx.author.id,
                    data.name,
                )
                await message.edit(
                    embed=Embed(
                        color=0xD31F27,
                        description=f"your lastfm username has been set as **{data.name}**",
                    )
                )
                return True
        except Exception as e:
            logger.info(f"lastfm_login raised {e}")
            continue
    return True


async def scrobble(session: ClientSession, ctx: Context, query: str):
    if not (
        data := await ctx.bot.db.fetchrow(
            """SELECT * FROM lastfm_data WHERE user_id = $1""", ctx.author.id
        )
    ):
        return

    pass


async def profile(
    session: ClientSession,
    username: str,
) -> LastfmProfile:
    data = await request(
        session,
        payload={
            "method": "user.getInfo",
            "username": username,
        },
        slug="user",
        raise_for={
            404: f"[**{username}**]({URL(f'https://last.fm/user/{username}')}) is not a valid **Last.fm** account"
        },
    )

    return LastfmProfile(
        url=data.url,
        username=data.name,
        display_name=data.realname,
        avatar_url=data.image[-1].text,
        information=LastfmProfileInformation(
            registered=data.registered.text,
            country=(data.country if data.country != "None" else "Unknown"),
            age=data.age,
            pro=data.subscriber == "1",
        ),
        library=LastfmProfileLibrary(
            scrobbles=data.playcount,
            artists=data.artist_count,
            albums=data.artist_count,
            tracks=data.track_count,
        ),
    )
