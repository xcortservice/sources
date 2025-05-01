from .base import *  # noqa: F403
from .instagram import Instagram
from .kick import Kick
from .tiktok import TikTok
from .twitch import Twitch
from .twitter import Twitter
from .youtube import YouTube

FEEDS = [TikTok, Twitter, YouTube, Twitch, Kick, Instagram]
