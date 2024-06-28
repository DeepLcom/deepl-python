# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from .version import VERSION as __version__  # noqa

__author__ = "DeepL SE <python-api@deepl.com>"

from .exceptions import (  # noqa
    AuthorizationException,
    ConnectionException,
    DeepLException,
    DocumentNotReadyException,
    DocumentTranslationException,
    GlossaryNotFoundException,
    TooManyRequestsException,
    QuotaExceededException,
)

from . import http_client  # noqa

from .api_data import (
    DocumentHandle,
    DocumentStatus,
    Formality,
    GlossaryInfo,
    Language,
    SplitSentences,
    TextResult,
    Usage,
)

from .translator import Translator


try:
    import asyncio
    import aiohttp
    have_async = True
except ImportError:
    asyncio = None
    aiohttp = None
    have_async = False

if have_async:
    from .translator_async import TranslatorAsync  # noqa

from .util import (  # noqa
    auth_key_is_free_account,
    convert_tsv_to_dict,
    convert_dict_to_tsv,
    validate_glossary_term,
)

__all__ = [
    "__version__",
    "__author__",
    "DocumentHandle",
    "DocumentStatus",
    "Formality",
    "GlossaryInfo",
    "Language",
    "SplitSentences",
    "TextResult",
    "Translator",
    "Usage",
    "http_client",
    "AuthorizationException",
    "ConnectionException",
    "DeepLException",
    "DocumentNotReadyException",
    "DocumentTranslationException",
    "GlossaryNotFoundException",
    "TooManyRequestsException",
    "QuotaExceededException",
    "auth_key_is_free_account",
    "convert_tsv_to_dict",
    "convert_dict_to_tsv",
    "validate_glossary_term",
]
