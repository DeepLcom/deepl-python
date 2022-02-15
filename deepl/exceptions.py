# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.


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
    """Connection to the DeepL API failed.

    :param message: Message describing the error that occurred.
    :param should_retry: True if the request would normally be retried
        following this error, otherwise false.
    """

    def __init__(
        self,
        message,
        should_retry=False,
    ):
        super().__init__(message)
        self.should_retry = should_retry


class DocumentTranslationException(DeepLException):
    """Error occurred while translating document.

    :param message: Message describing the error that occurred.
    :param document_handle: The document handle of the associated document.
    """

    def __init__(self, message, document_handle):
        super().__init__(message)
        self.document_handle = document_handle

    def __str__(self):
        return f"{super().__str__()}, document handle: {self.document_handle}"

    @property
    def document_request(self):
        """Deprecated, use document_handle instead."""
        import warnings

        warnings.warn(
            "document_request is deprecated", DeprecationWarning, stacklevel=2
        )
        return self.document_handle


class GlossaryNotFoundException(DeepLException):
    """The specified glossary was not found."""

    pass


class DocumentNotReadyException(DeepLException):
    """The translation of the specified document is not yet complete."""

    pass
