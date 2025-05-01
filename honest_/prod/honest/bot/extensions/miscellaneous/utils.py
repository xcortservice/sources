from system.worker import offloaded


@offloaded
def tts(text: str) -> bytes:
    """Explanation:
    Due to dask not supporting complex objects as return types and aiogtts not actually being asynchronous just being threaded (possible region for a thread leak)
    I am doing it this way. If i find a better way before ceasing development I will be sure to implement it
    """
    from io import BytesIO

    from gtts import gTTS  # type: ignore

    gtts = gTTS(text=text)
    buffer = BytesIO()
    gtts.write_to_fp(buffer)
    buffer.seek(0)
    return buffer.read()
