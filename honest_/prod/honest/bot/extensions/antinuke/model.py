import json
from typing import List, Literal, Optional

from data.config import CONFIG
from pydantic import BaseModel, ValidationError


class Module(BaseModel):
    status: Optional[bool] = False
    punishment: Optional[Literal["ban", "kick", "stripstaff", None]] = None
    threshold: Optional[int] = 3
    command: Optional[bool] = False

    @property
    def emoji(self) -> str:
        return CONFIG["emojis"]["success"] if self.status else CONFIG["emojis"]["fail"]


class Permission(BaseModel):
    type: Literal["grant", "remove"]
    punishment: Literal["ban", "kick", "stripstaff"]
    permission: str


class Configuration(BaseModel):
    guild_id: Optional[int] = None
    whitelist: List[int] = list()
    admins: List[int] = list()

    botadd: Module = Module()
    webhook: Module = Module()
    emoji: Module = Module()
    ban: Module = Module()
    kick: Module = Module()
    channel: Module = Module()
    role: Module = Module()
    permissions: List[Permission] = list()

    def __init__(self, **data):
        # Convert strings to dictionaries if they represent a Module
        for key in ["botadd", "webhook", "emoji", "ban", "kick", "channel", "role"]:
            if isinstance(data.get(key), str):
                try:
                    # Attempt to load the string as JSON, assuming it's serialized data
                    data[key] = Module(**json.loads(data[key]))
                except json.JSONDecodeError:
                    raise ValidationError(
                        f"Expected JSON string for field '{key}', got: {data[key]}"
                    )

        super().__init__(**data)
