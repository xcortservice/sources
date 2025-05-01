from re import Match, compile, sub, DOTALL  # noqa: F401
from typing import Any, Callable, Dict, Optional, Union
from discord.ext.commands import CommandError, Context, Converter
from discord import Embed, Guild, ActionRow, User, Member, Message, ButtonStyle  # noqa: F401
from discord.abc import GuildChannel
from aiohttp import ClientSession
from typing_extensions import Type, NoReturn, Self
from discord.ui import View, Button
from data.variables import EMOJI_REGEX, DEFAULT_EMOJIS
from discord.utils import format_dt
import discord
import regex
import re
import datetime
from .exceptions import EmbedError
from loguru import logger

def escape_md(s):
    transformations = {
        regex.escape(c): "\\" + c for c in ("*", "`", "__", "~", "\\", "||")
    }

    def replace(obj):
        return transformations.get(regex.escape(obj.group(0)), "")

    pattern = regex.compile("|".join(transformations.keys()))
    return pattern.sub(replace, s)

image_link = compile(
    r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/\/=]*(?:\.png|\.jpe?g|\.gif|\.jpg|))"
)

def embed_to_code(embed: Union[dict, Message, Embed], message: Optional[str] = None, escaped: Optional[bool] = True) -> dict:
    """Converts an embed to a code block."""
    code = "{embed}"
    msg = None
    if isinstance(embed, dict):
        message = embed.pop("message", embed.pop("content", message))
        embed = Embed.from_dict(embed)
    elif isinstance(embed, Message):
        msg = embed
        message = message or str(embed.content)
        embed = embed.embeds[0]
    if msg:
        for component in msg.components:
            if isinstance(component, (Button, discord.components.Button)):
                if component.url:
                    substeps = "$v{button: "
                    if component.label:
                        substeps += f"{component.label} && "
                    if component.emoji:
                        substeps += f"{str(component.emoji)} && "
                    substeps += f"{component.url}}}"
                    code += substeps
            elif isinstance(component, ActionRow):
                for child in component.children:
                    if isinstance(child, (Button, discord.components.Button)):
                        if child.url:
                            substeps = "$v{button: "
                            if child.label:
                                substeps += f"{child.label} && "
                            if child.emoji:
                                substeps += f"{str(child.emoji)} && "
                            substeps += f"{child.url}}}"
                            code += substeps
                        
    if message:
        code += f"$v{{content: {message}}}"
    if embed.title:
        code += f"$v{{title: {embed.title}}}"
    if embed.description:
        code += f"$v{{description: {embed.description}}}"
    if embed.timestamp:
        code += "$v{timestamp: true}"
    if embed.url:
        code += f"$v{{url: {embed.url}}}"
    if fields := embed.fields:
        for field in fields:
            inline = " && inline" if field.inline else ""
            code += f"$v{{field: {field.name} && {field.value}{inline}}}"
    if embed.footer:
        substeps = ""
        text = embed.footer.text or ""
        icon_url = embed.footer.icon_url or ""
        substeps += f"footer: {embed.footer.text}"
        if icon_url:
            substeps += f" && {icon_url}"
        code += f"$v{{{substeps}}}"
    if embed.author:
        substeps = ""
        icon_url = embed.author.icon_url or ""
        url = embed.author.url or None
        substeps += f"author: {embed.author.name}"
        if url:
            substeps += f" && {url}"
        if icon_url:
            substeps += f" && {icon_url}"
        code += "$v{"+ substeps + "}"
    if image_url := embed.image.url:
        code += f"$v{{image: {image_url}}}"
    if thumbnail_url := embed.thumbnail.url:
        code += f"$v{{thumbnail: {thumbnail_url}}}"
    if color := embed.color:
        code += f"$v{{color: #{str(color)}}}".replace("##", "#")
    if escaped:
        code = code.replace("```", "`\u200b`\u200b`")
    return code
    

        

def format_plays(amount):
    if amount == 1:
        return "play"
    return "plays"


