class MyBaseError(Exception):
    """Base class for all custom exceptions."""
    def __init__(self, message: str ="An error has occurred."):
        self.message: str = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message

class YoutubeError(MyBaseError):
    """Exception raised when unable to retrieve video transcript from YouTube."""
    def __init__(self, message="Unable to retrieve video transcript from YouTube."):
        super().__init__(message)

class UnsupportedFileError(MyBaseError):
    """Exception raised when an unsupported file type is uploaded."""
    def __init__(self, message="Unsupported file type."):
        super().__init__(message)

class AudioError(MyBaseError):
    """Exception raised when an unsupported file type is uploaded."""
    def __init__(self, message="Audio error."):
        super().__init__(message)