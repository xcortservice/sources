from asyncio import BoundedSemaphore, exceptions, sleep, wait_for
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

from aiohttp import ClientSession
from discord import File
from playwright.async_api import async_playwright
from tools import lock

from system.classes.exceptions import ConcurrencyLimit, NSFWDetection
from .nsfw import ImageModeration

SCREENSHOT_TIMEOUT = 0.2
CONCURRENCY_LIMIT = 5
SCREENSHOT_SEMAPHORE = BoundedSemaphore(5)
CACHE = {}


async def check_image(query: Union[bytes, str]):
    url = "https://api.sightengine.com/1.0/check.json"
    params = {
        "models": "nudity-2.1,weapon,recreational_drug,medical,offensive,text-content,face-attributes,gore-2.0,violence,self-harm",
        "api_user": "1398642624",
        "api_secret": "faUxfR48eGjHprUhwc6ktachGaE8Mr4V",
    }
    data = None
    async with ClientSession() as session:
        if isinstance(query, str):
            params["url"] = query
            async with session.get(url, params=params) as req:
                data = await req.json()
        else:
            request_data = {"media": query}
            async with session.post(url, params=params, data=request_data) as req:
                data = await req.json()
    return ImageModeration(**data)


async def get_screenshot(url: str, safe: Optional[bool] = True, **kwargs: Any) -> bytes:
    if not url.startswith("http"):
        url = f"https://{url}"
    wait: int = kwargs.pop("wait", 0)
    full_page: bool = kwargs.pop("full_page", False)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        await page.goto(
            url, wait_until=kwargs.pop("wait_until", "domcontentloaded"), **kwargs
        )
        await sleep(wait)
        to_check = str(await page.content()).lower().split(" ")
        if safe is True and any(
            (
                "xx" in to_check,
                "xxx" in to_check,
                "porn" in to_check,
                "sex" in to_check,
                "dick" in to_check,
                "cock" in to_check,
                "pussy" in to_check,
                "vagina" in to_check,
                "cum" in to_check,
                "pornhub" in to_check,
                "orgasm" in to_check,
                "gore" in to_check,
            )
        ):
            raise NSFWDetection(f"NSFW Content Detected on webpage of `{url}`")
        if cache := CACHE.get(f"{url}-{'-'.join(str(k) for k in kwargs.keys())}"):
            screenshot = cache
        screenshot = await page.screenshot(animations="disabled", full_page=full_page)
        await page.close()
    await p.stop()
    return screenshot


async def screenshot(url: str, safe: Optional[bool] = True, **kwargs: Any):
    """_summary_

        uses a bound semaphore to limit concurrency of
        screenshotting whilst retaining speed and efficiency
        in the memory namespace

    Args:
        url (str): _description_
        safe (Optional[bool], optional): _description_. Defaults to True.

    Raises:
        ConcurrencyLimit: _description_
        NSFWDetection: _description_

    Returns:
        _type_: _description_
    """
    try:
        await wait_for(SCREENSHOT_SEMAPHORE.acquire(), timeout=SCREENSHOT_TIMEOUT)
    except TimeoutError:
        raise ConcurrencyLimit(
            "Too many concurrent screenshot requests, please try again later"
        )
    except exceptions.TimeoutError:
        raise ConcurrencyLimit(
            "Too many concurrent screenshot requests, please try again later"
        )
    screenshot = await get_screenshot(url, safe, **kwargs)
    if safe:
        check = await check_image(screenshot)
        if check.nsfw:
            raise NSFWDetection(f"NSFW Content Detected on webpage of `{url}`")
    return File(fp=BytesIO(screenshot), filename="screenshot.png")
