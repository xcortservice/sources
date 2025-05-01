from typing import Optional, Dict
from datetime import datetime, timedelta
import aiohttp
from discord.ext.commands import CommandOnCooldown
from collections import defaultdict

class PopcatAPI:
    def __init__(self):
        self.base_url = "https://api.popcat.xyz"
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

    async def drip(self, image_url: str) -> bytes:
        return await self._make_request("/drip", {"image": image_url})

    async def gun(self, image_url: str) -> bytes:
        return await self._make_request("/gun", {"image": image_url})

    async def wanted(self, image_url: str) -> bytes:
        return await self._make_request("/wanted", {"image": image_url})

    async def alert(self, text: str) -> bytes:
        return await self._make_request("/alert", {"text": text})

    async def pooh(self, text1: str, text2: str) -> bytes:
        return await self._make_request("/pooh", {"text1": text1, "text2": text2})

    async def drake(self, text1: str, text2: str) -> bytes:
        return await self._make_request("/drake", {"text1": text1, "text2": text2})

    async def oogway(self, text: str) -> bytes:
        return await self._make_request("/oogway", {"text": text})

    async def sadcat(self, text: str) -> bytes:
        return await self._make_request("/sadcat", {"text": text})

    async def ship(self, image1: str, image2: str) -> bytes:
        return await self._make_request("/ship", {"user1": image1, "user2": image2})

popcat_api = PopcatAPI()