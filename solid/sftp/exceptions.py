class SFTPError(Exception):
    def __init__(self, message: str, original: Exception | None = None):
        self.message = message
        self.original = original
        super().__init__(message)


class SFTPConnectionError(SFTPError):
    pass


class SFTPTransferError(SFTPError):
    pass


class SFTPDirectoryError(SFTPError):
    pass
