from typing import Optional, Dict
from datetime import datetime, timedelta
import aiohttp
from discord.ext.commands import CommandOnCooldown
from collections import defaultdict

class AlexFlipnoteAPI:
    def __init__(self):
        self.base_url = "https://api.alexflipnote.dev"
        self.ratelimits = defaultdict(lambda: {"last_used": None, "uses": 0})

    def _check_ratelimit(self, endpoint: str) -> Optional[float]:
        now = datetime.now()
        rate_info = self.ratelimits[endpoint]

        if rate_info["last_used"]:
            time_passed = now - rate_info["last_used"]
            if time_passed < timedelta(seconds=10):
                if rate_info["uses"] >= 3:
                    retry_after = 10 - time_passed.total_seconds()
                    return retry_after
            else:
                rate_info["uses"] = 0

        rate_info["last_used"] = now
        rate_info["uses"] += 1
        return None

    async def _make_request(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> bytes:
        retry_after = self._check_ratelimit(endpoint)
        if retry_after:
            raise CommandOnCooldown(None, retry_after)

        url = f"{self.base_url}{endpoint}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if not response.ok:
                    raise Exception(f"API request failed with status {response.status}")
                return await response.read()

    async def achievement(self, text: str) -> bytes:
        return await self._make_request("/achievement", {"text": text})

    async def calling(self, text: str) -> bytes:
        return await self._make_request("/calling", {"text": text})

    async def captcha(self, text: str) -> bytes:
        return await self._make_request("/captcha", {"text": text})

    async def didyoumean(self, text: str, text2: str) -> bytes:
        return await self._make_request("/didyoumean", {"text": text, "text2": text2})

    async def supreme(self, text: str) -> bytes:
        return await self._make_request("/supreme", {"text": text})

    async def facts(self, text: str) -> bytes:
        return await self._make_request("/facts", {"text": text})

alexflipnote_api = AlexFlipnoteAPI()