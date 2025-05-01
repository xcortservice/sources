from typing import Union, List, Any
import os
from datetime import timedelta
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from greed.framework.tools import offloaded
import logging

logger = logging.getLogger("greed/plugins/information")

@offloaded
def get_timezone(location: str) -> str:
    geolocator = Nominatim(user_agent="Greed-Bot")
    location = geolocator.geocode(location)
    if location is None:
        raise ValueError("Location not found")
    tf = TimezoneFinder()
    timezone = tf.timezone_at(lng=location.longitude, lat=location.latitude)
    if timezone is None:
        raise ValueError("Timezone not found for the given location")
    logger.info(timezone)
    return timezone

class plural:
    def __init__(self, value: Union[int, str, List[Any]], number: bool = True, md: str = ""):
        self.value: int = len(value) if isinstance(value, list) else (int(value.split(" ", 1)[-1]) if value.startswith(("CREATE", "DELETE")) else int(value)) if isinstance(value, str) else value
        self.number: bool = number
        self.md: str = md

    def __format__(self, format_spec: str) -> str:
        v = self.value
        singular, sep, plural = format_spec.partition("|")
        plural = plural or f"{singular}s"
        result = f"{self.md}{v:,}{self.md} " if self.number else ""
        result += plural if abs(v) != 1 else singular
        return result

def get_lines():
    lines = 0
    for directory in [x[0] for x in os.walk("./") if ".git" not in x[0]]:
        for file in os.listdir(directory):
            if file.endswith(".py"):
                lines += len(open(f"{directory}/{file}", "r").read().splitlines())
    return lines

def humanize_timedelta(dt):
    timedelta_str = []
    if dt.days:
        days = dt.days
        timedelta_str.append(f'{days} day{"s" if days > 1 else ""}')
        dt -= timedelta(days=days)
    seconds = dt.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours:
        timedelta_str.append(f'{hours} hour{"s" if hours > 1 else ""}')
    if minutes:
        timedelta_str.append(f'{minutes} minute{"s" if minutes > 1 else ""}')
    if seconds:
        timedelta_str.append(f'{seconds} second{"s" if seconds > 1 else ""}')
    return ", ".join(timedelta_str)