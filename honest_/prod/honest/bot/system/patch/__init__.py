import discord

from .alias import *
from .channel import (confirm, dump_history, fail, normal, reply, success,
                      warning)
from .checks import guild_owner, is_booster, is_staff
from .command import *
from .context import *
from .guild import *
from .help import Help, map_check
from .interaction import *
from .member import config, is_donator, url, worker_badges
from .message import *
from .role import actual_position

discord.TextChannel.confirm = confirm
discord.TextChannel.success = success
discord.TextChannel.normal = normal
discord.TextChannel.fail = fail
discord.TextChannel.warning = warning
discord.TextChannel.reply = reply
discord.TextChannel.dump_history = dump_history

discord.Thread.confirm = confirm
discord.Thread.success = success
discord.Thread.normal = normal
discord.Thread.fail = fail
discord.Thread.warning = warning
discord.Thread.reply = reply
discord.Thread.dump_history = dump_history

discord.Member.config = config
discord.Member.url = url
discord.Member.is_donator = is_donator
discord.Member.worker_badges = worker_badges

discord.User.config = config
discord.User.url = url
discord.User.is_donator = is_donator
discord.User.worker_badges = worker_badges

discord.Role.actual_position = actual_position
