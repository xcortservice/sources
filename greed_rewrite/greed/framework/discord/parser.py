from re import compile, DOTALL, IGNORECASE
from typing import Any, Callable, Dict, Optional, Union
from aiohttp import ClientSession, ClientTimeout, ClientError
from typing_extensions import Type, NoReturn, Self
from urllib.parse import urlparse

from discord import (
    Embed, 
    User, 
    Member, 
    Message, 
    ButtonStyle
)
from discord.ext.commands import CommandError, Context, Converter
from discord.abc import GuildChannel
from discord.ui import View, Button
from discord.utils import format_dt


image_link = compile(
    r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/\/=]*(?:\.png|\.jpe?g|\.gif|\.jpg|))"
)
URL_PATTERN = compile(
    r"^https?:\/\/"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    DOTALL | IGNORECASE
)


def ordinal(n):
    try:
        n = int(n)
        return "%d%s" % (
            n,
            "tsnrhtdd"[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4],
        )
    except (ValueError, TypeError):
        return str(n)


class EmbedConverter(Converter):
    async def convert(self, ctx: Context, code: str) -> Optional[dict]:
        script = Script(code, ctx.author)
        try:
            await script.compile()
        except EmbedError as e:
            await ctx.embed(f"{e.message}", "warned")
            raise e
        return await script.send(ctx.channel, return_embed=True)


class EmbedError(CommandError):
    def __init__(self, message: str, **kwargs):
        self.message = message
        super().__init__(message, kwargs)


