from discord.ext import commands

from .channels import (CategoryChannelConverter, GuildChannelConverter,
                       TextChannelConverter, ThreadChannelConverter,
                       VoiceChannelConverter)
from .color import ColorConv, ColorInfo
from .custom import (AntiNukeAction, Boolean,  # , YouTubeChannelConverter,
                     CommandConverter, EmbedConverter, Expiration, GConverter,
                     GuildConv, GuildConverter, Timeframe)
from .roles import AssignedRole, FakePermission, MultipleRoles, Role
from .snowflakes import (Emoji, MemberConverter, SafeMemberConverter,
                         UserConverter)

commands.TextChannelConverter = TextChannelConverter
commands.ThreadConverter = ThreadChannelConverter
commands.GuildConverter = GuildConverter
commands.Emoji = Emoji
commands.AntiNukeAction = AntiNukeAction
commands.GuildChannelConverter = GuildChannelConverter
commands.CategoryChannelConverter = CategoryChannelConverter
commands.VoiceChannelConverter = VoiceChannelConverter
commands.UserConverter = UserConverter
commands.MemberConverter = MemberConverter
commands.SafeMemberConverter = SafeMemberConverter
commands.RoleConverter = Role
commands.SafeRoleConverter = AssignedRole
commands.MultipleRoles = MultipleRoles
commands.Boolean = Boolean
commands.ColourConverter = ColorConv
commands.ColorConverter = ColorConv
commands.ColorInfo = ColorInfo
# commands.YouTubeChannelConverter = YouTubeChannelConverter
commands.CommandConverter = CommandConverter
commands.Timeframe = Timeframe
commands.EmbedConverter = EmbedConverter
commands.GuildID = GConverter
commands.Expiration = Expiration
commands.FakePermission = FakePermission
