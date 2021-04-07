class DeepLException(Exception):
    """Base class for deepl module exceptions."""

    pass


class AuthorizationException(DeepLException):
    """Authorization failed, check your authentication key."""

    pass


class QuotaExceededException(DeepLException):
    """Quota for this billing period has been exceeded."""

    pass


class TooManyRequestsException(DeepLException):
    """The maximum number of failed attempts were reached."""

    pass


class ConnectionException(DeepLException):
    """Connection to the DeepL API failed."""

    def __init__(
        self,
        message,
        should_retry=False,
    ):
        super().__init__(message)
        self.should_retry = should_retry


class DocumentTranslationException(DeepLException):
    """Error occurred while translating document."""

    def __init__(self, message, document_request):
        super().__init__(message)
        self.document_request = document_request

    def __str__(self):
        return f"{super()}, document request: {self.document_request}"
