import re

from discord import AllowedMentions

_ID_REGEX = re.compile(r"([0-9]{15,20})$")
DISCORD_ROLE_MENTION = re.compile(r"<@&(\d+)>")
DISCORD_ID = re.compile(r"(\d+)")
DISCORD_USER_MENTION = re.compile(r"<@?(\d+)>")
DISCORD_CHANNEL_MENTION = re.compile(r"<#(\d+)>")
DISCORD_MESSAGE = re.compile(
    r"(?:https?://)?(?:canary\.|ptb\.|www\.)?discord(?:app)?.(?:com/channels|gg)/(?P<guild_id>[0-9]{17,22})/(?P<channel_id>[0-9]{17,22})/(?P<message_id>[0-9]{17,22})"
)
EMOJI_REGEX = re.compile(
    r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>"
)

DEFAULT_EMOJIS = re.compile(
    r"[\U0001F300-\U0001F5FF]|[\U0001F600-\U0001F64F]|[\U0001F680-\U0001F6FF]|[\U0001F700-\U0001F77F]|[\U0001F780-\U0001F7FF]|[\U0001F800-\U0001F8FF]|[\U0001F900-\U0001F9FF]|[\U0001FA00-\U0001FA6F]|[\U0001FA70-\U0001FAFF]|[\U00002702-\U000027B0]|[\U000024C2-\U0001F251]|[\U0001F910-\U0001F9C0]|[\U0001F3A0-\U0001F3FF]"
)
PERCENTAGE = re.compile(r"(?P<percentage>\d+)%")
BITRATE = re.compile(r"(?P<bitrate>\d+)kbps")
COLORHEX = re.compile("^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")


class position:
    HH_MM_SS = re.compile(r"(?P<h>\d{1,2}):(?P<m>\d{1,2}):(?P<s>\d{1,2})")
    MM_SS = re.compile(r"(?P<m>\d{1,2}):(?P<s>\d{1,2})")
    HUMAN = re.compile(r"(?:(?P<m>\d+)\s*m\s*)?(?P<s>\d+)\s*[sm]")
    OFFSET = re.compile(r"(?P<s>(?:\-|\+)\d+)\s*s")


AUTO_RESPONDER_COOLDOWN = (1, 5)
AUTO_REACTION_COOLDOWN = (1, 5)
STICKY_MESSAGE_COOLDOWN = (3, 5)
MESSAGE_EVENT_ALLOWED_MENTIONS = AllowedMentions(
    replied_user=False, users=True, roles=False, everyone=False
)
HEX_COOLDOWN = (2, 3)
TRANSCRIBE_COOLDOWN = (1, 3)
TRACKER_COOLDOWN = (4, 5)
FILTER_COOLDOWN = (10, 20)
PERCENTAGE = re.compile(r"(?P<percentage>\d+)%")

YOUTUBE_WILDCARD = re.compile(
    r"""
    (?x)                                                        # verbose mode
    (?:\s*)                                                    # optional whitespace before the URL
    (?:https?:\/\/)?                                           # optional scheme
    (?:www\.)?(?:youtube\.com|youtu\.be|youtube-nocookie\.com)  # main YouTube domains
    (?:\/(?:watch\?v=|embed\/|v\/|shorts\/|e\/|live\/)?)?      # optional path indicators
    ([\w-]{11})                                                 # video ID of 11 alphanumeric characters
    (?:[&?][\w=]*)*                                             # optional query parameters
    (?:[#\/]?|$)                                                # optional anchor or end of line
    (?:\s*)                                                    # optional whitespace after the URL
""",
    re.IGNORECASE | re.MULTILINE,
)

dangerous_permissions = [
    "administrator",
    "kick_members",
    "ban_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_emojis",
    "manage_webhooks",
    "manage_nicknames",
    "mention_everyone",
    "moderate_members",
    "view_audit_log",
]
PERMISSION_LIST = [
    "create_instant_invite",
    "kick_members",
    "ban_members",
    "administrator",
    "manage_channels",
    "manage_guild",
    "add_reactions",
    "view_audit_log",
    "priority_speaker",
    "stream",
    "read_messages",
    "manage_members",
    "send_messages",
    "send_tts_messages",
    "manage_messages",
    "embed_links",
    "attach_files",
    "read_message_history",
    "mention_everyone",
    "external_emojis",
    "view_guild_insights",
    "connect",
    "speak",
    "mute_members",
    "deafen_members",
    "move_members",
    "use_voice_activation",
    "change_nickname",
    "manage_nicknames",
    "manage_roles",
    "manage_webhooks",
    "manage_expressions",
    "use_application_commands",
    "request_to_speak",
    "manage_events",
    "manage_threads",
    "create_public_threads",
    "create_private_threads",
    "external_stickers",
    "send_messages_in_threads",
    "use_embedded_activities",
    "moderate_members",
    "use_soundboard",
    "create_expressions",
    "use_external_sounds",
    "send_voice_messages",
]

