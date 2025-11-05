# Copyright 2023 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

from deepl.util import get_int_safe, parse_timestamp


class TextResult:
    """Holds the result of a text translation request."""

    def __init__(
        self,
        text: str,
        detected_source_lang: str,
        billed_characters: int,
        model_type_used: Optional[str] = None,
    ):
        self.text = text
        self.detected_source_lang = detected_source_lang
        self.billed_characters = billed_characters
        self.model_type_used = model_type_used

    def __str__(self):
        return self.text


class WriteResult:
    """Holds the result of a text improvement request."""

    def __init__(
        self, text: str, detected_source_language: str, target_language: str
    ):
        self.text = text
        self.detected_source_language = detected_source_language
        self.target_language = target_language

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
            self._count = get_int_safe(json, f"{prefix}_count")
            self._limit = get_int_safe(json, f"{prefix}_limit")

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


class MultilingualGlossaryDictionaryEntries:
    def __init__(
        self,
        source_lang: str,
        target_lang: str,
        entries: Dict[str, str],
    ):
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._entries = entries

    def __str__(self) -> str:
        return (
            "MultilingualGlossaryDictionaryEntries: Source Language "
            f"{self._source_lang}, Target Language {self._target_lang} "
            f"Contents: {self._entries}"
        )

    @staticmethod
    def from_json(json) -> "MultilingualGlossaryDictionaryEntries":
        """Create MultilingualGlossaryDictionaryEntries from the given
        API JSON object.
        """
        return MultilingualGlossaryDictionaryEntries(
            str(json["source_lang"]),
            str(json["target_lang"]),
            json["entries"],
        )

    def to_json(self):
        """Create API JSON object from
        MultilingualGlossaryDictionaryEntries
        """
        return {
            "source_lang": self._source_lang,
            "target_lang": self._target_lang,
            "entries": self._entries,
        }

    @property
    def source_lang(self) -> str:
        return self._source_lang

    @property
    def target_lang(self) -> str:
        return self._target_lang

    @property
    def entries(self) -> Dict[str, str]:
        return self._entries


class MultilingualGlossaryDictionaryEntriesResponse:
    def __init__(
        self, dictionaries: List[MultilingualGlossaryDictionaryEntries]
    ):
        self._dictionaries = dictionaries

    def __str__(self) -> str:
        return (
            "MultilingualGlossaryDictionaryEntriesResponse: "
            f"Contents {self._dictionaries}"
        )

    @staticmethod
    def from_json(json) -> "MultilingualGlossaryDictionaryEntriesResponse":
        """Create MultilingualGlossaryDictionaryEntriesResponse from the given
        API JSON object.
        """
        glossary_dicts = list(json["dictionaries"])
        serialized_dicts = list(
            map(
                lambda glossary_dict: MultilingualGlossaryDictionaryEntries.from_json(  # noqa: E501
                    glossary_dict
                ),
                glossary_dicts,
            )
        )
        return MultilingualGlossaryDictionaryEntriesResponse(serialized_dicts)

    @property
    def dictionaries(self) -> List[MultilingualGlossaryDictionaryEntries]:
        return self._dictionaries


class MultilingualGlossaryDictionaryInfo:
    def __init__(self, source_lang: str, target_lang: str, entry_count: int):
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._entry_count = entry_count

    @staticmethod
    def from_json(json) -> "MultilingualGlossaryDictionaryInfo":
        """Create MultilingualGlossaryDictionaryInfo from the given API JSON
        object."""
        return MultilingualGlossaryDictionaryInfo(
            str(json["source_lang"]).upper(),
            str(json["target_lang"]).upper(),
            int(json["entry_count"]),
        )

    @property
    def source_lang(self) -> str:
        return self._source_lang

    @property
    def target_lang(self) -> str:
        return self._target_lang

    @property
    def entry_count(self) -> int:
        return self._entry_count


class MultilingualGlossaryInfo:
    """Information about a multilingual glossary, excluding the entry list.
    Used by the /v3/glossaries API endpoints

    :param glossary_id: Unique ID assigned to the glossary.
    :param name: User-defined name assigned to the glossary.
    :param creation_time: Timestamp when the glossary was created.
    :param dictionaries: Dictionaries contained in this glossary. Each
        dictionary contains its language pair and the number of entries.
    """

    def __init__(
        self,
        glossary_id: str,
        name: str,
        creation_time: datetime.datetime,
        dictionaries: List[MultilingualGlossaryDictionaryInfo],
    ):
        self._glossary_id = glossary_id
        self._name = name
        self._creation_time = creation_time
        self._dictionaries = dictionaries

    def __str__(self) -> str:
        return f'MultilingualGlossary "{self.name}" ({self.glossary_id})'

    @staticmethod
    def from_json(json) -> "MultilingualGlossaryInfo":
        """Create MultilingualGlossaryInfo from the given API JSON object."""
        return MultilingualGlossaryInfo(
            json["glossary_id"],
            json["name"],
            parse_timestamp(json["creation_time"]),
            list(
                map(
                    lambda entry: MultilingualGlossaryDictionaryInfo.from_json(
                        entry
                    ),
                    json["dictionaries"],
                )
            ),
        )

    @staticmethod
    def to_json(self) -> dict:
        """Create API JSON object from MultilingualGlossaryInfo."""
        return {
            "glossary_id": self._glossary_id,
            "name": self._name,
            "creation_time": self._creation_time,
            "dictionaries": self._dictionaries,
        }

    @property
    def glossary_id(self) -> str:
        return self._glossary_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def dictionaries(self) -> List[MultilingualGlossaryDictionaryInfo]:
        return self._dictionaries

    @property
    def creation_time(self) -> datetime.datetime:
        return self._creation_time


