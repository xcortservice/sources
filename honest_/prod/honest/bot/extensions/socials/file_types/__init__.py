from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel
from tornado.escape import url_unescape

from .data import data


class FileType(BaseModel):
    name: Optional[str] = None
    mime: Optional[str] = None
    extension: Optional[str] = None


def guess_extension(url: str) -> Optional[FileType]:
    """
    Guesses the file extension and MIME type based on the given URL.

    Args:
        url (str): The URL of the file.

    Returns:
        tuple[str, str]: A tuple containing the guessed MIME type and file extension.
    """
    _url = urlparse(url_unescape(url))
    _path = Path(_url.path)
    _path.name
    mime = data.get(_path.suffix)
    ext = _path.suffix
    return FileType(name=_path.name, mime=mime, extension=ext)
