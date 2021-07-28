from . import http_client, util
from .exceptions import (
    QuotaExceededException,
    TooManyRequestsException,
    DeepLException,
    AuthorizationException,
    DocumentTranslationException,
)
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
    def document_id(self):
        return self._document_id

    @property
    def document_key(self):
        return self._document_key


class DocumentStatus:
    """Status of a document translation request.

    :param status: One of the Status enum values below.
    :param seconds_remaining: Estimated time until document translation
        completes in seconds, or None if unknown.
    :param billed_characters: Number of characters billed for this document, or
        None if unknown or before translation is complete.
    """

    class Status(Enum):
        QUEUED = "queued"
        TRANSLATING = "translating"
        DONE = "done"
        DOWNLOADED = "downloaded"
        ERROR = "error"

    def __init__(
        self, status: Status, seconds_remaining=None, billed_characters=None
    ):
        self._status = self.Status(status)
        self._seconds_remaining = seconds_remaining
        self._billed_characters = billed_characters

    def __str__(self):
        return self.status.value

    @property
    def ok(self):
        return self._status != self.Status.ERROR

    @property
    def done(self):
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


class Usage:
    """Holds the result of a usage request.

    The character, document and team_document properties provide details about
    each corresponding usage type. These properties allow each usage type to be
    checked individually.
    The any_limit_exceeded property checks if any usage type is exceeded.
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
            """True iff both the count and limit are set for this usage type."""
            return self._count is not None and self._limit is not None

        @property
        def limit_exceeded(self) -> bool:
            """True iff this limit is valid and exceeded."""
            return self.valid and self.count >= self.limit

        def __str__(self) -> str:
            return f"{self.count} of {self.limit}" if self.valid else "Unknown"

    def __init__(self, json: dict):
        self._character = self.Detail(json, "character")
        self._document = self.Detail(json, "document")
        self._team_document = self.Detail(json, "team_document")

    @property
    def any_limit_exceeded(self) -> bool:
        """True if any API function limit is exceeded."""
        return (
            self.character.limit_exceeded
            or self.document.limit_exceeded
            or self.team_document.limit_exceeded
        )

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
    :param skip_language_check: (Optional) Set to True to override automatic
        request of available languages.
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
        skip_language_check: bool = False,
    ):
        if not auth_key:
            raise ValueError("auth_key must not be empty")
        self._auth_key = auth_key

        if server_url is None:
            server_url = (
                self._DEEPL_SERVER_URL_FREE
                if auth_key.endswith(":fx")
                else self._DEEPL_SERVER_URL
            )

        self._server_url = server_url
        self._client = http_client.HttpClient()
        self.headers = {}

        self._skip_language_check = skip_language_check
        self._source_languages_cached = None
        self._target_languages_cached = None

    def __del__(self):
        self.close()

    def _api_call(
        self,
        url: str,
        *,
        method: str = "POST",
        data: Optional[dict] = None,
        stream: bool = False,
        **kwargs,
    ) -> Tuple[int, Union[str, requests.Response], dict]:
        """
        Makes a request to the API, and returns response as status code,
        content and JSON object.
        """
        if data is None:
            data = {}
        data["auth_key"] = self._auth_key
        url = urllib.parse.urljoin(self._server_url, url)

        util.log_info("Request to DeepL API", method=method, url=url)
        util.log_debug("Request details", data=data)

        status_code, content = self._client.request_with_backoff(
            method,
            url,
            data=data,
            stream=stream,
            headers=self.headers,
            **kwargs,
        )

        json = None
        if isinstance(content, str):
            try:
                json = json_module.loads(content)
            except json_module.JSONDecodeError:
                pass

        util.log_info("DeepL API response", url=url, status_code=status_code)
        util.log_debug("Response details", content=content, json=json)

        return status_code, content, json

    def _raise_for_status(
        self, status_code: int, content: str, json: Optional[dict]
    ):
        if json is not None and "message" in json:
            message = ", message: " + json["message"]
        else:
            message = ""
        if 200 <= status_code < 400:
            return
        elif status_code == http.HTTPStatus.FORBIDDEN:
            raise AuthorizationException(
                "Authorization failure, check auth_key"
            )
        elif status_code == self._HTTP_STATUS_QUOTA_EXCEEDED:
            raise QuotaExceededException(
                "Quota for this billing period has been exceeded."
            )
        elif status_code == http.HTTPStatus.NOT_FOUND:
            raise DeepLException(f"Not found, check server_url{message}")
        elif status_code == http.HTTPStatus.BAD_REQUEST:
            raise DeepLException(f"Bad request{message}")
        elif status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
            raise TooManyRequestsException(
                "Too many requests, DeepL servers are currently experiencing high load"
            )
        else:
            status_name = (
                http.client.responses[status_code]
                if status_code in http.client.responses
                else "Unknown"
            )
            raise DeepLException(
                f"Unexpected status code: {status_code} {status_name}, content: {content}."
            )

    def _request_languages(self, target: bool) -> List[Language]:
        """Internal function to make a /languages request and cache the result."""
        data = {"type": "target"} if target else {}
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

    def _check_valid_languages(
        self, source_lang: Optional[str], target_lang: str
    ):
        """Internal function to check given languages match available languages."""
        if target_lang == "EN":
            raise DeepLException(
                'target_lang="EN" is deprecated, please use "EN-GB" or "EN-US" instead.'
            )
        elif target_lang == "PT":
            raise DeepLException(
                'target_lang="PT" is deprecated, please use "PT-PT" or "PT-BR" instead.'
            )

        if self._skip_language_check:
            return

        if source_lang is not None and not any(
            source_lang == lang.code for lang in self.get_source_languages()
        ):
            raise DeepLException(
                f"source_lang ({source_lang}) must be one of the supported "
                "language codes, or None for auto-detection"
            )

        if not any(
            target_lang == lang.code for lang in self.get_target_languages()
        ):
            raise DeepLException(
                f"target_lang ({target_lang}) must be one of the supported language codes"
            )

    def _check_language_and_formality(
        self,
        source_lang: Optional[str],
        target_lang: str,
        formality: Union[str, Formality],
    ) -> dict:
        # target_lang and source_lang are case insensitive
        target_lang = str(target_lang).upper()
        if source_lang is not None:
            source_lang = str(source_lang).upper()

        self._check_valid_languages(source_lang, target_lang)

        request_data = {"target_lang": target_lang}
        if source_lang is not None:
            request_data["source_lang"] = source_lang
        if str(formality) != str(Formality.DEFAULT):
            request_data["formality"] = str(formality).lower()
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
        source_lang: Optional[str] = None,
        target_lang: str,
        split_sentences: Union[str, SplitSentences] = SplitSentences.ALL,
        preserve_formatting: bool = False,
        formality: Union[str, Formality] = Formality.DEFAULT,
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
            language.
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
        :param tag_handling: (Optional) Type of tags to parse before
            translation, only "xml" is currently available.
        :param outline_detection: (Optional) Set to False to disable automatic
            tag detection.
        :param non_splitting_tags: (Optional) Tags that should not split a
            sentence.
        :type non_splitting_tags: List of tags or comma-separated-list of tags.
        :param splitting_tags: (Optional) Tags that should split a sentence.
        :type splitting_tags: List of tags or comma-separated-list of tags.
        :param ignore_tags: (Optional) Tags containing text that should not be
            translated.
        :type ignore_tags: List of tags or comma-separated-list of tags.
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
            source_lang, target_lang, formality
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

    def translate_document_from_filepath(
        self,
        input_path: Union[str, pathlib.PurePath],
        output_path: Union[str, pathlib.PurePath],
        *,
        source_lang: Optional[str] = None,
        target_lang: str,
        formality: Union[str, Formality] = Formality.DEFAULT,
    ) -> None:
        """Upload document at given input path, translate it into the target
        language, and download result to given output path.

        :param input_path: Path to document to be translated.
        :param output_path: Path to store translated document.
        :param source_lang: (Optional) Language code of input document, for example "DE",
            "EN", "FR". If omitted, DeepL will auto-detect the input language.
        :param target_lang: Language code to translate document into, for example "DE",
            "EN-US", "FR".
        :param formality: (Optional) Desired formality for translation, as Formality
            enum, "less" or "more".

        :raises DocumentTranslationException: If an error occurs during translation,
            The exception includes information about the document request.
        """
        with open(input_path, "rb") as in_file:
            with open(output_path, "wb") as out_file:
                try:
                    self.translate_document(
                        in_file,
                        out_file,
                        target_lang=target_lang,
                        source_lang=source_lang,
                        formality=formality,
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
    ) -> None:
        """Upload document, translate it into the target language, and download
        result.

        :param input_document: Document to translate as a file-like object. It
            is recommended to open files in binary mode.
        :param output_document: File-like object to receive translated document.
        :param source_lang: (Optional) Language code of input document, for
            example "DE", "EN", "FR". If omitted, DeepL will auto-detect the
            input language.
        :param target_lang: Language code to translate document into, for
            example "DE", "EN-US", "FR".
        :param formality: (Optional) Desired formality for translation, as
            Formality enum, "less" or "more".

        :raises DocumentTranslationException: If an error occurs during
            translation, the exception includes the document handle.
        """

        handle = self.translate_document_upload(
            input_document,
            target_lang=target_lang,
            source_lang=source_lang,
            formality=formality,
        )

        try:
            status = self.translate_document_get_status(handle)
            while status.ok and not status.done:
                secs = (status.seconds_remaining or 0) / 2 + 1
                time.sleep(secs)
                status = self.translate_document_get_status(handle)

            if status.ok:
                self.translate_document_download(handle, output_document)
        except Exception as e:
            raise DocumentTranslationException(str(e), handle) from e

        if not status.ok:
            raise DocumentTranslationException(
                "Error occurred while translating document", handle
            )

    def translate_document_upload(
        self,
        input_document: Union[TextIO, BinaryIO, str, bytes, Any],
        *,
        source_lang: Optional[str] = None,
        target_lang: str,
        formality: Union[str, Formality] = Formality.DEFAULT,
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
        :return: DocumentHandle with ID & key identifying document.
        """

        request_data = self._check_language_and_formality(
            source_lang, target_lang, formality
        )

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
        return DocumentStatus(status, seconds_remaining, billed_characters)

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

        if status_code == http.HTTPStatus.SERVICE_UNAVAILABLE:
            raise DeepLException("Document not ready for download")
        self._raise_for_status(status_code, "<file>", json)

        if output_file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                output_file.write(chunk)
            return None
        else:
            return response

    def get_source_languages(self, skip_cache=False) -> List[Language]:
        """Request the list of available source languages."""
        if self._source_languages_cached is None or skip_cache:
            self._source_languages_cached = self._request_languages(
                target=False
            )
        return self._source_languages_cached

    def get_target_languages(self, skip_cache=False) -> List[Language]:
        """Request the list of available target languages."""
        if self._target_languages_cached is None or skip_cache:
            self._target_languages_cached = self._request_languages(
                target=True
            )
        return self._target_languages_cached

    def get_usage(self) -> Usage:
        """Requests the current API usage."""
        status, content, json = self._api_call("v2/usage")

        self._raise_for_status(status, content, json)

        return Usage(json)
