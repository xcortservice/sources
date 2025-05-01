from io import BytesIO
from typing import Union

import aiohttp
from discord import Member, User
from PIL.Image import Image
from system.worker import offloaded


async def get_dominant_color(u: Union[Member, User, str]) -> str:
    @offloaded
    def get(url: str) -> str:
        from colorgram_rs import get_dominant_color as get_dom

        return get_dom(url)

    if isinstance(
        u,
        (
            Member,
            User,
        ),
    ):
        _ = await get(await u.display_avatar.read())
    else:
        async with aiohttp.ClientSession() as session:
            async with session.get(u) as resp:
                _u = await resp.read()
        _ = await get(_u)
    return f"#{_}"


@offloaded
def get_hash(image: Union[bytes, Image, BytesIO]):
    import random
    import string
    from io import BytesIO

    import imagehash
    from PIL import Image

    def unique_id(lenght: int = 6):
        return "".join(random.choices(string.ascii_letters + string.digits, k=lenght))

    if isinstance(image, bytes):
        image = BytesIO(image)

    result = str(imagehash.average_hash(image=Image.open(image), hash_size=8))
    if result == "0000000000000000":
        return unique_id(16)
    else:
        return result
