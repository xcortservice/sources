from json import dumps, loads
from typing import Any, Dict, Optional, Union

import aiohttp
from aiohttp import ClientSession as DefaultClientSession
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from data.config import CONFIG as config
from discord.ext.commands import CommandError
from munch import DefaultMunch
from pydantic import BaseModel, create_model
from yarl import URL


class CS(DefaultClientSession):
    def __init__(self, *args, **kwargs):
        super().__init__(
            timeout=ClientTimeout(total=15),
            raise_for_status=True,
            *args,
            **kwargs,
        )

    async def request(self, method, url=None, *args, **kwargs) -> Any:
        if url is None:
            url = method
            method = "GET"

        slug: Optional[str] = kwargs.pop("slug", None)
        response = await super().request(
            method=method,
            url=URL(url),
            *args,
            **kwargs,
        )

        if response.content_type == "text/plain":
            return await response.text()

        elif response.content_type.startswith(("image/", "video/", "audio/")):
            return await response.read()

        elif response.content_type == "text/html":
            return BeautifulSoup(await response.text(), "html.parser")

        elif response.content_type in (
            "application/json",
            "application/octet-stream",
            "text/javascript",
        ):
            try:
                data: Dict = await response.json(content_type=None)
            except Exception:
                return response

            munch = DefaultMunch.fromDict(data)
            if slug:
                for path in slug.split("."):
                    if path.isnumeric() and isinstance(munch, list):
                        try:
                            munch = munch[int(path)]
                        except IndexError:
                            pass

                    munch = getattr(munch, path, munch)

            return munch

        return response


def create_model_from_dict(data: Union[dict, list]) -> BaseModel:
    if "data" in data:
        data = data["data"]

    raw = dumps(data).replace("#text", "text")
    data = loads(raw)

    if isinstance(data, dict):
        field_definitions = {}

        for key, value in data.items():
            if isinstance(value, dict):
                field_definitions[key] = (create_model_from_dict(value), ...)

            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    field_definitions[key] = (
                        list[create_model_from_dict(value[0])],
                        ...,
                    )
                else:
                    field_definitions[key] = (list, ...)

            else:
                field_definitions[key] = (value.__class__, ...)

    elif isinstance(data, list):
        definitions = []

        for value in data:
            definitions.append(create_model_from_dict(value))

        return definitions
    else:
        raise TypeError(f"Unexpected type: {type(data)}")

    model = create_model("ResponseModel", **field_definitions)

    return model(**data)


class ClientSession(aiohttp.ClientSession):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            timeout=ClientTimeout(total=15),
            raise_for_status=True,
        )

    async def request(self, *args, **kwargs) -> Union[aiohttp.ClientResponse, dict]:
        args = list(args)
        args[1] = URL(args[1])
        raise_for = kwargs.pop("raise_for", {})
        if kwargs.pop("proxy", False):
            kwargs["params"] = {"url": str(args[1]), **kwargs.get("params", {})}
            args[1] = URL(config.proxy_url)

        args = tuple(args)

        try:
            response = await super().request(*args, **kwargs)
        except aiohttp.ClientResponseError as e:
            if error_message := raise_for.get(e.status):
                raise CommandError(error_message)

            raise

        if response.content_type == "text/html":
            return BeautifulSoup(await response.text(), "html.parser")

        elif response.content_type in ("application/json", "text/javascript"):
            return create_model_from_dict(await response.json(content_type=None))

        elif response.content_type.startswith(("image/", "video/", "audio/")):
            return await response.read()

        return response