activity_types = [
    {
        "id": 755827207812677713,
        "name": "Poker Night",
        "emoji": "♠",
    },
    {
        "id": 902271654783242291,
        "name": "Sketch Heads",
        "emoji": "🎨",
    },
    {
        "id": 880218394199220334,
        "name": "Watch Togther",
        "emoji": "🎥",
    },
    {
        "id": 832025144389533716,
        "name": "Blazing 8s",
        "emoji": "🎴",
    },
    {
        "id": 832012774040141894,
        "name": "Chess in the Park",
        "emoji": "♟",
    },
    {
        "id": 832013003968348200,
        "name": "Checkers in the Park",
        "emoji": "⚪",
    },
    {
        "id": 879863686565621790,
        "name": "Letter League",
        "emoji": "🅰",
    },
    {
        "id": 879863976006127627,
        "name": "Word Snacks",
        "emoji": "🍬",
    },
    {
        "id": 852509694341283871,
        "name": "Spell Cast",
        "emoji": "🪄",
    },
    {
        "id": 945737671223947305,
        "name": "Putt Party",
        "emoji": "⛳",
    },
    {
        "id": 903769130790969345,
        "name": "Land-io",
        "emoji": "👁",
    },
    {
        "id": 947957217959759964,
        "name": "Bobble League",
        "emoji": "⚽",
    },
]

regions = [
    "brazil",
    "hongkong",
    "india",
    "japan",
    "rotterdam",
    "russia",
    "singapore",
    "south-korea",
    "southafrica",
    "sydney",
    "us-central",
    "us-east",
    "us-south",
    "us-west",
]


IMAGE_URL = re.compile(r"(?:http\:|https\:)?\/\/.*\.(?P<mime>png|jpg|jpeg|webp|gif)")
URL = re.compile(r"(?:http\:|https\:)?\/\/[^\s]*")


colors = {
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
    "blue": "#0000ff",
    "blueviolet": "#8a2be2",
    "brown": "#a52a2a",
    "burlywood": "#deb887",
    "cadetblue": "#5f9ea0",
    "chartreuse": "#7fff00",
    "chocolate": "#d2691e",
    "coral": "#ff7f50",
    "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc",
    "crimson": "#dc143c",
    "cyan": "#00ffff",
    "darkblue": "#00008b",
    "darkcyan": "#008b8b",
    "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9",
    "darkgrey": "#a9a9a9",
    "darkgreen": "#006400",
    "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00",
    "darkorchid": "#9932cc",
    "darkred": "#8b0000",
    "darksalmon": "#e9967a",
    "darkseagreen": "#8fbc8f",
    "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f",
    "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3",
    "deeppink": "#ff1493",
    "deepskyblue": "#00bfff",
    "dimgray": "#696969",
    "dimgrey": "#696969",
    "dodgerblue": "#1e90ff",
    "firebrick": "#b22222",
    "floralwhite": "#fffaf0",
    "forestgreen": "#228b22",
    "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc",
    "ghostwhite": "#f8f8ff",
    "gold": "#ffd700",
    "goldenrod": "#daa520",
    "gray": "#808080",
    "grey": "#808080",
    "green": "#008000",
    "greenyellow": "#adff2f",
    "honeydew": "#f0fff0",
    "hotpink": "#ff69b4",
    "indianred": "#cd5c5c",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5",
    "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd",
    "lightblue": "#add8e6",
    "lightcoral": "#f08080",
    "lightcyan": "#e0ffff",
    "lightgoldenrodyellow": "#fafad2",
    "lightgray": "#d3d3d3",
    "lightgrey": "#d3d3d3",
    "lightgreen": "#90ee90",
    "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa",
    "lightslategray": "#778899",
    "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0",
    "lime": "#00ff00",
    "limegreen": "#32cd32",
    "linen": "#faf0e6",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a",
    "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585",
    "midnightblue": "#191970",
    "mintcream": "#f5fffa",
    "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead",
    "navy": "#000080",
    "oldlace": "#fdf5e6",
    "olive": "#808000",
    "olivedrab": "#6b8e23",
    "orange": "#ffa500",
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    "paleturquoise": "#afeeee",
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "pink": "#ffc0cb",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    "purple": "#800080",
    "red": "#ff0000",
    "rosybrown": "#bc8f8f",
    "royalblue": "#4169e1",
    "saddlebrown": "#8b4513",
    "salmon": "#fa8072",
    "sandybrown": "#f4a460",
    "seagreen": "#2e8b57",
    "seashell": "#fff5ee",
    "sienna": "#a0522d",
    "silver": "#c0c0c0",
    "skyblue": "#87ceeb",
    "slateblue": "#6a5acd",
    "slategray": "#708090",
    "slategrey": "#708090",
    "snow": "#fffafa",
    "springgreen": "#00ff7f",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "teal": "#008080",
    "thistle": "#d8bfd8",
    "tomato": "#ff6347",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "white": "#ffffff",
    "whitesmoke": "#f5f5f5",
    "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}
# BLEED COLOR VARIABLES
