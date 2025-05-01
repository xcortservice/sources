from os import getenv
from json import loads
from cashews import cache
from discord import Member
from redis.asyncio import Redis
from urllib.parse import urlparse, quote, unquote
from typing import (
    Any,
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
    ClassVar,
    Literal,
)
from dotenv import load_dotenv
from typing_extensions import Self

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

load_dotenv(override=True)

if TYPE_CHECKING:
    from greed.framework import Greed


class Defaults(BaseModel):
    prefix: str = ","
    help_menu: Literal["Greed", "Basic", "Dropdown"] = (
        "Greed"
    )
    auto_transcription: bool = False
    ignored_channels: List[int] = []
    disabled_commands: List[str] = []
    disabled_cogs: List[str] = []


class Colors(BaseModel):
    approved: int = 0xCCCCFF
    denied: int = 0xCCCCFF
    warned: int = 0xCCCCFF
    information: int = 0xCCCCFF
    neutral: int = 0xCCCCFF


class FunEmojis(BaseSettings):
    lesbian: str = "<:lesbian:1300034112987598890>"
    gay: str = "<:gay:1300034800257732719>"
    dumbass: str = "<:dumbass:1339465205914144819>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_FUN_ENV_PREFIX", "EMOJIS_FUN_"
        )
    )


class DeviceEmojis(BaseSettings):
    desk_dnd: str = "<:pc_dnd:1348051783947255839>"
    desk_idle: str = "<:pc_idle:1348051786623094839>"
    desk_online: str = "<:pc_online:1348051790293368924>"
    phone_dnd: str = "<:phone_dnd:1348051793745281076>"
    phone_idle: str = "<:phone_idle:1348051796878430228>"
    phone_online: str = (
        "<:phone_online:1348051801248759959>"
    )
    web_dnd: str = "<:web_dnd:1348826528519159918>"
    web_idle: str = "<:web_idle:1348826531631206561>"
    web_online: str = "<:web_online:1348826534261166100>"
    offline: str = "<:status_offline:1348826787529887814>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_DEVICES_ENV_PREFIX", "EMOJIS_DEVICES_"
        )
    )


class EconomyEmojis(BaseSettings):
    welcome: str = "<a:welcome:1332951722271703070>"
    command: str = "<:command:1333095008286408795>"
    gem: str = "<a:gem:1332951453589049456>"
    crown: str = "<:crown:1320338275570946120>"
    invis: str = "<:invis:1333300029460582400>"
    coin: str = "<a:coinflip:1353072353612923041>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_ECONOMY_ENV_PREFIX", "EMOJIS_ECONOMY_"
        )
    )


class PollEmojis(BaseSettings):
    blr: str = "<:evict_blr:1263759792439169115>"
    square: str = "<:evict_sqaure:1263759807417028649>"
    brr: str = "<:evict_brr:1263759798751461377>"
    wlr: str = "<:white_left_rounded:1263743905120387172>"
    white: str = "<:white:1263743898145001517>"
    wrr: str = "<:white_right_rounded:1263743912221216862>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_POLL_ENV_PREFIX", "EMOJIS_POLL_"
        )
    )


class StaffEmojis(BaseSettings):
    developer: str = "<:developer:1325012518006947861>"
    owner: str = "<:owner:1325012419587866666>"
    support: str = "<:support:1325012723922370601>"
    trial: str = "<:trial:1323255897656397824>"
    moderator: str = "<:mod:1325081613238931457>"
    donor: str = "<:donor1:1320054420616249396>"
    instance: str = "<:donor4:1320428908406902936>"
    staff: str = "<:staff:1325012421819236443>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_STAFF_ENV_PREFIX", "EMOJIS_STAFF_"
        )
    )


class InterfaceEmojis(BaseSettings):
    lock: str = "<:lock:1263727069095919698>"
    unlock: str = "<:unlock:1263730907680870435>"
    ghost: str = "<:hide:1263731781157392396>"
    reveal: str = "<:reveal:1263731670121709568>"
    claim: str = "<:claim:1263731873167708232>"
    disconnect: str = "<:hammer:1292838404597354637>"
    activity: str = "<:activity:1292838226125656097>"
    information: str = "<:information:1263727043967717428>"
    increase: str = "<:increase:1263731093845315654>"
    decrease: str = "<:decrease:1263731510239035442>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_INTERFACE_ENV_PREFIX",
            "EMOJIS_INTERFACE_",
        )
    )


