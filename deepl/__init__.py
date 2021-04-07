from .version import VERSION as __version__  # noqa

__author__ = "DeepL GmbH <support@deepl.com>"

from .exceptions import (  # noqa
    AuthorizationException,
    ConnectionException,
    DeepLException,
    DocumentTranslationException,
    TooManyRequestsException,
    QuotaExceededException,
)

from . import http_client  # noqa

from .translator import (  # noqa
    DocumentHandle,
    DocumentStatus,
    Formality,
    Language,
    SplitSentences,
    TextResult,
    Translator,
    Usage,
)