def ordinal(n):
    n = int(n)
    return "%d%s" % (n, "tsnrhtdd"[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# URL pattern to verify the format
URL_PATTERN = re.compile(
    r"^(https?://)"
    r"([a-zA-Z0-9.-]+)"  # Domain
    r"(\.[a-zA-Z]{2,})"  # TLD
    r"(/.*)?$",          # Path
)

async def is_valid_icon_url(url: str) -> bool:
    # Check if URL format is valid
    if not URL_PATTERN.match(url):
        return False
    
    # Check the Content-Type to ensure it's an allowed image format
    async with ClientSession() as session:
        try:
            async with session.head(url) as response:
                content_type = response.headers.get("Content-Type", "")
                return content_type in ALLOWED_MIME_TYPES
        except Exception as e:
            print(f"Failed to fetch URL: {e}")
            return False



class EmbedConverter(Converter):
    async def convert(self, ctx: Context, code: str) -> Optional[dict]:
        script = Script(code, ctx.author)
        try:
            await script.compile()
        except EmbedError as e:
            await ctx.warning(f"{e.message}")
            raise e
        return await script.send(ctx.channel, return_embed=True)


class Script:
    def __init__(self, template: str, user: Union[Member, User], lastfm_data: dict = {}):
        self.pattern = compile(r"\{([\s\S]*?)\}")  # compile(r"{(.*?)}")
        self.data: Dict[str, Union[Dict, str]] = {
            "embed": {},
        }
        self.compiled = False
        self.replacements = {
            "{user}": str(user),
            "{user.mention}": user.mention,
            "{user.name}": user.name,
            "{user.avatar}": user.display_avatar.url,
            "{user.joined_at}": format_dt(user.joined_at, style="R"),
            "{user.created_at}": format_dt(user.created_at, style="R"),
            "{guild.name}": user.guild.name,
            "{guild.count}": str(user.guild.member_count),
            "{guild.count.format}": ordinal(len(user.guild.members)),
            "{guild.id}": user.guild.id,
            "{guild.created_at}": format_dt(user.guild.created_at, style="R"),
            "{guild.boost_count}": str(user.guild.premium_subscription_count),
            "{guild.booster_count}": str(len(user.guild.premium_subscribers)),
            "{guild.boost_count.format}": ordinal(
                str(user.guild.premium_subscription_count)
            ),
            "{guild.booster_count.format}": ordinal(
                str(user.guild.premium_subscription_count)
            ),
            "{guild.boost_tier}": str(user.guild.premium_tier),
            "{guild.icon}": user.guild.icon.url if user.guild.icon else "",
            "{track}": lastfm_data.get("track", ""),
            "{track.duration}": lastfm_data.get("duration", ""),
            "{artist}": lastfm_data.get("artist", ""),
            "{user}": lastfm_data.get("user", ""),  # noqa: F601
            "{avatar}": lastfm_data.get("avatar", ""),
            "{track.url}": lastfm_data.get("track.url", ""),
            "{artist.url}": lastfm_data.get("artist.url", ""),
            "{scrobbles}": lastfm_data.get("scrobbles", ""),
            "{track.image}": lastfm_data.get("track.image", ""),
            "{username}": lastfm_data.get("username", ""),
            "{artist.plays}": lastfm_data.get("artist.plays", ""),
            "{track.plays}": lastfm_data.get("track.plays", ""),
            "{track.lower}": lastfm_data.get("track.lower", ""),
            "{artist.lower}": lastfm_data.get("artist.lower", ""),
            "{track.hyperlink}": lastfm_data.get("track.hyperlink", ""),
            "{track.hyperlink_bold}": lastfm_data.get("track.hyperlink_bold", ""),
            "{artist.hyperlink}": lastfm_data.get("artist.hyperlink", ""),
            "{artist.hyperlink_bold}": lastfm_data.get("artist.hyperlink_bold", ""),
            "{track.color}": lastfm_data.get("track.color", ""),
            "{artist.color}": lastfm_data.get("artist.color", ""),
            "{date}": lastfm_data.get("date", ""),
            "{whitespace}": "\u200e",
        }
        self.template = self._replace_placeholders(template.replace("`\u200b`\u200b`", "```"))

    def get_color(self, color: str):
        try:
            return int(color, 16)
        except Exception:
            raise EmbedError(f"color `{color[:6]}` not a valid hex color")

    @property
    def components(self) -> Dict[str, Callable[[Any], None]]:
        return {
            "content": lambda value: self.data.update({"content": value}),
            "autodelete": lambda value: self.data.update({"delete_after": int(value)}),
            "url": lambda value: self.data["embed"].update({"url": value}),
            "color": lambda value: self.data["embed"].update(
                {"color": self.get_color(value.replace("#", ""))}
            ),
            "title": lambda value: self.data["embed"].update({"title": value}),
            "description": (
                lambda value: self.data["embed"].update({"description": value})
            ),
            "thumbnail": (
                lambda value: self.data["embed"].update({"thumbnail": {"url": value}})
            ),
            "fields": (lambda value: self.data["embed"].update({"fields": value})),
            "image": (
                lambda value: self.data["embed"].update({"image": {"url": value}})
            ),
            "footer": (
                lambda value: self.data["embed"]
                .setdefault("footer", {})
                .update({"text": value})
            ),
            "author": (
                lambda value: self.data["embed"]
                .setdefault("author", {})
                .update({"name": value})
            ),
        }

    def validate_keys(self: Self):
        data = self.template.split("{")
        for d in data:
            if d != "":
                if not d.endswith("}") and not d.endswith("$v"):
                    missing = "}"
                    raise EmbedError(
                        f"`{d.split(':')[0]}` is missing a `{missing}` at the end"
                    )
        _data = self.template.split("}")
        for _d in _data:
            if _d != "":
                if not _d.startswith("{") and not d.startswith("$v{"):
                    missing = "{"
                    raise EmbedError(
                        f"`{_d.split(':')[0]}` is missing a `{missing}` at the start"
                    )

    def validate_url(self: Self, url: str) -> Optional[bool]:
        import re

        regex_pattern = r"^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+.*$"
        data = bool(re.match(regex_pattern, url))
        if not data:
            raise EmbedError(f"`{url}` is not a valid URL Format")
        return data

    async def validate_image(self: Self, url: str) -> Optional[bool]:
        if not image_link.match(url):
            raise EmbedError(f" 1 `{url}` is not a valid Image URL Format")
        async with ClientSession() as session:
            async with session.request("HEAD", url) as response:
                if int(response.headers.get("Content-Length", 15000)) > 240000000:
                    raise EmbedError(f"`{url}` is to large of a URL")
                if content_type := response.headers.get("Content-Type"):
                    if "image" not in content_type.lower():
                        raise EmbedError(
                            f"`{url}` is not a valid Image URL due to the content type being `{content_type}`"
                        )
                else:
                    raise EmbedError(f"`{url}` is not a valid Image URL")
        return True

    async def validate(self: Self) -> NoReturn:
        DICT = {}
        if thumbnail := self.data.get("embed").get("thumbnail", DICT).get("url"):
            await self.validate_image(thumbnail)
        if image := self.data.get("embed").get("image", DICT).get("url"):
            await self.validate_image(image)
        if author_icon := self.data.get("embed").get("author", DICT).get("icon_url"):
            await self.validate_image(author_icon)
        if footer_icon := self.data.get("embed").get("footer", DICT).get("icon_url"):
            await self.validate_image(footer_icon)
        if author_url := self.data.get("embed").get("author", DICT).get("url"):
            self.validate_url(author_url)
        if embed_url := self.data.get("embed").get("url"):
            self.validate_url(embed_url)
        author = self.data.get("embed").get("author", DICT).get("name", "")
        footer = self.data.get("embed").get("footer", DICT).get("text", "")
        title = self.data.get("embed").get("title", "")
        description = self.data.get("embed").get("description", "")
        fields = self.data.get("embed").get("fields", [])
        if len(author) >= 256:
            raise EmbedError(
                "field `author name` is to long the limit is 256 characters"
            )
        if len(footer) >= 2048:
            raise EmbedError(
                "field `footer text` is to long the limit is 2048 characters"
            )
        if len(description) >= 4096:
            raise EmbedError(
                "field `description` is to long the limit is 4096 characters"
            )
        for f in fields:
            if len(f.get("name", "")) >= 256:
                raise EmbedError("field `name` is to long the limit is 256 characters")
            if len(f.get("value", "")) >= 1024:
                raise EmbedError(
                    "field `value` is to long the limit is 1024 characters"
                )
        if len(title) >= 256:
            raise EmbedError("field `title` is to long the limit is 256 characters")
        if len(self.data.get("content", "")) >= 2000:
            raise EmbedError("field `content` is to long the limit is 2000 characters")
        if len(Embed.from_dict(self.data["embed"])) >= 6000:
            raise EmbedError("field `embed` is to long the limit is 6000 characters")
        keys = [k for k in self.data.get("embed", {}).keys()]
        if len(keys) == 1 and "color" in keys:
            raise EmbedError("A field or description is required if you provide a color")

    def _replace_placeholders(self: Self, template: str) -> str:
        template = (
            template.replace("{embed}", "").replace("$v", "").replace("} {", "}{")
        )
        for placeholder, value in self.replacements.items():
            template = template.replace(placeholder, str(value))
        return template

    async def compile(self: Self) -> None:
        self.template = self.template.replace(r"\n", "\n").replace("\\n", "\n")
        matches = self.pattern.findall(self.template)

        for match in matches:
            parts = match.split(":", 1)
            if len(parts) == 2:
                if parts[0] == "footer" and "&&" in parts[1]:
                    values = parts[1].split("&&")
                    for i, v in enumerate(values, start=1):
                        if i == 1:
                            self.data["embed"]["footer"] = {"text": v.lstrip().rstrip()}
                        elif i == 2:
                            self.data["embed"]["footer"]["url"] = v.lstrip().rstrip()
                        else:
                            self.data["embed"]["footer"][
                                "icon_url"
                            ] = v.lstrip().rstrip()
                elif parts[0] == "author" and "&&" in parts[1]:
                    values = parts[1].split("&&")
                    for i, v in enumerate(values, start=1):
                        if i == 1:
                            self.data["embed"]["author"] = {"name": v.lstrip().rstrip()}
                        elif i == 2:
                            if (
                                ".jpg" in v.lstrip().rstrip()
                                or ".png" in v.lstrip().rstrip()
                                or ".gif" in v.lstrip().rstrip()
                                or ".webp" in v.lstrip().rstrip()
                            ) or await is_valid_icon_url(v.lstrip().rstrip()):
                                self.data["embed"]["author"][
                                    "icon_url"
                                ] = v.lstrip().rstrip()
                            else:
                                self.data["embed"]["author"][
                                    "url"
                                ] = v.lstrip().rstrip()
                        else:
                            if await is_valid_icon_url(v.lstrip().rstrip()):
                                self.data["embed"]["author"][
                                    "icon_url"
                                ] = v.lstrip().rstrip()
                            else:
                                self.data["embed"]["author"]["icon_url"] = v.lstrip().rstrip()
                elif parts[0] == "button":
                    button_data = parts[1].split("&&")
                    if len(button_data) == 3:
                        data = {}
                        for d in button_data:
                            if "http" in d:
                                data["url"] = d
                            else:
                                if _matches := EMOJI_REGEX.findall(d):
                                    button_key = "emoji"
                                elif __matches := DEFAULT_EMOJIS.findall(d):
                                    button_key = "emoji"
                                else:
                                    button_key = "label" if d else "emoji"
                                if data.get("label") and button_key == "label":
                                    continue
                                data[button_key] = d.lstrip().rstrip()
                        if not self.data.get("buttons"):
                            self.data["buttons"] = [data]
                        else:
                            self.data["buttons"].append(data)


                    if len(button_data) == 2:
                        button_label = button_data[0].strip()
                        if _matches := EMOJI_REGEX.findall(button_label):
                            button_key = "emoji"
                        elif __matches := DEFAULT_EMOJIS.findall(button_label):
                            button_key = "emoji"
                        else:
                            button_key = "label"
                        _button_url = (
                            button_data[1].strip().replace("url: ", "").replace(" ", "")
                        )
                        self.validate_url(_button_url)
                        if not self.data.get("buttons"):
                            self.data["buttons"] = [{
                                button_key: button_label,
                                "url": _button_url,
                            }]
                        else:
                            self.data["buttons"].append({button_key: button_label, "url": _button_url})
                elif parts[0] == "field":
                    if "fields" not in self.data["embed"]:
                        self.data["embed"]["fields"] = []
                    field_data = parts[1].split("&&")
                    field_name = field_data[0].strip()
                    field_value = None
                    inline = False

                    if len(field_data) >= 2:
                        field_value = (
                            field_data[1].strip().replace("value: ", "") or None
                        )

                    if len(field_data) >= 3:
                        inline = bool(field_data[2].strip().replace("inline ", ""))

                    self.data["embed"]["fields"].append(
                        {"name": field_name, "value": field_value, "inline": inline}
                    )
                else:
                    name, value = map(str.strip, parts)
                    if name not in self.components:
                        continue

                    self.components[name](value)

        if self.template.startswith("{"):
            self.validate_keys()
            await self.validate()
        else:
            self.data.pop("embed", None)
            self.data["content"] = self.template
        if len(self.data.get("embed", {}).keys()) == 0:
            self.data.pop("embed", None)
        self.compiled = True

    async def send(self: Self, target: Union[Context , GuildChannel], **kwargs) -> Message:
        buttons = self.data.pop("buttons", None)
        if buttons:
            view = View()
            for button in buttons:
                k = {}
                if label := button.get("label"):
                    k["label"] = label
                if emoji := button.get("emoji"):
                    k["emoji"] = emoji
                if not k.get("emoji", k.get("label")):
                    continue
                view.add_item(
                    Button(
                        style=ButtonStyle.link,
                        url=button["url"],
                        **k
                    )
                )
            kwargs["view"] = view
        else:
            if kwargs.get("view"):
                pass
            else:
                kwargs["view"] = None
        if isinstance(self.data.get("embed"), Embed):
            embed = self.data["embed"]
        else:
            embed = (
                Embed.from_dict(self.data["embed"]) if self.data.get("embed") else None
            )
        if embed:
            kwargs["embed"] = embed
            if "{timestamp}" in self.template:
                kwargs["embed"].timestamp = datetime.datetime.now()
        if content := self.data.get("content"):
            kwargs["content"] = content
        if delete_after := self.data.get("delete_after"):
            kwargs["delete_after"] = delete_after
        if kwargs.pop("return_embed", False):
            return kwargs
        return await target.send(
            **kwargs,
        )
    
    async def edit(self: Self, message: Message, **kwargs):
        buttons = self.data.pop("buttons", None)
        if buttons:
            view = View()
            for button in buttons:
                kwargs = {}
                if label := button.get("label"):
                    kwargs["label"] = label
                if emoji := button.get("emoji"):
                    kwargs["emoji"] = emoji
                if not kwargs.get("emoji", kwargs.get("button")):
                    continue
                view.add_item(
                    Button(
                        style=ButtonStyle.link,
                        url=button["url"],
                        **kwargs
                    )
                )
            kwargs["view"] = view
        else:
            if kwargs.get("view"):
                pass
            else:
                kwargs["view"] = None
        if isinstance(self.data.get("embed"), Embed):
            embed = self.data["embed"]
        else:
            embed = (
                Embed.from_dict(self.data["embed"]) if self.data.get("embed") else None
            )
        if embed:
            kwargs["embed"] = embed
        if content := self.data.get("content"):
            kwargs["content"] = content
        if delete_after := self.data.get("delete_after"):
            kwargs["delete_after"] = delete_after
        if kwargs.pop("return_embed", False):
            return kwargs
        return await message.edit(**kwargs)

    @classmethod
    async def convert(cls: Type["Script"], ctx: Context, argument: str) -> "Script":
        data = cls(template=argument, user=ctx.author)
        await data.compile()
        return data

    def __dict__(self: Self) -> dict:
        return self.data

    def __repr__(self: Self) -> str:
        return f"<EmbedParser template={self.template!r}>"

    def __str__(self: Self) -> str:
        return self.template


    @property
    def dict(self: Self) -> dict:
        if not self.compiled:
            raise Exception("Coroutine Script.compile has not been executed yet")
        return self.data

