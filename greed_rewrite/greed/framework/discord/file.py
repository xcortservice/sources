class File:
    """
    A parameter object used for :meth:`abc.Messageable.send`
    to represent a file to be uploaded to Discord.
    """
    def __init__(self, fp, *, filename=None, spoiler=False):
        self.fp = fp
        self.filename = filename
        self.spoiler = spoiler
