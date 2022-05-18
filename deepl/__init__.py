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

from .translator import (  # noqa
    DocumentHandle,
    DocumentStatus,
    Formality,
    GlossaryInfo,
    Language,
    SplitSentences,
    TextResult,
    Translator,
    Usage,
)

from .util import (  # noqa
    auth_key_is_free_account,
    convert_tsv_to_dict,
    convert_dict_to_tsv,
    validate_glossary_term,
)