class GlossaryInfo:
    """Information about a glossary, excluding the entry list. GlossaryInfo
    is compatible with the /v2 glossary endpoints and can only support
    mono-lingual glossaries (e.g. a glossary with only one source and
    target language defined).

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
        return GlossaryInfo(
            json["glossary_id"],
            json["name"],
            bool(json["ready"]),
            str(json["source_lang"]).upper(),
            str(json["target_lang"]).upper(),
            parse_timestamp(json["creation_time"]),
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


class ModelType(Enum):
    """Options for model_type parameter.

    Sets whether the translation engine should use a newer model type that
    offers higher quality translations at the cost of translation time.
    """

    QUALITY_OPTIMIZED = "quality_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"
    PREFER_QUALITY_OPTIMIZED = "prefer_quality_optimized"

    def __str__(self):
        return self.value


class WritingStyle(Enum):
    """Options for the `style` parameter of the Write API.
    Sets the style the improved text should be in. Note that currently, only
    a style OR a tone is supported.

    When using a style starting with `prefer_`, the style will only be used
    if the chosen or detected language supports it.
    """

    ACADEMIC = "academic"
    BUSINESS = "business"
    CASUAL = "casual"
    DEFAULT = "default"
    PREFER_ACADEMIC = "prefer_academic"
    PREFER_BUSINESS = "prefer_business"
    PREFER_CASUAL = "prefer_casual"
    PREFER_SIMPLE = "prefer_simple"
    SIMPLE = "simple"

    def __str__(self):
        return self.value


class WritingTone(Enum):
    """Options for the `tone` parameter of the Write API.
    Sets the tone the improved text should be in. Note that currently, only
    a style OR a tone is supported.

    When using a tone starting with `prefer_`, the tone will only be used
    if the chosen or detected language supports it.
    """

    CONFIDENT = "confident"
    DEFAULT = "default"
    DIPLOMATIC = "diplomatic"
    ENTHUSIASTIC = "enthusiastic"
    FRIENDLY = "friendly"
    PREFER_CONFIDENT = "prefer_confident"
    PREFER_DIPLOMATIC = "prefer_diplomatic"
    PREFER_ENTHUSIASTIC = "prefer_enthusiastic"
    PREFER_FRIENDLY = "prefer_friendly"

    def __str__(self):
        return self.value


class ConfiguredRules:
    """Configuration rules for a style rule list.

    :param dates_and_times: Date and time formatting rules.
    :param formatting: Text formatting rules.
    :param numbers: Number formatting rules.
    :param punctuation: Punctuation rules.
    :param spelling_and_grammar: Spelling and grammar rules.
    :param style_and_tone: Style and tone rules.
    :param vocabulary: Vocabulary rules.
    """

    def __init__(
        self,
        dates_and_times: Optional[Dict[str, str]] = None,
        formatting: Optional[Dict[str, str]] = None,
        numbers: Optional[Dict[str, str]] = None,
        punctuation: Optional[Dict[str, str]] = None,
        spelling_and_grammar: Optional[Dict[str, str]] = None,
        style_and_tone: Optional[Dict[str, str]] = None,
        vocabulary: Optional[Dict[str, str]] = None,
    ):
        self._dates_and_times = dates_and_times or {}
        self._formatting = formatting or {}
        self._numbers = numbers or {}
        self._punctuation = punctuation or {}
        self._spelling_and_grammar = spelling_and_grammar or {}
        self._style_and_tone = style_and_tone or {}
        self._vocabulary = vocabulary or {}

    @staticmethod
    def from_json(json) -> "ConfiguredRules":
        """Create ConfiguredRules from the given API JSON object."""
        if not json:
            return ConfiguredRules()

        return ConfiguredRules(
            dates_and_times=json.get("dates_and_times"),
            formatting=json.get("formatting"),
            numbers=json.get("numbers"),
            punctuation=json.get("punctuation"),
            spelling_and_grammar=json.get("spelling_and_grammar"),
            style_and_tone=json.get("style_and_tone"),
            vocabulary=json.get("vocabulary"),
        )

    @property
    def dates_and_times(self) -> Dict[str, str]:
        """Returns date and time formatting rules."""
        return self._dates_and_times

    @property
    def formatting(self) -> Dict[str, str]:
        """Returns text formatting rules."""
        return self._formatting

    @property
    def numbers(self) -> Dict[str, str]:
        """Returns number formatting rules."""
        return self._numbers

    @property
    def punctuation(self) -> Dict[str, str]:
        """Returns punctuation rules."""
        return self._punctuation

    @property
    def spelling_and_grammar(self) -> Dict[str, str]:
        """Returns spelling and grammar rules."""
        return self._spelling_and_grammar

    @property
    def style_and_tone(self) -> Dict[str, str]:
        """Returns style and tone rules."""
        return self._style_and_tone

    @property
    def vocabulary(self) -> Dict[str, str]:
        """Returns vocabulary rules."""
        return self._vocabulary


class CustomInstruction:
    """Custom instruction for a style rule.

    :param label: Label for the custom instruction.
    :param prompt: Prompt text for the custom instruction.
    :param source_language: Optional source language code for the custom
        instruction.
    """

    def __init__(
        self,
        label: str,
        prompt: str,
        source_language: Optional[str] = None,
    ):
        self._label = label
        self._prompt = prompt
        self._source_language = source_language

    @staticmethod
    def from_json(json) -> "CustomInstruction":
        """Create CustomInstruction from the given API JSON object."""
        return CustomInstruction(
            label=json["label"],
            prompt=json["prompt"],
            source_language=json.get("source_language"),
        )

    @property
    def label(self) -> str:
        """Returns the label of the custom instruction."""
        return self._label

    @property
    def prompt(self) -> str:
        """Returns the prompt text of the custom instruction."""
        return self._prompt

    @property
    def source_language(self) -> Optional[str]:
        """Returns the source language code, if specified."""
        return self._source_language


class StyleRuleInfo:
    """Information about a style rule list.

    :param style_id: Unique ID assigned to the style rule list.
    :param name: User-defined name assigned to the style rule list.
    :param creation_time: Timestamp when the style rule list was created.
    :param updated_time: Timestamp when the style rule list was last updated.
    :param language: Language code for the style rule list.
    :param version: Version number of the style rule list.
    :param configured_rules: The predefined rules that have been enabled.
    :param custom_instructions: Optional list of custom instructions.
    """

    def __init__(
        self,
        style_id: str,
        name: str,
        creation_time: datetime.datetime,
        updated_time: datetime.datetime,
        language: str,
        version: int,
        configured_rules: Optional[ConfiguredRules] = None,
        custom_instructions: Optional[List[CustomInstruction]] = None,
    ):
        self._style_id = style_id
        self._name = name
        self._creation_time = creation_time
        self._updated_time = updated_time
        self._language = language
        self._version = version
        self._configured_rules = configured_rules
        self._custom_instructions = custom_instructions

    def __str__(self) -> str:
        return f'StyleRule "{self.name}" ({self.style_id})'

    @staticmethod
    def from_json(json) -> "StyleRuleInfo":
        """Create StyleRuleInfo from the given API JSON object."""
        configured_rules_data = json.get("configured_rules")
        configured_rules = None
        if configured_rules_data:
            configured_rules = ConfiguredRules.from_json(configured_rules_data)

        custom_instructions_data = json.get("custom_instructions")
        custom_instructions = None
        if custom_instructions_data:
            custom_instructions = [
                CustomInstruction.from_json(instruction)
                for instruction in custom_instructions_data
            ]

        return StyleRuleInfo(
            style_id=json["style_id"],
            name=json["name"],
            creation_time=parse_timestamp(json["creation_time"]),
            updated_time=parse_timestamp(json["updated_time"]),
            language=json["language"],
            version=json["version"],
            configured_rules=configured_rules,
            custom_instructions=custom_instructions,
        )

    @property
    def style_id(self) -> str:
        """Returns the unique ID of the style rule set."""
        return self._style_id

    @property
    def name(self) -> str:
        """Returns the name of the style rule set."""
        return self._name

    @property
    def creation_time(self) -> datetime.datetime:
        """Returns the creation timestamp."""
        return self._creation_time

    @property
    def updated_time(self) -> datetime.datetime:
        """Returns the last update timestamp."""
        return self._updated_time

    @property
    def language(self) -> str:
        """Returns the language code."""
        return self._language

    @property
    def version(self) -> int:
        """Returns the version number."""
        return self._version

    @property
    def configured_rules(self) -> Optional[ConfiguredRules]:
        """Returns the detailed configuration rules."""
        return self._configured_rules

    @property
    def custom_instructions(self) -> List[CustomInstruction]:
        """Returns the list of custom instructions."""
        return self._custom_instructions or []
