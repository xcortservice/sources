import pytz
from discord.ext import commands
from system.patch.context import Context
from system.worker import offloaded


@offloaded
def get_timezone(location: str) -> str:
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder

    obj = TimezoneFinder()
    geolocator = Nominatim(user_agent="Honest.rocks")
    lad = location
    location = geolocator.geocode(lad)
    obj = TimezoneFinder()
    result = obj.timezone_at(lng=location.longitude, lat=location.latitude)
    return result


class Timezone(commands.Converter):
    async def convert(self, ctx: Context, argument: str):
        try:
            timezone = pytz.timezone(argument)
            return timezone
        except Exception:
            try:
                timezone = pytz.timezone(await get_timezone(argument))
                return timezone
            except Exception:
                raise commands.CommandError(
                    f"No timezone found from query `{argument[:25]}`"
                )
