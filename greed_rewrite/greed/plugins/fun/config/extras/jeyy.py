from typing import Optional, Dict
from datetime import datetime, timedelta
import aiohttp
from collections import defaultdict
from discord.ext.commands import CommandOnCooldown

class JeyyAPI:
    def __init__(self):
        self.base_url = "https://api.jeyy.xyz/v2"
        self.headers = {"Authorization": f"Bearer 74PJ0CPO6COJ6C9O6OPJGD1I70OJC.CLR6IORK.lkpD588_z_FMB40-Nl6L1w"}
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
            async with session.get(
                url, headers=self.headers, params=params
            ) as response:
                if not response.ok:
                    raise Exception(f"API request failed with status {response.status}")
                return await response.read()

    async def ace(self, name: str, side: str, text: str) -> bytes:
        return await self._make_request("/image/ace", {
            "name": name,
            "side": side,
            "text": text
        })

    async def scrapbook(self, text: str) -> bytes:
        return await self._make_request("/image/scrapbook", {"text": text})

    async def _process_image(self, endpoint: str, image_url: str) -> bytes:
        return await self._make_request(endpoint, {"image_url": image_url})

    async def three_d(self, image_url: str) -> bytes:
        return await self._process_image("/image/3d", image_url)

    async def ads(self, image_url: str) -> bytes:
        return await self._process_image("/image/ads", image_url)

    async def bayer(self, image_url: str) -> bytes:
        return await self._process_image("/image/bayer", image_url)

    async def bevel(self, image_url: str) -> bytes:
        return await self._process_image("/image/bevel", image_url)

    async def billboard(self, image_url: str) -> bytes:
        return await self._process_image("/image/billboard", image_url)

    async def blocks(self, image_url: str) -> bytes:
        return await self._process_image("/image/blocks", image_url)

    async def boil(self, image_url: str) -> bytes:
        return await self._process_image("/image/boil", image_url)

    async def bomb(self, image_url: str) -> bytes:
        return await self._process_image("/image/bomb", image_url)

    async def bonks(self, image_url: str) -> bytes:
        return await self._process_image("/image/bonks", image_url)

    async def burn(self, image_url: str) -> bytes:
        return await self._process_image("/image/burn", image_url)

    async def canny(self, image_url: str) -> bytes:
        return await self._process_image("/image/canny", image_url)

    async def cartoon(self, image_url: str) -> bytes:
        return await self._process_image("/image/cartoon", image_url)

    async def cinema(self, image_url: str) -> bytes:
        return await self._process_image("/image/cinema", image_url)

    async def clock(self, image_url: str) -> bytes:
        return await self._process_image("/image/clock", image_url)

    async def console(self, image_url: str) -> bytes:
        return await self._process_image("/image/console", image_url)

    async def contour(self, image_url: str) -> bytes:
        return await self._process_image("/image/contour", image_url)

    async def cow(self, image_url: str) -> bytes:
        return await self._process_image("/image/cow", image_url)

    async def cracks(self, image_url: str) -> bytes:
        return await self._process_image("/image/cracks", image_url)

    async def cube(self, image_url: str) -> bytes:
        return await self._process_image("/image/cube", image_url)

    async def dither(self, image_url: str) -> bytes:
        return await self._process_image("/image/dither", image_url)

    async def dizzy(self, image_url: str) -> bytes:
        return await self._process_image("/image/dizzy", image_url)

    async def earthquake(self, image_url: str) -> bytes:
        return await self._process_image("/image/earthquake", image_url)

    async def emojify(self, image_url: str) -> bytes:
        return await self._process_image("/image/emojify", image_url)

    async def endless(self, image_url: str) -> bytes:
        return await self._process_image("/image/endless", image_url)

    async def equations(self, image_url: str) -> bytes:
        return await self._process_image("/image/equations", image_url)

    async def explicit(self, image_url: str) -> bytes:
        return await self._process_image("/image/explicit", image_url)

    async def fall(self, image_url: str) -> bytes:
        return await self._process_image("/image/fall", image_url)

    async def fan(self, image_url: str) -> bytes:
        return await self._process_image("/image/fan", image_url)

    async def fire(self, image_url: str) -> bytes:
        return await self._process_image("/image/fire", image_url)

    async def flag(self, image_url: str) -> bytes:
        return await self._process_image("/image/flag", image_url)

    async def flush(self, image_url: str) -> bytes:
        return await self._process_image("/image/flush", image_url)

    async def gallery(self, image_url: str) -> bytes:
        return await self._process_image("/image/gallery", image_url)

    async def gameboy(self, image_url: str) -> bytes:
        return await self._process_image("/image/gameboy_camera", image_url)

    async def glitch(self, image_url: str) -> bytes:
        return await self._process_image("/image/glitch", image_url)

    async def globe(self, image_url: str) -> bytes:
        return await self._process_image("/image/globe", image_url)

    async def half_invert(self, image_url: str) -> bytes:
        return await self._process_image("/image/half_invert", image_url)

    async def heart_locket(self, image_url1: str, image_url2: str) -> bytes:
        return await self._make_request(
            "/image/heart_locket", {"image_url": image_url1, "image_url_2": image_url2}
        )

    async def hearts(self, image_url: str) -> bytes:
        return await self._process_image("/image/hearts", image_url)

    async def infinity(self, image_url: str) -> bytes:
        return await self._process_image("/image/infinity", image_url)

    async def ipcam(self, image_url: str) -> bytes:
        return await self._process_image("/image/ipcam", image_url)

    async def kanye(self, image_url: str) -> bytes:
        return await self._process_image("/image/kanye", image_url)

    async def knit(self, image_url: str) -> bytes:
        return await self._process_image("/image/knit", image_url)

    async def lamp(self, image_url: str) -> bytes:
        return await self._process_image("/image/lamp", image_url)

    async def laundry(self, image_url: str) -> bytes:
        return await self._process_image("/image/laundry", image_url)

    async def layers(self, image_url: str) -> bytes:
        return await self._process_image("/image/layers", image_url)

    async def letters(self, image_url: str) -> bytes:
        return await self._process_image("/image/letters", image_url)

    async def lines(self, image_url: str) -> bytes:
        return await self._process_image("/image/lines", image_url)

    async def liquefy(self, image_url: str) -> bytes:
        return await self._process_image("/image/liquefy", image_url)

    async def logoff(self, image_url: str) -> bytes:
        return await self._process_image("/image/logoff", image_url)

    async def lsd(self, image_url: str) -> bytes:
        return await self._process_image("/image/lsd", image_url)

    async def magnify(self, image_url: str) -> bytes:
        return await self._process_image("/image/magnify", image_url)

    async def matrix(self, image_url: str) -> bytes:
        return await self._process_image("/image/matrix", image_url)

    async def melt(self, image_url: str) -> bytes:
        return await self._process_image("/image/melt", image_url)

    async def minecraft(self, image_url: str) -> bytes:
        return await self._process_image("/image/minecraft", image_url)

    async def neon(self, image_url: str) -> bytes:
        return await self._process_image("/image/neon", image_url)

    async def optics(self, image_url: str) -> bytes:
        return await self._process_image("/image/optics", image_url)

    async def painting(self, image_url: str) -> bytes:
        return await self._process_image("/image/painting", image_url)

    async def paparazzi(self, image_url: str) -> bytes:
        return await self._process_image("/image/paparazzi", image_url)

    async def patpat(self, image_url: str) -> bytes:
        return await self._process_image("/image/patpat", image_url)

    async def pattern(self, image_url: str) -> bytes:
        return await self._process_image("/image/pattern", image_url)

    async def phase(self, image_url: str) -> bytes:
        return await self._process_image("/image/phase", image_url)

    async def phone(self, image_url: str) -> bytes:
        return await self._process_image("/image/phone", image_url)

    async def plank(self, image_url: str) -> bytes:
        return await self._process_image("/image/plank", image_url)

    async def plates(self, image_url: str) -> bytes:
        return await self._process_image("/image/plates", image_url)

    async def poly(self, image_url: str) -> bytes:
        return await self._process_image("/image/poly", image_url)

    async def print(self, image_url: str) -> bytes:
        return await self._process_image("/image/print", image_url)

    async def pyramid(self, image_url: str) -> bytes:
        return await self._process_image("/image/pyramid", image_url)

    async def radiate(self, image_url: str) -> bytes:
        return await self._process_image("/image/radiate", image_url)

    async def rain(self, image_url: str) -> bytes:
        return await self._process_image("/image/rain", image_url)

    async def reflection(self, image_url: str) -> bytes:
        return await self._process_image("/image/reflection", image_url)

    async def ripped(self, image_url: str) -> bytes:
        return await self._process_image("/image/ripped", image_url)

    async def ripple(self, image_url: str) -> bytes:
        return await self._process_image("/image/ripple", image_url)

    async def roll(self, image_url: str) -> bytes:
        return await self._process_image("/image/roll", image_url)

    async def sensitive(self, image_url: str) -> bytes:
        return await self._process_image("/image/sensitive", image_url)

    async def shear(self, image_url: str) -> bytes:
        return await self._process_image("/image/shear", image_url)

    async def shine(self, image_url: str) -> bytes:
        return await self._process_image("/image/shine", image_url)

    async def shock(self, image_url: str) -> bytes:
        return await self._process_image("/image/shock", image_url)

    async def shoot(self, image_url: str) -> bytes:
        return await self._process_image("/image/shoot", image_url)

    async def shred(self, image_url: str) -> bytes:
        return await self._process_image("/image/shred", image_url)

    async def slice(self, image_url: str) -> bytes:
        return await self._process_image("/image/slice", image_url)

    async def soap(self, image_url: str) -> bytes:
        return await self._process_image("/image/soap", image_url)

    async def spin(self, image_url: str) -> bytes:
        return await self._process_image("/image/spin", image_url)

    async def stereo(self, image_url: str) -> bytes:
        return await self._process_image("/image/stereo", image_url)

    async def stretch(self, image_url: str) -> bytes:
        return await self._process_image("/image/stretch", image_url)

    async def tiles(self, image_url: str) -> bytes:
        return await self._process_image("/image/tiles", image_url)

    async def tunnel(self, image_url: str) -> bytes:
        return await self._process_image("/image/tunnel", image_url)

    async def tv(self, image_url: str) -> bytes:
        return await self._process_image("/image/tv", image_url)

    async def wall(self, image_url: str) -> bytes:
        return await self._process_image("/image/wall", image_url)

    async def warp(self, image_url: str) -> bytes:
        return await self._process_image("/image/warp", image_url)

    async def wave(self, image_url: str) -> bytes:
        return await self._process_image("/image/wave", image_url)

    async def wiggle(self, image_url: str) -> bytes:
        return await self._process_image("/image/wiggle", image_url)

    async def zonk(self, image_url: str) -> bytes:
        return await self._process_image("/image/zonk", image_url)


jeyy_api = JeyyAPI()