class PaginatorEmojis(BaseSettings):
    next: str = "<:right:1263727130370637995>"
    navigate: str = "<:filter:1263727034798968893>"
    previous: str = "<:left:1263727060078035066>"
    cancel: str = "<:deny:1263727013433184347>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_PAGINATOR_ENV_PREFIX",
            "EMOJIS_PAGINATOR_",
        )
    )


class AudioEmojis(BaseSettings):
    skip: str = "<:skip:1243011308333564006>"
    resume: str = "<:resume:1243011309449252864>"
    repeat: str = "<:repeat:1243011309843382285>"
    previous: str = "<:previous:1243011310942162990>"
    pause: str = "<:pause:1243011311860842627>"
    queue: str = "<:queue:1243011313006022698>"
    repeat_track: str = (
        "<:repeat_track:1243011313660334101>"
    )

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_AUDIO_ENV_PREFIX", "EMOJIS_AUDIO_"
        )
    )


class AntinukeEmojis(BaseSettings):
    enable: str = "<:enable:1263758811429343232>"
    disable: str = "<:disable:1263758691858120766>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_ANTINUKE_ENV_PREFIX", "EMOJIS_ANTINUKE_"
        )
    )


class BadgesEmojis(BaseSettings):
    hypesquad_brilliance: str = (
        "<:hypesquad_brillance:1289500479117590548>"
    )
    boost: str = "<:booster:1263727083310415885>"
    staff: str = "<:staff:1263729127199084645>"
    verified_bot_developer: str = (
        "<:earlydev:1263727027022860330>"
    )
    server_owner: str = "<:owner:1329251274440310834>"
    hypesquad_bravery: str = (
        "<:hypesquad_bravery:1289500873830961279>"
    )
    partner: str = "<:partner:1263727124066340978>"
    hypesquad_balance: str = (
        "<:hypesquad_balance:1289500688052785222>"
    )
    early_supporter: str = "<:early:1263727021318602783>"
    hypesquad: str = "<:hypesquad:1289501069449236572>"
    bug_hunter_level_2: str = (
        "<:buggold:1263726960882876456>"
    )
    certified_moderator: str = (
        "<:certified_moderator:1289501261640765462>"
    )
    nitro: str = "<:nitro:1289499927117828106>"
    bug_hunter: str = "<:bugreg:1263726968377966642>"
    active_developer: str = (
        "<:activedev:1263726943048695828>"
    )

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_BADGES_ENV_PREFIX", "EMOJIS_BADGES_"
        )
    )

    def from_flags(self, member: Member) -> List[str]:
        return [
            getattr(self, flag[0])
            for flag in member.flags
            if flag[1] and getattr(self, flag[0])
        ]


class ContextEmojis(BaseSettings):
    approved: str = "<:approve:1271155661451034666>"
    denied: str = "<:deny:1263727013433184347>"
    warned: str = "<:warn:1263727178802004021>"
    filter: str = "<:filter:1263727034798968893>"
    left: str = "<:left:1263727060078035066>"
    right: str = "<:right:1263727130370637995>"
    juul: str = "<:juul:1300217541909545000>"
    no_juul: str = "<:no_juul:1300217551699181588>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_CONTEXT_ENV_PREFIX", "EMOJIS_CONTEXT_"
        )
    )


class StatusEmojis(BaseSettings):
    approved: str = "<:approve:1271155661451034666>"
    denied: str = "<:deny:1263727013433184347>"
    warned: str = "<:warn:1263727178802004021>"
    filter: str = "<:filter:1263727034798968893>"
    left: str = "<:left:1263727060078035066>"
    right: str = "<:right:1263727130370637995>"
    juul: str = "<:juul:1300217541909545000>"
    no_juul: str = "<:no_juul:1300217551699181588>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_STATUS_ENV_PREFIX", "EMOJIS_STATUS_"
        )
    )


class SocialEmojis(BaseSettings):
    discord: str = "<:discord:1290120978306695281>"
    github: str = "<:github:1289507143887884383>"
    website: str = "<:link:1290119682103316520>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_SOCIAL_ENV_PREFIX", "EMOJIS_SOCIAL_"
        )
    )


class MiscEmojis(BaseSettings):
    connection: str = "<:connection:1300775066933530755>"
    crypto: str = "<:crypto:1323197786111606847>"
    bitcoin: str = "<:bitcoin:1323197068734632031>"
    ethereum: str = "<:ethereum:1323197076238237758>"
    xrp: str = "<:XRP:1323197083603177472>"
    litecoin: str = "<:LTC:1323197091933327360>"
    extra_support: str = (
        "<:extra_support:1331659705709236264>"
    )
    security: str = "<:security:1331659736386637834>"
    analytics: str = "<:analytics:1331659734637609141>"
    reduced_cooldowns: str = (
        "<:reduced_cooldown:1331659608116297788>"
    )
    ai: str = "<:ai:1331659592630800477>"
    moderation: str = "<:moderator:1325012416035033139>"
    commands: str = "<:donor4:1320428908406902936>"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "EMOJIS_MISC_ENV_PREFIX", "EMOJIS_MISC_"
        )
    )


