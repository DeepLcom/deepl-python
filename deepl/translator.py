# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from . import http_client, util
from .exceptions import (
    DocumentNotReadyException,
    GlossaryNotFoundException,
    QuotaExceededException,
    TooManyRequestsException,
    DeepLException,
    AuthorizationException,
    DocumentTranslationException,
)
import datetime
from enum import Enum
import http
import http.client
import json as json_module
import os
import pathlib
import requests
import time
from typing import (
    Any,
    BinaryIO,
    Dict,
    Iterable,
    List,
    Optional,
    TextIO,
    Tuple,
    Union,
)
import urllib.parse


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
        def __init__(self, json: dict, prefix: str):
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
            return self.valid and self.count >= self.limit

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

    def __init__(self, json: dict):
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

    def __str__(self):
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
    def remove_regional_variant(language: Union[str]) -> str:
        """Removes the regional variant from a language, e.g. EN-US gives EN"""
        return str(language).upper()[0:2]

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
    LITHUANIAN = "lt"
    LATVIAN = "lv"
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
    DEFAULT = "default"
    MORE = "more"

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


class Translator:
    """Wrapper for the DeepL API for language translation.

    You must create an instance of Translator to use the DeepL API.

    :param auth_key: Authentication key as found in your DeepL API account.
    :param server_url: (Optional) Base URL of DeepL API, can be overridden e.g.
        for testing purposes.
    :param proxy: (Optional) Proxy server URL string or dictionary containing
        URL strings for the 'http' and 'https' keys. This is passed to the
        underlying requests session, see the requests proxy documentation for
        more information.
    :param skip_language_check: Deprecated, and now has no effect as the
        corresponding internal functionality has been removed. This parameter
        will be removed in a future version.

    All functions may raise DeepLException or a subclass if a connection error
    occurs.
    """

    _DEEPL_SERVER_URL = "https://api.deepl.com"
    _DEEPL_SERVER_URL_FREE = "https://api-free.deepl.com"

    # HTTP status code used by DeepL API to indicate the character limit for
    # this billing period has been reached.
    _HTTP_STATUS_QUOTA_EXCEEDED = 456

    def __init__(
        self,
        auth_key: str,
        *,
        server_url: Optional[str] = None,
        proxy: Union[Dict, str, None] = None,
        skip_language_check: bool = False,
    ):
        if not auth_key:
            raise ValueError("auth_key must not be empty")

        if server_url is None:
            server_url = (
                self._DEEPL_SERVER_URL_FREE
                if util.auth_key_is_free_account(auth_key)
                else self._DEEPL_SERVER_URL
            )

        self._server_url = server_url
        self._client = http_client.HttpClient(proxy)
        self.headers = {"Authorization": f"DeepL-Auth-Key {auth_key}"}

    def __del__(self):
        self.close()

    def _api_call(
        self,
        url: str,
        *,
        method: str = "POST",
        data: Optional[dict] = None,
        stream: bool = False,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Tuple[int, Union[str, requests.Response], dict]:
        """
        Makes a request to the API, and returns response as status code,
        content and JSON object.
        """
        if data is None:
            data = {}
        url = urllib.parse.urljoin(self._server_url, url)

        util.log_info("Request to DeepL API", method=method, url=url)
        util.log_debug("Request details", data=data)

        if headers is None:
            headers = dict()
        headers.update(
            {k: v for k, v in self.headers.items() if k not in headers}
        )

        status_code, content = self._client.request_with_backoff(
            method,
            url,
            data=data,
            stream=stream,
            headers=headers,
            **kwargs,
        )

        json = None
        if isinstance(content, str):
            try:
                json = json_module.loads(content)
            except json_module.JSONDecodeError:
                pass

        util.log_info("DeepL API response", url=url, status_code=status_code)
        util.log_debug("Response details", content=content)

        return status_code, content, json

    def _raise_for_status(
        self,
        status_code: int,
        content: str,
        json: Optional[dict],
        glossary: bool = False,
        downloading_document: bool = False,
    ):
        message = ""
        if json is not None and "message" in json:
            message += ", message: " + json["message"]
        if json is not None and "detail" in json:
            message += ", detail: " + json["detail"]

        if 200 <= status_code < 400:
            return
        elif status_code == http.HTTPStatus.FORBIDDEN:
            raise AuthorizationException(
                f"Authorization failure, check auth_key{message}"
            )
        elif status_code == self._HTTP_STATUS_QUOTA_EXCEEDED:
            raise QuotaExceededException(
                f"Quota for this billing period has been exceeded{message}"
            )
        elif status_code == http.HTTPStatus.NOT_FOUND:
            if glossary:
                raise GlossaryNotFoundException(f"Glossary not found{message}")
            raise DeepLException(f"Not found, check server_url{message}")
        elif status_code == http.HTTPStatus.BAD_REQUEST:
            raise DeepLException(f"Bad request{message}")
        elif status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
            raise TooManyRequestsException(
                "Too many requests, DeepL servers are currently experiencing "
                f"high load{message}"
            )
        elif status_code == http.HTTPStatus.SERVICE_UNAVAILABLE:
            if downloading_document:
                raise DocumentNotReadyException(f"Document not ready{message}")
            else:
                raise DeepLException(f"Service unavailable{message}")
        else:
            status_name = (
                http.client.responses[status_code]
                if status_code in http.client.responses
                else "Unknown"
            )
            raise DeepLException(
                f"Unexpected status code: {status_code} {status_name}, "
                f"content: {content}."
            )

    def _check_valid_languages(
        self, source_lang: Optional[str], target_lang: str
    ):
        """Internal function to check given languages are valid."""
        if target_lang == "EN":
            raise DeepLException(
                'target_lang="EN" is deprecated, please use "EN-GB" or "EN-US"'
                "instead."
            )
        elif target_lang == "PT":
            raise DeepLException(
                'target_lang="PT" is deprecated, please use "PT-PT" or "PT-BR"'
                "instead."
            )

    def _check_language_and_formality(
        self,
        source_lang: Union[str, Language, None],
        target_lang: Union[str, Language],
        formality: Union[str, Formality],
        glossary: Union[str, GlossaryInfo, None] = None,
    ) -> dict:
        # target_lang and source_lang are case insensitive
        target_lang = str(target_lang).upper()
        if source_lang is not None:
            source_lang = str(source_lang).upper()

        if glossary is not None and source_lang is None:
            raise ValueError("source_lang is required if using a glossary")

        if isinstance(glossary, GlossaryInfo):
            if (
                Language.remove_regional_variant(target_lang)
                != glossary.target_lang
                or source_lang != glossary.source_lang
            ):
                raise ValueError(
                    "source_lang and target_lang must match glossary"
                )

        self._check_valid_languages(source_lang, target_lang)

        request_data = {"target_lang": target_lang}
        if source_lang is not None:
            request_data["source_lang"] = source_lang
        if str(formality).lower() != str(Formality.DEFAULT):
            request_data["formality"] = str(formality).lower()
        if isinstance(glossary, GlossaryInfo):
            request_data["glossary_id"] = glossary.glossary_id
        elif glossary is not None:
            request_data["glossary_id"] = glossary
        return request_data

    def close(self):
        if hasattr(self, "_client"):
            self._client.close()

    @property
    def server_url(self):
        return self._server_url

    def translate_text(
        self,
        text: Union[str, Iterable[str]],
        *,
        source_lang: Union[str, Language, None] = None,
        target_lang: Union[str, Language],
        split_sentences: Union[str, SplitSentences] = SplitSentences.ALL,
        preserve_formatting: bool = False,
        formality: Union[str, Formality] = Formality.DEFAULT,
        glossary: Union[str, GlossaryInfo, None] = None,
        tag_handling: Optional[str] = None,
        outline_detection: bool = True,
        non_splitting_tags: Union[str, List[str], None] = None,
        splitting_tags: Union[str, List[str], None] = None,
        ignore_tags: Union[str, List[str], None] = None,
    ) -> Union[TextResult, List[TextResult]]:
        """Translate text(s) into the target language.

        :param text: Text to translate.
        :type text: UTF-8 :class:`str`; string sequence (list, tuple, iterator,
            generator)
        :param source_lang: (Optional) Language code of input text, for example
            "DE", "EN", "FR". If omitted, DeepL will auto-detect the input
            language. If a glossary is used, source_lang must be specified.
        :param target_lang: language code to translate text into, for example
            "DE", "EN-US", "FR".
        :param split_sentences: (Optional) Controls how the translation engine
            should split input into sentences before translation, see
            :class:`SplitSentences`.
        :param preserve_formatting: (Optional) Set to True to prevent the
            translation engine from correcting some formatting aspects, and
            instead leave the formatting unchanged.
        :param formality: (Optional) Desired formality for translation, as
            Formality enum, "less" or "more".
        :param glossary: (Optional) glossary or glossary ID to use for
            translation. Must match specified source_lang and target_lang.
        :param tag_handling: (Optional) Type of tags to parse before
            translation, only "xml" and "html" are currently available.
        :param outline_detection: (Optional) Set to False to disable automatic
            tag detection.
        :param non_splitting_tags: (Optional) XML tags that should not split a
            sentence.
        :type non_splitting_tags: List of XML tags or comma-separated-list of
            tags.
        :param splitting_tags: (Optional) XML tags that should split a
            sentence.
        :type splitting_tags: List of XML tags or comma-separated-list of tags.
        :param ignore_tags: (Optional) XML tags containing text that should not
            be translated.
        :type ignore_tags: List of XML tags or comma-separated-list of tags.
        :return: List of TextResult objects containing results, unless input
            text was one string, then a single TextResult object is returned.
        """
        if isinstance(text, str):
            if len(text) == 0:
                raise ValueError("text must not be empty")
            multi_input = False
        elif hasattr(text, "__iter__"):
            multi_input = True
        else:
            raise TypeError(
                "text parameter must be a string or an iterable of strings"
            )

        request_data = self._check_language_and_formality(
            source_lang,
            target_lang,
            formality,
            glossary,
        )
        request_data["text"] = text

        if str(split_sentences) != str(SplitSentences.DEFAULT):
            request_data["split_sentences"] = str(split_sentences)
        if preserve_formatting:
            request_data["preserve_formatting"] = "1"
        if tag_handling is not None:
            request_data["tag_handling"] = tag_handling
        if not outline_detection:
            request_data["outline_detection"] = "0"

        def join_tags(tag_argument: Union[str, Iterable[str]]) -> str:
            return (
                tag_argument
                if isinstance(tag_argument, str)
                else ",".join(tag_argument)
            )

        if non_splitting_tags is not None:
            request_data["non_splitting_tags"] = join_tags(non_splitting_tags)
        if splitting_tags is not None:
            request_data["splitting_tags"] = join_tags(splitting_tags)
        if ignore_tags is not None:
            request_data["ignore_tags"] = join_tags(ignore_tags)

        status, content, json = self._api_call(
            "v2/translate", data=request_data
        )

        self._raise_for_status(status, content, json)

        translations = json.get("translations", [])
        output = []
        for translation in translations:
            text = translation.get("text")
            lang = translation.get("detected_source_language")
            output.append(TextResult(text, detected_source_lang=lang))

        return output if multi_input else output[0]

    def translate_text_with_glossary(
        self,
        text: Union[str, Iterable[str]],
        glossary: GlossaryInfo,
        target_lang: Union[str, Language, None] = None,
        **kwargs,
    ) -> Union[TextResult, List[TextResult]]:
        """Translate text(s) using given glossary. The source and target
        languages are assumed to match the glossary languages.

        Note that if the glossary target language is English (EN), the text
        will be translated into British English (EN-GB). To instead translate
        into American English specify target_lang="EN-US".

        :param text: Text to translate.
        :type text: UTF-8 :class:`str`; string sequence (list, tuple, iterator,
            generator)
        :param glossary: glossary to use for translation.
        :type glossary: :class:`GlossaryInfo`.
        :param target_lang: override target language of glossary.
        :return: List of TextResult objects containing results, unless input
            text was one string, then a single TextResult object is returned.
        """

        if not isinstance(glossary, GlossaryInfo):
            msg = (
                "This function expects the glossary parameter to be an "
                "instance of GlossaryInfo. Use get_glossary() to obtain a "
                "GlossaryInfo using the glossary ID of an existing "
                "glossary. Alternatively, use translate_text() and "
                "specify the glossary ID using the glossary parameter. "
            )
            raise ValueError(msg)

        if target_lang is None:
            target_lang = glossary.target_lang
            if target_lang == "EN":
                target_lang = "EN-GB"

        return self.translate_text(
            text,
            source_lang=glossary.source_lang,
            target_lang=target_lang,
            glossary=glossary,
            **kwargs,
        )

    def translate_document_from_filepath(
        self,
        input_path: Union[str, pathlib.PurePath],
        output_path: Union[str, pathlib.PurePath],
        *,
        source_lang: Optional[str] = None,
        target_lang: str,
        formality: Union[str, Formality] = Formality.DEFAULT,
        glossary: Union[str, GlossaryInfo, None] = None,
    ) -> DocumentStatus:
        """Upload document at given input path, translate it into the target
        language, and download result to given output path.

        :param input_path: Path to document to be translated.
        :param output_path: Path to store translated document.
        :param source_lang: (Optional) Language code of input document, for
            example "DE", "EN", "FR". If omitted, DeepL will auto-detect the
            input language.
        :param target_lang: Language code to translate document into, for
            example "DE", "EN-US", "FR".
        :param formality: (Optional) Desired formality for translation, as
            Formality enum, "less" or "more".
        :param glossary: (Optional) glossary or glossary ID to use for
            translation. Must match specified source_lang and target_lang.
        :return: DocumentStatus when document translation completed, this
            allows the number of billed characters to be queried.

        :raises DocumentTranslationException: If an error occurs during
            translation. The exception includes information about the document
            request.
        """
        with open(input_path, "rb") as in_file:
            with open(output_path, "wb") as out_file:
                try:
                    return self.translate_document(
                        in_file,
                        out_file,
                        target_lang=target_lang,
                        source_lang=source_lang,
                        formality=formality,
                        glossary=glossary,
                    )
                except Exception as e:
                    out_file.close()
                    os.unlink(output_path)
                    raise e

    def translate_document(
        self,
        input_document: Union[TextIO, BinaryIO, Any],
        output_document: Union[TextIO, BinaryIO, Any],
        *,
        source_lang: Optional[str] = None,
        target_lang: str,
        formality: Union[str, Formality] = Formality.DEFAULT,
        glossary: Union[str, GlossaryInfo, None] = None,
    ) -> DocumentStatus:
        """Upload document, translate it into the target language, and download
        result.

        :param input_document: Document to translate as a file-like object. It
            is recommended to open files in binary mode.
        :param output_document: File-like object to receive translated
            document.
        :param source_lang: (Optional) Language code of input document, for
            example "DE", "EN", "FR". If omitted, DeepL will auto-detect the
            input language.
        :param target_lang: Language code to translate document into, for
            example "DE", "EN-US", "FR".
        :param formality: (Optional) Desired formality for translation, as
            Formality enum, "less" or "more".
        :param glossary: (Optional) glossary or glossary ID to use for
            translation. Must match specified source_lang and target_lang.
        :return: DocumentStatus when document translation completed, this
            allows the number of billed characters to be queried.

        :raises DocumentTranslationException: If an error occurs during
            translation, the exception includes the document handle.
        """

        handle = self.translate_document_upload(
            input_document,
            target_lang=target_lang,
            source_lang=source_lang,
            formality=formality,
            glossary=glossary,
        )

        try:
            status = self.translate_document_wait_until_done(handle)
            if status.ok:
                self.translate_document_download(handle, output_document)
        except Exception as e:
            raise DocumentTranslationException(str(e), handle) from e

        if not status.ok:
            error_message = status.error_message or "unknown error"
            raise DocumentTranslationException(
                f"Error occurred while translating document: {error_message}",
                handle,
            )
        return status

    def translate_document_upload(
        self,
        input_document: Union[TextIO, BinaryIO, str, bytes, Any],
        *,
        source_lang: Optional[str] = None,
        target_lang: str,
        formality: Union[str, Formality] = Formality.DEFAULT,
        glossary: Union[str, GlossaryInfo, None] = None,
        filename: Optional[str] = None,
    ) -> DocumentHandle:
        """Upload document to be translated and return handle associated with
        request.

        :param input_document: Document to translate as a file-like object, or
            string or bytes containing file content.
        :param source_lang: (Optional) Language code of input document, for
            example "DE", "EN", "FR". If omitted, DeepL will auto-detect the
            input language.
        :param target_lang: Language code to translate document into, for
            example "DE", "EN-US", "FR".
        :param formality: (Optional) Desired formality for translation, as
            Formality enum, "less" or "more".
        :param glossary: (Optional) glossary or glossary ID to use for
            translation. Must match specified source_lang and target_lang.
        :param filename: (Optional) Filename including extension, only required
            if uploading string or bytes containing file content.
        :return: DocumentHandle with ID and key identifying document.
        """

        request_data = self._check_language_and_formality(
            source_lang, target_lang, formality, glossary
        )

        if isinstance(input_document, (str, bytes)):
            if filename is None:
                raise ValueError(
                    "filename is required if uploading file content as string "
                    "or bytes"
                )
            files = {"file": (filename, input_document)}
        else:
            files = {"file": input_document}
        status, content, json = self._api_call(
            "v2/document", data=request_data, files=files
        )
        self._raise_for_status(status, content, json)

        return DocumentHandle(json["document_id"], json["document_key"])

    def translate_document_get_status(
        self, handle: DocumentHandle
    ) -> DocumentStatus:
        """Gets the status of the document translation request associated with
         given handle.

        :param handle: DocumentHandle to the request to check.
        :return: DocumentStatus containing the request status.
        """

        data = {"document_key": handle.document_key}
        url = f"v2/document/{handle.document_id}"

        status, content, json = self._api_call(url, data=data)

        self._raise_for_status(status, content, json)

        status = json["status"]
        seconds_remaining = json.get("seconds_remaining", None)
        billed_characters = json.get("billed_characters", None)
        error_message = json.get("error_message", None)
        return DocumentStatus(
            status, seconds_remaining, billed_characters, error_message
        )

    def translate_document_wait_until_done(
        self, handle: DocumentHandle
    ) -> DocumentStatus:
        """
        Continually polls the status of the document translation associated
        with the given handle, sleeping in between requests, and returns the
        final status when the translation completes (whether successful or
        not).

        :param handle: DocumentHandle to the document translation to wait on.
        :return: DocumentStatus containing the status when completed.
        """
        status = self.translate_document_get_status(handle)
        while status.ok and not status.done:
            secs = (status.seconds_remaining or 0) / 2.0 + 1.0
            secs = max(1.0, min(secs, 60.0))
            util.log_info(
                f"Rechecking document translation status "
                f"after sleeping for {secs:.3f} seconds."
            )
            time.sleep(secs)
            status = self.translate_document_get_status(handle)
        return status

    def translate_document_download(
        self,
        handle: DocumentHandle,
        output_file: Union[TextIO, BinaryIO, Any, None] = None,
        chunk_size: int = 1,
    ) -> Optional[requests.Response]:
        """Downloads the translated document for the request associated with
        given handle and returns a response object for streaming the data. Call
        iter_content() on the response object to read streamed file data.
        Alternatively, a file-like object may be given as output_file where the
        complete file will be downloaded and written to.

        :param handle: DocumentHandle associated with request.
        :param output_file: (Optional) File-like object to store downloaded
            document. If not provided, use iter_content() on the returned
            response object to read streamed file data.
        :param chunk_size: (Optional) Size of chunk in bytes for streaming.
            Only used if output_file is specified.
        :return: None if output_file is specified, otherwise the
            requests.Response will be returned.
        """

        data = {"document_key": handle.document_key}
        url = f"v2/document/{handle.document_id}/result"

        status_code, response, json = self._api_call(
            url, data=data, stream=True
        )

        self._raise_for_status(
            status_code, "<file>", json, downloading_document=True
        )

        if output_file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                output_file.write(chunk)
            return None
        else:
            return response

    def get_source_languages(self, skip_cache=False) -> List[Language]:
        """Request the list of available source languages.

        :param skip_cache: Deprecated, and now has no effect as the
            corresponding internal functionality has been removed. This
            parameter will be removed in a future version.
        :return: List of supported source languages.
        """
        status, content, json = self._api_call("v2/languages")
        self._raise_for_status(status, content, json)
        return [
            Language(
                language["language"],
                language["name"],
            )
            for language in json
        ]

    def get_target_languages(self, skip_cache=False) -> List[Language]:
        """Request the list of available target languages.

        :param skip_cache: Deprecated, and now has no effect as the
            corresponding internal functionality has been removed. This
            parameter will be removed in a future version.
        :return: List of supported target languages.
        """
        data = {"type": "target"}
        status, content, json = self._api_call("v2/languages", data=data)
        self._raise_for_status(status, content, json)
        return [
            Language(
                language["language"],
                language["name"],
                language.get("supports_formality", None),
            )
            for language in json
        ]

    def get_glossary_languages(self) -> List[GlossaryLanguagePair]:
        """Request the list of language pairs supported for glossaries."""
        status, content, json = self._api_call(
            "v2/glossary-language-pairs", method="GET"
        )

        self._raise_for_status(status, content, json)

        return [
            GlossaryLanguagePair(
                language_pair["source_lang"], language_pair["target_lang"]
            )
            for language_pair in json["supported_languages"]
        ]

    def get_usage(self) -> Usage:
        """Requests the current API usage."""
        status, content, json = self._api_call("v2/usage")

        self._raise_for_status(status, content, json)

        return Usage(json)

    def create_glossary(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        entries: Dict[str, str],
    ) -> GlossaryInfo:
        """Creates a glossary with given name for the source and target
        languages, containing the entries in dictionary. The glossary may be
        used in the translate_text functions.

        Only certain language pairs are supported. The available language pairs
        can be queried using get_glossary_languages(). Glossaries are not
        regional specific: a glossary with target language EN may be used to
        translate texts into both EN-US and EN-GB.

        This function requires the glossary entries to be provided as a
        dictionary of source-target terms. To create a glossary from a CSV file
        downloaded from the DeepL website, see create_glossary_from_csv().

        :param name: user-defined name to attach to glossary.
        :param source_lang: Language of source terms.
        :param target_lang: Language of target terms.
        :param entries: dictionary of terms to insert in glossary, with the
            keys and values representing source and target terms respectively.
        :return: GlossaryInfo containing information about created glossary.

        :raises ValueError: If the glossary name is empty, or entries are
            empty or invalid.
        :raises DeepLException: If source and target language pair are not
            supported for glossaries.
        """
        # glossaries are only supported for base language types
        target_lang = Language.remove_regional_variant(target_lang)
        source_lang = Language.remove_regional_variant(source_lang)

        if not name:
            raise ValueError("glossary name must not be empty")
        if not entries:
            raise ValueError("glossary entries must not be empty")

        request_data = {
            "name": name,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "entries_format": "tsv",
            "entries": util.convert_dict_to_tsv(entries),
        }

        status, content, json = self._api_call(
            "v2/glossaries", data=request_data
        )
        self._raise_for_status(status, content, json, glossary=True)
        return GlossaryInfo.from_json(json)

    def get_glossary(self, glossary_id: str) -> GlossaryInfo:
        """Retrieves GlossaryInfo for the glossary with specified ID.

        :param glossary_id: ID of glossary to retrieve.
        :return: GlossaryInfo with information about specified glossary.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        """
        status, content, json = self._api_call(
            f"v2/glossaries/{glossary_id}", method="GET"
        )
        self._raise_for_status(status, content, json, glossary=True)
        return GlossaryInfo.from_json(json)

    def list_glossaries(self) -> List[GlossaryInfo]:
        """Retrieves GlossaryInfo for all available glossaries.

        :return: list of GlossaryInfo for all available glossaries.
        """
        status, content, json = self._api_call("v2/glossaries", method="GET")
        self._raise_for_status(status, content, json, glossary=True)
        return [
            GlossaryInfo.from_json(glossary) for glossary in json["glossaries"]
        ]

    def get_glossary_entries(self, glossary: Union[str, GlossaryInfo]) -> dict:
        """Retrieves the entries of the specified glossary and returns them as
        a dictionary.

        :param glossary: GlossaryInfo or ID of glossary to retrieve.
        :return: dictionary of glossary entries.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        """
        if isinstance(glossary, GlossaryInfo):
            glossary_id = glossary.glossary_id
        else:
            glossary_id = glossary

        status, content, json = self._api_call(
            f"v2/glossaries/{glossary_id}/entries",
            method="GET",
            headers={"Accept": "text/tab-separated-values"},
        )
        self._raise_for_status(status, content, json, glossary=True)
        return util.convert_tsv_to_dict(content)

    def delete_glossary(self, glossary: Union[str, GlossaryInfo]) -> None:
        """Deletes specified glossary.

        :param glossary: GlossaryInfo or ID of glossary to delete.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        """
        if isinstance(glossary, GlossaryInfo):
            glossary_id = glossary.glossary_id
        else:
            glossary_id = glossary

        status, content, json = self._api_call(
            f"v2/glossaries/{glossary_id}",
            method="DELETE",
        )
        self._raise_for_status(status, content, json, glossary=True)
