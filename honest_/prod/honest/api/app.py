import asyncio
import socket
from asyncio import ensure_future, sleep
from base64 import b64decode
from contextlib import asynccontextmanager
from typing import Any, Optional

import orjson
import uvicorn
from aiohttp import ClientSession
from honestredis.client import HonestRedis
from ext.github import GithubPushEvent
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (FileResponse, JSONResponse, ORJSONResponse, PlainTextResponse, Response)
from loguru import logger
from tuuid import tuuid

WEBHOOK_ADDRESS = "http://127.0.0.1:1275"
ADDRESS = {"host": "127.0.0.1", "port": 1274}
DOMAIN = "honest.rocks"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await HonestRedis.from_url()
    app.state.statistics = None
    app.state._commands = None
    yield
    app.state.redis.close()


app = FastAPI(title="API", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_time_image_bytes(tz: str):
    import io

    import arrow
    from PIL import Image, ImageDraw, ImageFont
    from pytz import timezone

    # Get the current time in EST
    est = timezone(tz)
    current_time = arrow.now(est).format("h:mm A")

    # Create an image with Pillow
    img_width, img_height = 400, 400
    background_color = "black"
    text_color = "white"

    # Create a blank image
    image = Image.new("RGB", (img_width, img_height), color=background_color)
    draw = ImageDraw.Draw(image)

    # Load a default font
    try:
        font = ImageFont.truetype("Ariel.ttf", size=40)
    except IOError:
        font = ImageFont.load_default(size=40)

    # Calculate text size and position it in the center
    text_bbox = draw.textbbox((0, 0), current_time, font=font)
    text_width = text_bbox[2] - text_bbox[0] * 2
    text_height = text_bbox[3] - text_bbox[1] * 2
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2

    # Draw the text on the image
    draw.text((text_x, text_y), current_time, fill=text_color, font=font)

    # Save the image to a bytes buffer
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    return img_bytes.getvalue()


def check_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except socket.error:
            return True  # Port is in use
    return False  # Port is available


async def dump_commandsXD(delay: Optional[int] = None):
    if delay:
        await sleep(delay)
    commands = orjson.loads(await app.state.redis.get("commands"))
    return commands


@app.get("/")
async def index():
    if not app.state._commands or len(list(app.state._commands.keys())) == 1:
        app.state._commands = await dump_commandsXD()
    ensure_future(dump_commandsXD(500))
    return JSONResponse(content=app.state._commands)


async def forward_payload(data: Any, headers: dict):
    process = await asyncio.create_subprocess_shell(
        "cd .. ; cd bot ; git pull origin main",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait until the process finishes
    stdout, stderr = await process.communicate()

    # Check the return code
    if process.returncode == 0:
        total_changes = []
        total_changes.extend(data.head_commit.added)
        total_changes.extend(data.head_commit.removed)
        total_changes.extend(data.head_commit.modified)
        for change in total_changes:
            if "system" in change.lower():
                logger.info(
                    f"Reloading due to a new commit being added from {data.head_commit.author.name}"
                )


@app.post("/github")
async def github(request: Request):
    payload = await request.json()
    async with ClientSession() as session:
        async with session.post(f"{WEBHOOK_ADDRESS}/github", json=payload) as response:
            data = await response.json()
    return JSONResponse(content=data, status_code=200)


async def redump_statistics(delay: Optional[int] = None):
    if delay:
        await sleep(delay)
    app.state.statistics = orjson.loads(await app.state.redis.get("statistics"))
    return app.state.statistics


@app.get("/statistics")
async def statistics_():
    if not app.state.statistics:
        await redump_statistics()
    ensure_future(redump_statistics(60))
    return JSONResponse(content=app.state.statistics)


@app.get("/avatar")
async def avatar():
    async with ClientSession() as session:
        async with session.get(f"{WEBHOOK_ADDRESS}/avatar") as response:
            data = await response.read()
            content_type = response.content_type
    return Response(content=data, media_type=content_type)


@app.get("/shards")
async def shards():
    async with ClientSession() as session:
        async with session.get(f"{WEBHOOK_ADDRESS}/shards") as response:
            data = await response.json()
    return JSONResponse(content=data)


@app.get("/status")
async def status():
    async with ClientSession() as session:
        async with session.get(f"{WEBHOOK_ADDRESS}/status") as response:
            data = await response.json()
    return JSONResponse(content=data)


@app.get("/logs/{identifier}")
async def message_logs(identifier: str):
    async with ClientSession() as session:
        async with session.get(f"{WEBHOOK_ADDRESS}/logs/{identifier}") as response:
            data = await response.json()
            status = response.status
    return JSONResponse(content=data, status_code=status)


@app.get("/asset/{path}")
async def asset(path: str):
    if not (entry := await app.state.redis.get(path.split(".")[0])):
        raise HTTPException(status_code=404, detail="File not found")
    image_data, content_type = orjson.loads(entry)
    return Response(content=image_data, media_type=content_type)


async def add_asset(b64_string: str, **kwargs):
    content_type, base64_str = (
        b64_string.split(",")[0].split(":")[1].split(";")[0],
        b64_string.split(",")[1],
    )
    image_data = b64decode(base64_str)
    name = kwargs.pop("name", tuuid())
    await app.state.redis.set(name, orjson.dumps([image_data, content_type]), ex=500)
    return f"https://api.{app.state.domain}/asset/{name}"


@app.get("/clock.png")
async def clock(timezone: Optional[str] = "US/Eastern"):
    return Response(content=get_time_image_bytes(timezone), media_type="image/png")


async def run():
    config = uvicorn.Config(
        app,
        **ADDRESS,
        log_level="info",
        proxy_headers=True,
        access_log=True,
        workers=10,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(run())
