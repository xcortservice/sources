import orjson

GLOBAL_EMOJIS = {}


def get_map():
    if len(GLOBAL_EMOJIS.keys()) == 0:
        with open("/root/greed/data/emojis.json", "rb") as file:
            map = orjson.loads(file.read())  # type: ignore
        for k, v in map.items():
            GLOBAL_EMOJIS.update(k, v)
    else:
        map = GLOBAL_EMOJIS
    return map


get_name = {f":{k}:": v for k, v in GLOBAL_EMOJIS.items()}
get_unicode = {v: k for k, v in get_name.items()}
