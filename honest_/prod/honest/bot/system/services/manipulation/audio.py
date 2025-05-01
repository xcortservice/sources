import asyncio
from asyncio import sleep
from contextlib import suppress
from dataclasses import asdict
from os import remove

import aiohttp
import whisper
from aiohttp import ClientSession as Session
from discord import Client
from tuuid import tuuid

from ...worker import offloaded


@offloaded
def save_file(filename: str, data: bytes):
    with open(filename, "wb") as file:
        file.write(data)
    return filename


async def download_file(url: str) -> str:
    file_type = get_filetype(url)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.read()
    return await save_file(f"files/audio/{tuuid()}.{file_type}", data)


def get_filetype(url: str) -> str:
    return url.split("/")[-1].split(".")[1].split("?")[0]


class Whisper:
    def __init__(self, model: str = "base"):
        self.model_type = model
        self.model = whisper.load_model(self.model_type)

    def delete(self, filepath: str):
        remove(filepath)
        return True

    async def delete_file(self, filepath: str):
        await sleep(20)
        remove(filepath)
        return True

    def do_whisper(self, filepath: str):
        def do_whisper(fp: str):
            audio = whisper.load_audio(fp)
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
            _, probs = self.model.detect_language(mel)
            options = whisper.DecodingOptions(fp16=False)
            result = whisper.decode(self.model, mel, options)
            self.delete(fp)
            return asdict(result)

        try:
            data = do_whisper(filepath)
            try:
                self.delete(filepath)
            except Exception:
                pass
        except asyncio.CancelledError:
            return None
        return data

    async def run_with_timeout(self, coro, timeout):
        task = asyncio.create_task(coro)
        with suppress(asyncio.TimeoutError):
            return await asyncio.wait_for(task, timeout)

    async def execute_whisper(self, filepath: str):
        try:
            return await self.run_with_timeout(
                self.do_whisper(filepath), timeout=10
            )  # Set timeout as needed
        except asyncio.TimeoutError:
            return None  # Task took too long, handle appropriately

    async def download_file(self, url: str) -> str:
        file_type = get_filetype(url)
        if not hasattr(self, "session"):
            self.session = Session()
        async with self.session.get(url) as response:
            data = await response.read()
        return await self.save_file(data, file_type)

    async def save_file(self, data: bytes, filetype: str):
        filename = tuuid()
        return await save_file(f"{filename}.{filetype}", data)


async def do_transcribe(bot: Client, filepath: str):
    return await do_whisper(bot, filepath)


@offloaded
def do_whisper(bot: Client, filepath: str):
    if not bot.whisper:
        bot.whisper = Whisper()
    import os

    import whisper

    segments = bot.whisper.do_whisper(filepath)
    result = segments["text"]
    try:
        os.remove(filepath)
    except Exception:
        pass
    return result
