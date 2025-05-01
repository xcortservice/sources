"""
AllowedMentions class for Discord
"""

class AllowedMentions:
    """
    A class that represents what mentions are allowed in a message.
    """
    def __init__(self, *, everyone=True, users=True, roles=True, replied_user=True):
        self.everyone = everyone
        self.users = users
        self.roles = roles
        self.replied_user = replied_user 