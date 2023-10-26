# Copyright 2023 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

import datetime
from enum import Enum
from typing import List, Optional, Tuple, Union

from deepl import util


class TextResult:
    """Holds the result of a text translation request."""

    def __init__(self, text: str, detected_source_lang: str):
        self.text = text
        self.detected_source_lang = detected_source_lang

    def __str__(self):
        return self.text


class DocumentHandle:
    """Handle to an in-progress document translation.

    :param document_id: ID of associated document request.
    :param document_key: Key of associated document request.
    """

    def __init__(self, document_id: str, document_key: str):
        self._document_id = document_id
        self._document_key = document_key

    def __str__(self):
        return f"Document ID: {self.document_id}, key: {self.document_key}"

    @property
    def document_id(self) -> str:
        return self._document_id

    @property
    def document_key(self) -> str:
        return self._document_key


class DocumentStatus:
    """Status of a document translation request.

    :param status: One of the Status enum values below.
    :param seconds_remaining: Estimated time until document translation
        completes in seconds, or None if unknown.
    :param billed_characters: Number of characters billed for this document, or
        None if unknown or before translation is complete.
    :param error_message: A short description of the error, or None if no error
        has occurred.
    """

    class Status(Enum):
        QUEUED = "queued"
        TRANSLATING = "translating"
        DONE = "done"
        DOWNLOADED = "downloaded"
        ERROR = "error"

    def __init__(
        self,
        status: Status,
        seconds_remaining=None,
        billed_characters=None,
        error_message=None,
    ):
        self._status = self.Status(status)
        self._seconds_remaining = seconds_remaining
        self._billed_characters = billed_characters
        self._error_message = error_message

    def __str__(self) -> str:
        return self.status.value

    @property
    def ok(self) -> bool:
        return self._status != self.Status.ERROR

    @property
    def done(self) -> bool:
        return self._status == self.Status.DONE

    @property
    def status(self) -> Status:
        return self._status

    @property
    def seconds_remaining(self) -> Optional[int]:
        return self._seconds_remaining

    @property
    def billed_characters(self) -> Optional[int]:
        return self._billed_characters

    @property
    def error_message(self) -> Optional[int]:
        return self._error_message


class GlossaryInfo:
    """Information about a glossary, excluding the entry list.

    :param glossary_id: Unique ID assigned to the glossary.
    :param name: User-defined name assigned to the glossary.
    :param ready: True iff the glossary may be used for translations.
    :param source_lang: Source language code of the glossary.
    :param target_lang: Target language code of the glossary.
    :param creation_time: Timestamp when the glossary was created.
    :param entry_count: The number of entries contained in the glossary.
    """

    def __init__(
        self,
        glossary_id: str,
        name: str,
        ready: bool,
        source_lang: str,
        target_lang: str,
        creation_time: datetime.datetime,
        entry_count: int,
    ):
        self._glossary_id = glossary_id
        self._name = name
        self._ready = ready
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._creation_time = creation_time
        self._entry_count = entry_count

    def __str__(self) -> str:
        return f'Glossary "{self.name}" ({self.glossary_id})'

    @staticmethod
    def from_json(json) -> "GlossaryInfo":
        """Create GlossaryInfo from the given API JSON object."""
        # Workaround for bugs in strptime() in Python 3.6
        creation_time = json["creation_time"]
        if ":" == creation_time[-3:-2]:
            creation_time = creation_time[:-3] + creation_time[-2:]
        if "Z" == creation_time[-1:]:
            creation_time = creation_time[:-1] + "+0000"

        return GlossaryInfo(
            json["glossary_id"],
            json["name"],
            bool(json["ready"]),
            str(json["source_lang"]).upper(),
            str(json["target_lang"]).upper(),
            datetime.datetime.strptime(
                creation_time, "%Y-%m-%dT%H:%M:%S.%f%z"
            ),
            int(json["entry_count"]),
        )

    @property
    def glossary_id(self) -> str:
        return self._glossary_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def source_lang(self) -> str:
        return self._source_lang

    @property
    def target_lang(self) -> str:
        return self._target_lang

    @property
    def creation_time(self) -> datetime.datetime:
        return self._creation_time

    @property
    def entry_count(self) -> int:
        return self._entry_count


