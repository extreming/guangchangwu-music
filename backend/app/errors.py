class AppError(Exception):
    """User-facing failure. `message` is Simplified Chinese."""

    def __init__(self, message: str, code: str = "ERROR", status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


class FetchError(AppError):
    """Upstream page or file could not be read. Parsers may try another source."""
