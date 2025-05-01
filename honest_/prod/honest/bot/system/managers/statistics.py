from pathlib import Path

from discord import Client
from pydantic import BaseModel


class Statistics(BaseModel):
    files: str
    imports: str
    lines: str
    classes: str
    functions: str
    coroutines: str


async def get_statistics(bot: Client):
    p = Path("./")
    imp = cm = cr = fn = cl = ls = fc = 0
    for f in p.rglob("*.py"):
        if str(f).startswith("venv"):
            continue
        if str(f).startswith("discord"):
            continue
        fc += 1
        with f.open() as of:
            for _l in of.readlines():
                ll = _l.strip()
                if ll.startswith("class"):
                    cl += 1
                if ll.startswith("def"):
                    fn += 1
                if ll.startswith("import"):
                    imp += 1
                if ll.startswith("from"):
                    imp += 1
                if ll.startswith("async def"):
                    cr += 1
                if "#" in ll:
                    cm += 1
                ls += 1
    data = {
        "files": f"{fc:,}",
        "imports": f"{imp:,}",
        "lines": f"{ls:,}",
        "classes": f"{cl:,}",
        "functions": f"{fn:,}",
        "coroutines": f"{cr:,}",
    }
    return Statistics(**data)