class Emojis(BaseModel):
    fun: FunEmojis = FunEmojis()
    economy: EconomyEmojis = EconomyEmojis()
    poll: PollEmojis = PollEmojis()
    staff: StaffEmojis = StaffEmojis()
    interface: InterfaceEmojis = InterfaceEmojis()
    paginator: PaginatorEmojis = PaginatorEmojis()
    audio: AudioEmojis = AudioEmojis()
    antinuke: AntinukeEmojis = AntinukeEmojis()
    badges: BadgesEmojis = BadgesEmojis()
    context: ContextEmojis = ContextEmojis()
    social: SocialEmojis = SocialEmojis()
    misc: MiscEmojis = MiscEmojis()
    device: DeviceEmojis = DeviceEmojis()


class GoogleAPI(BaseSettings):
    cx: str = ""
    key: str = ""

    model_config = SettingsConfigDict(
        env_prefix=getenv("GOOGLE_ENV_PREFIX", "GOOGLE_")
    )


class TwitchAPI(BaseSettings):
    client_id: str = ""
    client_secret: str = ""

    model_config = SettingsConfigDict(
        env_prefix=getenv("TWITCH_ENV_PREFIX", "TWITCH_")
    )


class SpotifyAPI(BaseSettings):
    client_id: str = getenv("SPOTIFY_CLIENT_ID", "908846bb106d4190b4cdf5ceb3d1e0e5")
    client_secret: str = getenv("SPOTIFY_CLIENT_SECRET", "d08df8638ee44bdcbfe6057a5e7ffd78")

    model_config = SettingsConfigDict(
        env_prefix=getenv("SPOTIFY_ENV_PREFIX", "SPOTIFY_")
    )


class RedditAPI(BaseSettings):
    client_id: str = ""
    client_secret: str = ""

    model_config = SettingsConfigDict(
        env_prefix=getenv("REDDIT_ENV_PREFIX", "REDDIT_")
    )


class BunnyCDNBackup(BaseSettings):
    host: str = ""
    user: str = ""
    password: str = ""

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "BUNNYCDN_BACKUPS_ENV_PREFIX",
            "BUNNYCDN_BACKUPS_",
        )
    )


class BunnyCDNAVH(BaseSettings):
    url: str = ""
    access_key: str = ""

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "BUNNYCDN_AVH_ENV_PREFIX", "BUNNYCDN_AVH_"
        )
    )


class BunnyCDNSocials(BaseSettings):
    url: str = ""
    access_key: str = ""

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "BUNNYCDN_SOCIALS_ENV_PREFIX",
            "BUNNYCDN_SOCIALS_",
        )
    )


class APIKeys(BaseSettings):
    fnbr: str = ""
    clever: str = ""
    wolfram: str = ""
    weather: str = ""
    osu: str = ""
    lastfm: list[str] = ["419e14665806ce4075565abe456a7bd4"]
    soundcloud: str = ""
    gemini: str = ""
    kraken: str = ""
    fernet_key: str = ""
    piped_api: str = ""
    jeyy_api: str = ""
    openai: str = ""
    lovense: str = ""

    google: GoogleAPI = GoogleAPI()
    twitch: TwitchAPI = TwitchAPI()
    spotify: SpotifyAPI = SpotifyAPI()
    reddit: RedditAPI = RedditAPI()
    backups: BunnyCDNBackup = BunnyCDNBackup()
    avh: BunnyCDNAVH = BunnyCDNAVH()
    socials: BunnyCDNSocials = BunnyCDNSocials()

    model_config = SettingsConfigDict(
        env_prefix=getenv("API_ENV_PREFIX", "API_")
    )


class Proxy(BaseModel):
    protocol: Literal[
        "http", "https", "socks4", "socks5", "socks5h"
    ] = "https"
    host: str = "localhost"
    port: int = 6995
    username: Optional[str]
    password: Optional[str]

    @property
    def url(self) -> str:
        auth = f"{quote(self.username)}:{quote(self.password or '')}@" if self.username else ""
        return f"{self.protocol}://{auth}{self.host}:{self.port}"

    @classmethod
    def from_url(cls, url: str) -> Self:
        """
        Parses a proxy URL and returns a Proxy instance.
        """
        if (
            parsed := urlparse(url)
        ) and parsed.scheme not in {
            "http",
            "https",
            "socks4",
            "socks5",
            "socks5h",
        }:
            raise ValueError(
                f"Invalid proxy protocol: {parsed.scheme}"
            )

        return cls(
            protocol=parsed.scheme,  # type: ignore
            host=parsed.hostname or "localhost",
            port=parsed.port or 6995,
            username=unquote(parsed.username)
            if parsed.username
            else None,
            password=unquote(parsed.password)
            if parsed.password
            else None,
        )


