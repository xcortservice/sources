class BotMissingPermissions(Exception):
    """
    Exception raised when the bot is missing required permissions
    """
    def __init__(self, missing_permissions):
        self.missing_permissions = missing_permissions
        super().__init__(f"Bot is missing required permissions: {', '.join(missing_permissions)}") 