class Script:
    def __init__(
        self, template: str, user: Union[Member, User], lastfm_data: dict = {}
    ):
        self.pattern = compile(r"\{([\s\S]*?)\}")
        self.data: Dict[str, Union[Dict, str]] = {
            "embed": {},
        }
        self.replacements = {
            "{user}": str(user),
            "{user.mention}": user.mention,
            "{user.name}": user.name,
            "{user.avatar}": user.display_avatar.url,
            "{user.created_at}": format_dt(user.created_at, style="R"),
            "{whitespace}": "\u200e",
            "{message}": "",  # Will be updated in compile if message exists
            "{context}": "",  # Will be updated in compile if context exists
            "{content}": "",  # Will be updated in compile if content exists
        }
        if isinstance(user, Member):
            self.replacements.update(
                {
                    "{user.joined_at}": format_dt(user.joined_at, style="R"),
                    "{guild.name}": user.guild.name,
                    "{guild.count}": str(user.guild.member_count),
                    "{guild.count.format}": ordinal(len(user.guild.members)),
                    "{guild.id}": str(user.guild.id),  # Convert to string for safety
                    "{guild.created_at}": format_dt(user.guild.created_at, style="R"),
                    "{guild.boost_count}": str(user.guild.premium_subscription_count),
                    "{guild.booster_count}": str(len(user.guild.premium_subscribers)),
                    "{guild.boost_count.format}": ordinal(
                        user.guild.premium_subscription_count
                    ),
                    "{guild.booster_count.format}": ordinal(
                        user.guild.premium_subscription_count
                    ),
                    "{guild.boost_tier}": str(user.guild.premium_tier),
                    "{guild.icon}": user.guild.icon.url if user.guild.icon else "",
                    "{guild.vanity}": user.guild.vanity_url_code or "",
                }
            )
            # Add lastfm data with safe defaults
            self.replacements.update(
                {f"{{{k}}}": str(v) for k, v in lastfm_data.items()}
            )

        self.template = self._replace_placeholders(template)

    def get_color(self, color: str) -> int:
        """Safely convert a hex color string to integer."""
        try:
            # Remove # if present and validate length
            color = color.replace("#", "").strip()
            if not (len(color) == 6 or len(color) == 8):
                raise ValueError("Invalid color length")
            return int(color[:6], 16)
        except (ValueError, TypeError) as e:
            raise EmbedError(f"Invalid hex color `{color[:6]}`: {str(e)}")

    @property
    def components(self) -> Dict[str, Callable[[Any], None]]:
        return {
            "content": lambda value: self.data.update({"content": value}),
            "message": lambda value: self.data.update({"content": value}),
            "context": lambda value: self.data.update({"content": value}),
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

    def validate_keys(self: Self) -> None:
        """Validate template key structure."""
        stack = []
        template = self.template
        i = 0

        try:
            while i < len(template):
                char = template[i]

                if char == "{":
                    if i + 1 < len(template) and (
                        template[i + 1] == ":" or template[i + 1] == "$"
                    ):
                        stack.append("{:")
                        i += 1
                    else:
                        stack.append("{")

                elif char == "}":
                    if not stack:
                        raise EmbedError("Found a `}` without a matching `{`")
                    opening = stack.pop()
                    if (
                        opening == "{:"
                        and i + 1 < len(template)
                        and template[i + 1] != "}"
                    ):
                        raise EmbedError("`{:` is missing a `}` at the end")
                    elif opening != "{:" and opening != "{":
                        raise EmbedError("Mismatched braces found")

                i += 1

            if stack:
                raise EmbedError("Unmatched `{` found in the template")
        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"Template validation error: {str(e)}")
            raise

    def validate_url(self: Self, url: str) -> bool:
        """Validate URL format and structure."""
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                raise EmbedError(f"`{url}` is not a valid URL Format")
            if result.scheme not in ("http", "https"):
                raise EmbedError(f"`{url}` must use http or https protocol")
            return True
        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"URL validation error for `{url}`: {str(e)}")
            raise

    async def validate_image(self: Self, url: str) -> bool:
        """Validate image URL and content."""
        if not image_link.match(url):
            raise EmbedError(f"`{url}` is not a valid Image URL Format")

        timeout = ClientTimeout(total=10)
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.head(url) as response:
                    if not response.ok:
                        raise EmbedError(f"`{url}` returned HTTP {response.status}")

                    # Check content length
                    if content_length := response.headers.get("Content-Length"):
                        if int(content_length) > 240000000:
                            raise EmbedError(f"`{url}` exceeds maximum size of 240MB")

                    # Validate content type
                    content_type = response.headers.get("Content-Type", "").lower()
                    if not content_type or "image" not in content_type:
                        raise EmbedError(
                            f"`{url}` has invalid content type: `{content_type}`"
                        )

                    return True
        except ClientError as e:
            raise EmbedError(f"Failed to validate image `{url}`: {str(e)}")
        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"Image validation error for `{url}`: {str(e)}")
            raise

    def parse_button(self, value: str) -> None:
        """Parse button data safely."""
        try:
            button_data = [part.strip() for part in value.split("&&")]
            if len(button_data) < 2:
                raise EmbedError(
                    "Button must have both label and URL (format: label && url)"
                )

            label = button_data[0]
            url = button_data[1].replace("url:", "").strip()

            if not label:
                raise EmbedError("Button label cannot be empty")

            if len(label) > 80:  # Discord's button label limit
                raise EmbedError("Button label cannot exceed 80 characters")

            self.validate_url(url)
            self.data["button"] = {"label": label, "url": url}

        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"Button parsing error: {str(e)}")
            raise

    def parse_field(self, value: str) -> None:
        """Parse field data safely."""
        try:
            if "fields" not in self.data["embed"]:
                self.data["embed"]["fields"] = []

            field_data = [part.strip() for part in value.split("&&")]
            if not field_data[0]:
                raise EmbedError("Field name cannot be empty")

            field = {
                "name": field_data[0],
                "value": (
                    field_data[1].replace("value:", "").strip()
                    if len(field_data) > 1
                    else "\u200b"
                ),
                "inline": False,
            }

            # Parse inline parameter if present
            if len(field_data) > 2:
                inline_str = field_data[2].replace("inline:", "").strip().lower()
                field["inline"] = inline_str in ("true", "yes", "1", "on")

            # Validate lengths
            if len(field["name"]) > 256:
                raise EmbedError("Field name cannot exceed 256 characters")
            if len(field["value"]) > 1024:
                raise EmbedError("Field value cannot exceed 1024 characters")

            self.data["embed"]["fields"].append(field)

        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"Field parsing error: {str(e)}")
            raise

    def _replace_placeholders(self: Self, template: str) -> str:
        template = (
            template.replace("{embed}", "").replace("$v", "").replace("} {", "}{")
        )
        for placeholder, value in self.replacements.items():
            template = template.replace(placeholder, str(value))
        return template

    async def validate(self: Self) -> NoReturn:
        """Validate all embed components."""
        try:
            DICT = {}
            embed_data = self.data.get("embed", {})

            # Validate URLs
            if thumbnail := embed_data.get("thumbnail", DICT).get("url"):
                await self.validate_image(thumbnail)
            if image := embed_data.get("image", DICT).get("url"):
                await self.validate_image(image)
            if author_icon := embed_data.get("author", DICT).get("icon_url"):
                await self.validate_image(author_icon)
            if footer_icon := embed_data.get("footer", DICT).get("icon_url"):
                await self.validate_image(footer_icon)
            if author_url := embed_data.get("author", DICT).get("url"):
                self.validate_url(author_url)
            if embed_url := embed_data.get("url"):
                self.validate_url(embed_url)

            # Validate text lengths
            author = embed_data.get("author", DICT).get("name", "")
            footer = embed_data.get("footer", DICT).get("text", "")
            title = embed_data.get("title", "")
            description = embed_data.get("description", "")
            fields = embed_data.get("fields", [])
            content = self.data.get("content", "")

            if len(author) > 256:
                raise EmbedError("Author name cannot exceed 256 characters")
            if len(footer) > 2048:
                raise EmbedError("Footer text cannot exceed 2048 characters")
            if len(description) > 4096:
                raise EmbedError("Description cannot exceed 4096 characters")
            if len(title) > 256:
                raise EmbedError("Title cannot exceed 256 characters")
            if len(content) > 2000:
                raise EmbedError("Content cannot exceed 2000 characters")

            # Validate fields
            for idx, f in enumerate(fields, 1):
                if len(f.get("name", "")) > 256:
                    raise EmbedError(f"Field {idx} name cannot exceed 256 characters")
                if len(f.get("value", "")) > 1024:
                    raise EmbedError(f"Field {idx} value cannot exceed 1024 characters")

            # Validate total embed length
            if embed_data:
                embed = Embed.from_dict(embed_data)
                if len(embed) > 6000:
                    raise EmbedError("Total embed length cannot exceed 6000 characters")

                # Ensure embed has content if only color is set
                keys = list(embed_data.keys())
                if len(keys) == 1 and "color" in keys:
                    raise EmbedError("Embed must have content when only color is set")

        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"Validation error: {str(e)}")
            raise

    async def compile(self: Self) -> None:
        """Compile the template into structured data for an embed."""
        try:
            self.template = self.template.replace(r"\n", "\n").replace("\\n", "\n")
            matches = self.pattern.findall(self.template)

            for match in matches:
                parts = match.split(":", 1)
                if len(parts) != 2:
                    continue

                key, value = parts[0].strip(), parts[1].strip()

                if key == "footer":
                    self.parse_footer(value)
                elif key == "author":
                    self.parse_author(value)
                elif key == "button":
                    self.parse_button(value)
                elif key == "field":
                    self.parse_field(value)
                elif key in self.components:
                    self.components[key](value)

            if self.template.startswith("{"):
                self.validate_keys()
                await self.validate()
            else:
                self.data.pop("embed", None)
                self.data["content"] = self.template

            if not self.data.get("embed"):
                self.data.pop("embed", None)

        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"Compilation error: {str(e)}")
            raise

    def parse_footer(self, value: str) -> None:
        """Parse footer data safely."""
        try:
            values = [v.strip() for v in value.split("&&")]
            if not values[0]:
                raise EmbedError("Footer text cannot be empty")

            footer_data = {"text": values[0]}

            if len(values) > 1 and values[1]:
                url = values[1]
                self.validate_url(url)
                footer_data["url"] = url

            if len(values) > 2 and values[2]:
                footer_data["icon_url"] = values[2]

            self.data["embed"]["footer"] = footer_data

        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"Footer parsing error: {str(e)}")
            raise

    def parse_author(self, value: str) -> None:
        """Parse author data safely."""
        try:
            values = [v.strip() for v in value.split("&&")]
            if not values[0]:
                raise EmbedError("Author name cannot be empty")

            author_data = {"name": values[0]}

            for v in values[1:]:
                if not v:
                    continue

                if any(ext in v.lower() for ext in [".jpg", ".png", ".gif", ".webp"]):
                    author_data["icon_url"] = v
                else:
                    self.validate_url(v)
                    author_data["url"] = v

            self.data["embed"]["author"] = author_data

        except Exception as e:
            if not isinstance(e, EmbedError):
                raise EmbedError(f"Author parsing error: {str(e)}")
            raise

    async def send(
        self: Self, target: Union[Context, GuildChannel], **kwargs
    ) -> Message:
        """Send the compiled embed."""
        try:
            # Handle button view
            if button := self.data.pop("button", None):
                view = View()
                view.add_item(
                    Button(
                        style=ButtonStyle.link,
                        label=button["label"],
                        url=button["url"],
                    )
                )
                kwargs["view"] = view
            else:
                kwargs["view"] = kwargs.get("view", None)

            # Prepare embed
            if isinstance(self.data.get("embed"), Embed):
                embed = self.data["embed"]
            else:
                embed = (
                    Embed.from_dict(self.data["embed"])
                    if self.data.get("embed")
                    else None
                )

            if embed:
                kwargs["embed"] = embed

            # Add content if present
            if content := self.data.get("content"):
                kwargs["content"] = content

            # Handle return_embed early
            if kwargs.pop("return_embed", False):
                return kwargs

            # Handle message editing vs sending
            if message := kwargs.pop("message", None):
                if hasattr(message, "edit"):
                    edit_kwargs = {
                        k: v
                        for k, v in kwargs.items()
                        if k in ["content", "embed", "view"]
                    }
                    return await message.edit(**edit_kwargs)

            # Handle delete_after for new messages only
            if delete_after := self.data.get("delete_after"):
                kwargs["delete_after"] = delete_after

            return await target.send(**kwargs)

        except Exception as e:
            raise EmbedError(f"Failed to send message: {str(e)}")

    @classmethod
    async def convert(cls: Type["Script"], ctx: Context, argument: str) -> "Script":
        """Convert string argument to Script instance."""
        data = cls(template=argument, user=ctx.author)
        await data.compile()
        return data

    def __repr__(self: Self) -> str:
        return f"<Parser template={self.template!r}>"

    def __str__(self: Self) -> str:
        return self.template


# type: ignore