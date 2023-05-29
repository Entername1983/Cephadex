class YoutubeError(Exception):
    def __init__(self, message="Unable to retrieve video transcript from YouTube."):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message