class Usage:
    """Holds the result of a usage request.

    The character, document and team_document properties provide details about
    each corresponding usage type. These properties allow each usage type to be
    checked individually.
    The any_limit_reached property checks if for any usage type the amount used
    has reached the allowed amount.
    """

    class Detail:
        def __init__(self, json: Optional[dict], prefix: str):
            self._count = util.get_int_safe(json, f"{prefix}_count")
            self._limit = util.get_int_safe(json, f"{prefix}_limit")

        @property
        def count(self) -> Optional[int]:
            """Returns the amount used for this usage type, may be None."""
            return self._count

        @property
        def limit(self) -> Optional[int]:
            """Returns the maximum amount for this usage type, may be None."""
            return self._limit

        @property
        def valid(self) -> bool:
            """True iff both the count and limit are set for this usage
            type."""
            return self._count is not None and self._limit is not None

        @property
        def limit_reached(self) -> bool:
            """True if this limit is valid and the amount used is greater than
            or equal to the amount allowed, otherwise False."""
            return self.valid and self.count >= self.limit  # type: ignore[operator] # noqa: E501

        @property
        def limit_exceeded(self) -> bool:
            """Deprecated, use limit_reached instead."""
            import warnings

            warnings.warn(
                "limit_reached is deprecated", DeprecationWarning, stacklevel=2
            )
            return self.limit_reached

        def __str__(self) -> str:
            return f"{self.count} of {self.limit}" if self.valid else "Unknown"

    def __init__(self, json: Optional[dict]):
        self._character = self.Detail(json, "character")
        self._document = self.Detail(json, "document")
        self._team_document = self.Detail(json, "team_document")

    @property
    def any_limit_reached(self) -> bool:
        """True if for any API usage type, the amount used is greater than or
        equal to the amount allowed, otherwise False."""
        return (
            self.character.limit_reached
            or self.document.limit_reached
            or self.team_document.limit_reached
        )

    @property
    def any_limit_exceeded(self) -> bool:
        """Deprecated, use any_limit_reached instead."""
        import warnings

        warnings.warn(
            "any_limit_reached is deprecated", DeprecationWarning, stacklevel=2
        )
        return self.any_limit_reached

    @property
    def character(self) -> Detail:
        """Returns usage details for characters, primarily associated with the
        translate_text (/translate) function."""
        return self._character

    @property
    def document(self) -> Detail:
        """Returns usage details for documents."""
        return self._document

    @property
    def team_document(self) -> Detail:
        """Returns usage details for documents shared among your team."""
        return self._team_document

    def __str__(self) -> str:
        details: List[Tuple[str, Usage.Detail]] = [
            ("Characters", self.character),
            ("Documents", self.document),
            ("Team documents", self.team_document),
        ]
        return "Usage this billing period:\n" + "\n".join(
            [f"{label}: {detail}" for label, detail in details if detail.valid]
        )


class Language:
    """Information about a language supported by DeepL translator.

    :param code: Language code according to ISO 639-1, for example "EN".
        Some target languages also include the regional variant according to
        ISO 3166-1, for example "EN-US".
    :param name: Name of the language in English.
    :param supports_formality: (Optional) Specifies whether the formality
        option is available for this language; target languages only.
    """

    def __init__(
        self, code: str, name: str, supports_formality: Optional[bool] = None
    ):
        self.code = code
        self.name = name
        self.supports_formality = supports_formality

    def __str__(self):
        return self.code

    @staticmethod
    def remove_regional_variant(language: Union[str, "Language"]) -> str:
        """Removes the regional variant from a language, e.g. EN-US gives EN"""
        return str(language).upper()[0:2]

    ARABIC = "ar"
    BULGARIAN = "bg"
    CZECH = "cs"
    DANISH = "da"
    GERMAN = "de"
    GREEK = "el"
    ENGLISH = "en"  # Only usable as a source language
    ENGLISH_BRITISH = "en-GB"  # Only usable as a target language
    ENGLISH_AMERICAN = "en-US"  # Only usable as a target language
    SPANISH = "es"
    ESTONIAN = "et"
    FINNISH = "fi"
    FRENCH = "fr"
    HUNGARIAN = "hu"
    INDONESIAN = "id"
    ITALIAN = "it"
    JAPANESE = "ja"
    KOREAN = "ko"
    LITHUANIAN = "lt"
    LATVIAN = "lv"
    NORWEGIAN = "nb"
    DUTCH = "nl"
    POLISH = "pl"
    PORTUGUESE = "pt"  # Only usable as a source language
    PORTUGUESE_BRAZILIAN = "pt-BR"  # Only usable as a target language
    PORTUGUESE_EUROPEAN = "pt-PT"  # Only usable as a target language
    ROMANIAN = "ro"
    RUSSIAN = "ru"
    SLOVAK = "sk"
    SLOVENIAN = "sl"
    SWEDISH = "sv"
    TURKISH = "tr"
    UKRAINIAN = "uk"
    CHINESE = "zh"


class GlossaryLanguagePair:
    """Information about a pair of languages supported for DeepL glossaries.

    :param source_lang: The code of the source language.
    :param target_lang: The code of the target language.
    """

    def __init__(self, source_lang: str, target_lang: str):
        self._source_lang = source_lang
        self._target_lang = target_lang

    @property
    def source_lang(self) -> str:
        """Returns the code of the source language."""
        return self._source_lang

    @property
    def target_lang(self) -> str:
        """Returns the code of the target language."""
        return self._target_lang


class Formality(Enum):
    """Options for formality parameter."""

    LESS = "less"
    """Translate using informal language."""

    DEFAULT = "default"
    """Translate using the default formality."""

    MORE = "more"
    """Translate using formal language."""

    PREFER_MORE = "prefer_more"
    """Translate using formal language if the target language supports
    formality, otherwise use default formality."""

    PREFER_LESS = "prefer_less"
    """Translate using informal language if the target language supports
    formality, otherwise use default formality."""

    def __str__(self):
        return self.value


class SplitSentences(Enum):
    """Options for split_sentences parameter.

    Sets whether the translation engine should first split the input into
    sentences. This is enabled by default. Possible values are:
    - OFF: no splitting at all, whole input is treated as one sentence. Use
        this option if the input text is already split into sentences, to
        prevent the engine from splitting the sentence unintentionally.
    - ALL: (default) splits on punctuation and on newlines.
    - NO_NEWLINES: splits on punctuation only, ignoring newlines.
    """

    OFF = "0"
    ALL = "1"
    NO_NEWLINES = "nonewlines"
    DEFAULT = ALL

    def __str__(self):
        return self.value
