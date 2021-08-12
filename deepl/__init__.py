# Copyright 2021 DeepL GmbH (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from .version import VERSION as __version__  # noqa

__author__ = "DeepL GmbH <python-api@deepl.com>"

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
