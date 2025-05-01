from discord import Guild, Role


@property
def actual_position(self: Role) -> int:
    guild: Guild = self.guild
    roles = [r for r in guild.roles][::-1]
    return roles.index(self)