class LoggingGuilds(BaseModel):
    primary: int = 892675627373699072
    logging: int = 1318473085032071178
    testing: int = 0


class LoggingTypes(BaseModel):
    command: int = 1319467001051090956
    status: int = 1319470623071670295

    guild_blacklist: int = 1357643053392859180
    guild_unblacklist: int = 1357643073991086172

    user_blacklist: int = 1319467099969556542
    user_unblacklist: int = 1357643139673755741

    guild_joined: int = 1356918941133570154
    guild_left: int = 1356918926088605697


class Logging(BaseModel):
    guilds: LoggingGuilds = LoggingGuilds()
    types: LoggingTypes = LoggingTypes()


class Lavalink(BaseSettings):
    nodes: int = 1
    host: str = "127.0.0.1"
    port: int = 2333
    password: str = "youshallnotpass"

    model_config = SettingsConfigDict(
        env_prefix=getenv(
            "LAVALINK_ENV_PREFIX", "LAVALINK_"
        )
    )


class Authentication:
    keys: ClassVar[APIKeys] = APIKeys()
    token: ClassVar[str] = getenv("TOKEN", "")
    redis: ClassVar[Redis] = Redis.from_url(
        getenv("REDIS_URL", "redis://localhost:6379")
    )
    proxy: ClassVar[Proxy] = Proxy.from_url(
        getenv("PROXY_URL", "http://127.1:40000")
    )
    logging: ClassVar[Logging] = Logging()
    lavalink: ClassVar[Lavalink] = Lavalink()
    owner_ids: ClassVar[List[int]] = loads(
        getenv(
            "OWNER_IDS",
            "[585689685771288600, 987183275560820806, 1247076592556183598, 320288667329495040, 930383131863842816, 442626774841556992]",
        )
    )
    support_url: ClassVar[str] = getenv(
        "SUPPORT_URL", "https://discord.gg/evict"
    )
    bot_invite: ClassVar[str] = getenv(
        "BOT_INVITE",
        "https://discord.com/oauth2/authorize?client_id=1203514684326805524&permissions=8&scope=bot%20applications.commands",
    )
    client_secret: ClassVar[str] = getenv(
        "CLIENT_SECRET", ""
    )
    redirect_uri: ClassVar[str] = getenv(
        "REDIRECT_URI", "https://vesta.greed.best/callback"
    )


class Configuration:
    colors: Colors
    emojis: Emojis
    defaults: Defaults
    authentication: ClassVar[Authentication] = (
        Authentication()
    )

    __slots__ = ("colors", "emojis", "defaults")

    def __init__(
        self,
        *,
        colors: Optional[Colors] = None,
        emojis: Optional[Emojis] = None,
        defaults: Optional[Defaults] = None,
    ):
        self.colors = colors or Colors()
        self.emojis = emojis or Emojis()
        self.defaults = defaults or Defaults()

    @classmethod
    @cache(ttl="3m", key="configuration:guild:{guild_id}")
    async def from_guild(
        cls, guild_id: int, bot: "Greed"
    ) -> Self:
        config: Dict[str, Any] = loads(
            await bot.pool.fetchval(
                """
                SELECT config 
                FROM guild.settings 
                WHERE guild_id = $1
                """,
                guild_id,
            )
            or '{"defaults": {}, "emojis": {}, "colors": {}}'
        )
        return cls(
            colors=Colors(**config["colors"]),
            emojis=Emojis(**config["emojis"]),
            defaults=Defaults(**config["defaults"]),
        )

    @classmethod
    @cache(ttl="3m", key="configuration:user:{user_id}")
    async def from_user(
        cls, user_id: int, bot: "Greed"
    ) -> Self:
        config: Dict[str, Any] = loads(
            await bot.pool.fetchval(
                """
                SELECT config 
                FROM user.settings 
                WHERE user_id = $1
                """,
                user_id,
            )
            or str({
                "defaults": {},
                "emojis": {},
                "colors": {},
            })
        )
        return cls(
            colors=Colors(**config["colors"]),
            emojis=Emojis(**config["emojis"]),
            defaults=Defaults(**config["defaults"]),
        )
