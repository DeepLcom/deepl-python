# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import http
import http.client
import json as json_module
import platform
import traceback
import urllib.parse
from abc import abstractmethod
from functools import lru_cache
from typing import (
    Any,
    BinaryIO,
    Dict,
    Iterable,
    List,
    Optional,
    TextIO,
    Union,
    Iterator,
    Callable,
)

import requests  # type: ignore
from requests.structures import CaseInsensitiveDict

from deepl.api_data import (
    DocumentHandle,
    DocumentStatus,
    Formality,
    GlossaryInfo,
    GlossaryLanguagePair,
    Language,
    SplitSentences,
    TextResult,
    Usage,
)
from . import http_client, util
from . import version
from .exceptions import (
    DocumentNotReadyException,
    GlossaryNotFoundException,
    QuotaExceededException,
    TooManyRequestsException,
    DeepLException,
    AuthorizationException,
    DocumentTranslationException,
)


class HttpRequest:
    """
    HttpRequest contains information to construct an HTTP request,
    implementations of IHttpClient should implement prepare_request to
    convert it into their implementation-specific model of requests.

    :param method: HTTP method e.g. "GET".
    :param url: Request URL e.g. "https://api.deepl.com/v2/translate"
    :param headers: HTTP headers.
    :param json: If not None, the request body to encode as JSON.
    :param data: HTTP data to include as multipart-form
    :param files: If not None, files to include as multipart-form
    :param stream: If true, the response body should not be read immediately as
        it will be handled subsequently, see HttpResponse.raw_response()
    :param stream_chunks: If true, the response body should be streamed to the
        given callable.
    """

    def __init__(
        self,
        method: str,
        url: str,
        headers: CaseInsensitiveDict[str, str],
        json: Optional[dict],
        data: Optional[dict],
        files: Optional[Dict[str, Any]],
        stream: bool,
        stream_chunks: Optional[Callable[[bytes], None]],
    ):
        self.method = method
        self.url = url
        self.headers = headers
        self.data = data
        self.json = json
        self.files = files
        self.stream = stream
        self.stream_chunks = stream_chunks


class HttpResponse:
    def __init__(
        self,
        status_code: int,
        text: Optional[str],
        headers: dict[str, str],
    ):
        self._status_code = status_code
        self._text = text
        self._headers = CaseInsensitiveDict(headers)

        try:
            self._json = json_module.loads(self._text) if self._text else None
        except json_module.JSONDecodeError:
            self._json = None

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def text(self) -> Optional[str]:
        return self._text

    @property
    def headers(self) -> CaseInsensitiveDict[str]:
        return self._headers

    @property
    def json(self) -> Optional[Any]:
        return self._json

    @abstractmethod
    def raw_response(self) -> Any:
        """
        TODO
        """
        raise NotImplementedError()

    @abstractmethod
    def iter_content(self, chunk_size) -> Iterator[bytes]:
        """
        Implementations should return an iterator that returns the content.
        """
        raise NotImplementedError()


class BaseContext:
    """
    Used by TranslatorBase to include extra context among pre- and post-request
    functions.
    """

    def __init__(
        self,
    ):
        pass


class TranslatorBase:
    """
    Base class for synchronous and asynchronous Translator classes.
    Handles synchronous preparation of HTTP requests and interpretation of
    HTTP responses.
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
        send_platform_info: bool = True,
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
        self.headers = {"Authorization": f"DeepL-Auth-Key {auth_key}"}

        self._send_platform_info = send_platform_info
        self._set_user_agent(None, None)

    def _prepare_http_request(
        self,
        url: str,
        headers: Dict[str, str] = None,
        method: str = "POST",
        data: Optional[dict] = None,
        json: Optional[dict] = None,
        files: Optional[dict[str, Any]] = None,
        stream: bool = False,
        stream_chunks: Optional[Callable[[bytes], None]] = None,
    ) -> HttpRequest:
        if data is not None and json is not None:
            raise ValueError("cannot accept both json and data")

        url = urllib.parse.urljoin(self._server_url, url)

        if headers is None:
            headers = {}
        headers.update(
            {k: v for k, v in self.headers.items() if k not in headers}
        )
        return HttpRequest(
            method, url, headers, json, data, files, stream, stream_chunks
        )

    def _raise_for_status(
        self,
        response: HttpResponse,
        glossary_management: bool = False,
        downloading_document: bool = False,
    ):
        message = ""
        if response.json is not None:
            if "message" in response.json:
                message += ", message: " + response.json["message"]
            if "detail" in response.json:
                message += ", detail: " + response.json["detail"]

        status_code = response.status_code
        if 200 <= status_code < 400:
            return
        elif status_code == http.HTTPStatus.FORBIDDEN:
            raise AuthorizationException(
                f"Authorization failure, check auth_key{message}",
                http_status_code=status_code,
            )
        elif status_code == self._HTTP_STATUS_QUOTA_EXCEEDED:
            raise QuotaExceededException(
                f"Quota for this billing period has been exceeded{message}",
                http_status_code=status_code,
            )
        elif status_code == http.HTTPStatus.NOT_FOUND:
            if glossary_management:
                raise GlossaryNotFoundException(
                    f"Glossary not found{message}",
                    http_status_code=status_code,
                )
            raise DeepLException(
                f"Not found, check server_url{message}",
                http_status_code=status_code,
            )
        elif status_code == http.HTTPStatus.BAD_REQUEST:
            raise DeepLException(
                f"Bad request{message}", http_status_code=status_code
            )
        elif status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
            raise TooManyRequestsException(
                "Too many requests, DeepL servers are currently experiencing "
                f"high load{message}",
                should_retry=True,
                http_status_code=status_code,
            )
        elif status_code == http.HTTPStatus.SERVICE_UNAVAILABLE:
            if downloading_document:
                raise DocumentNotReadyException(
                    f"Document not ready{message}",
                    should_retry=True,
                    http_status_code=status_code,
                )
            else:
                raise DeepLException(
                    f"Service unavailable{message}",
                    should_retry=True,
                    http_status_code=status_code,
                )
        else:
            status_name = (
                http.client.responses[status_code]
                if status_code in http.client.responses
                else "Unknown"
            )

            # TODO Handle streams below
            content_str = response.text
            # if isinstance(response.content, str) else response.content.text

            raise DeepLException(
                f"Unexpected status code: {status_code} {status_name}, "
                f"content: {content_str}.",
                should_retry=False,
                http_status_code=status_code,
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
        formality: Union[str, Formality, None],
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
        if formality is not None:
            request_data["formality"] = str(formality).lower()
        if isinstance(glossary, GlossaryInfo):
            request_data["glossary_id"] = glossary.glossary_id
        elif glossary is not None:
            request_data["glossary_id"] = glossary
        return request_data

    def _set_user_agent(
        self, app_info_name: Optional[str], app_info_version: Optional[str]
    ):
        self.headers["User-Agent"] = _generate_user_agent(
            http_client.user_agent,
            self._send_platform_info,
            app_info_name,
            app_info_version,
        )

    @abstractmethod
    def translate_text(
        self,
        text: Union[str, Iterable[str]],
        *,
        source_lang: Union[str, Language, None] = None,
        target_lang: Union[str, Language],
        context: Optional[str] = None,
        split_sentences: Union[str, SplitSentences, None] = None,
        preserve_formatting: Optional[bool] = None,
        formality: Union[str, Formality, None] = None,
        glossary: Union[str, GlossaryInfo, None] = None,
        tag_handling: Optional[str] = None,
        outline_detection: Optional[bool] = None,
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
        :param context: (Optional) Additional contextual text to influence
            translations, that is not translated itself. Characters in the
            `context` parameter are not counted toward billing. See the API
            documentation for more information and example usage.
        :param split_sentences: (Optional) Controls how the translation engine
            should split input into sentences before translation, see
            :class:`SplitSentences`.
        :param preserve_formatting: (Optional) Set to True to prevent the
            translation engine from correcting some formatting aspects, and
            instead leave the formatting unchanged.
        :param formality: (Optional) Desired formality for translation, as
            Formality enum, "less", "more", "prefer_less", "prefer_more", or
            "default".
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

    @abstractmethod
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

    @abstractmethod
    def translate_document_upload(
        self,
        input_document: Union[TextIO, BinaryIO, str, bytes, Any],
        *,
        source_lang: Optional[str] = None,
        target_lang: str,
        formality: Union[str, Formality, None] = None,
        glossary: Union[str, GlossaryInfo, None] = None,
        filename: Optional[str] = None,
        output_format: Optional[str] = None,
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
            Formality enum, "less", "more", "prefer_less", or "prefer_more".
        :param glossary: (Optional) glossary or glossary ID to use for
            translation. Must match specified source_lang and target_lang.
        :param filename: (Optional) Filename including extension, only required
            if uploading string or bytes containing file content.
        :param output_format: (Optional) Desired output file extension, if
            it differs from the input file format.
        :return: DocumentHandle with ID and key identifying document.
        """

    @abstractmethod
    def translate_document_get_status(
        self, handle: DocumentHandle
    ) -> DocumentStatus:
        """Gets the status of the document translation request associated with
         given handle.

        :param handle: DocumentHandle to the request to check.
        :return: DocumentStatus containing the request status.

        :raises DocumentTranslationException: If an error occurs during
            querying the document, the exception includes the document handle.
        """

    @abstractmethod
    def translate_document_download(
        self,
        handle: DocumentHandle,
        output_file: Union[TextIO, BinaryIO, Any, None] = None,
        chunk_size: int = 1,
    ) -> Optional[Any]:
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
            raw response object will be returned.
        """

    @abstractmethod
    def get_source_languages(self, skip_cache=False) -> List[Language]:
        """Request the list of available source languages.

        :param skip_cache: Deprecated, and now has no effect as the
            corresponding internal functionality has been removed. This
            parameter will be removed in a future version.
        :return: List of supported source languages.
        """

    @abstractmethod
    def get_target_languages(self, skip_cache=False) -> List[Language]:
        """Request the list of available target languages.

        :param skip_cache: Deprecated, and now has no effect as the
            corresponding internal functionality has been removed. This
            parameter will be removed in a future version.
        :return: List of supported target languages.
        """

    @abstractmethod
    def get_glossary_languages(self) -> List[GlossaryLanguagePair]:
        """Request the list of language pairs supported for glossaries."""

    @abstractmethod
    def get_usage(self) -> Usage:
        """Requests the current API usage."""

    @abstractmethod
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

    @abstractmethod
    def get_glossary(self, glossary_id: str) -> GlossaryInfo:
        """Retrieves GlossaryInfo for the glossary with specified ID.

        :param glossary_id: ID of glossary to retrieve.
        :return: GlossaryInfo with information about specified glossary.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        """

    @abstractmethod
    def list_glossaries(self) -> List[GlossaryInfo]:
        """Retrieves GlossaryInfo for all available glossaries.

        :return: list of GlossaryInfo for all available glossaries.
        """

    @abstractmethod
    def get_glossary_entries(self, glossary: Union[str, GlossaryInfo]) -> dict:
        """Retrieves the entries of the specified glossary and returns them as
        a dictionary.

        :param glossary: GlossaryInfo or ID of glossary to retrieve.
        :return: dictionary of glossary entries.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        :raises DeepLException: If the glossary could not be retrieved
            in the right format.
        """

    @abstractmethod
    def delete_glossary(self, glossary: Union[str, GlossaryInfo]) -> None:
        """Deletes specified glossary.

        :param glossary: GlossaryInfo or ID of glossary to delete.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        """

    def set_app_info(self, app_info_name: str, app_info_version: str):
        self._set_user_agent(app_info_name, app_info_version)
        return self

    def _translate_text_pre(
        self,
        text: Union[str, Iterable[str]],
        *,
        source_lang: Union[str, Language, None] = None,
        target_lang: Union[str, Language],
        context: Optional[str] = None,
        split_sentences: Union[str, SplitSentences, None] = None,
        preserve_formatting: Optional[bool] = None,
        formality: Union[str, Formality, None] = None,
        glossary: Union[str, GlossaryInfo, None] = None,
        tag_handling: Optional[str] = None,
        outline_detection: Optional[bool] = None,
        non_splitting_tags: Union[str, List[str], None] = None,
        splitting_tags: Union[str, List[str], None] = None,
        ignore_tags: Union[str, List[str], None] = None,
    ) -> tuple[HttpRequest, BaseContext]:

        if isinstance(text, str):
            if len(text) == 0:
                raise ValueError("text must not be empty")
            text = [text]
            multi_input = False
        elif hasattr(text, "__iter__"):
            multi_input = True
            text = list(text)
        else:
            raise TypeError(
                "text parameter must be a string or an iterable of strings"
            )

        request = self._prepare_http_request("v2/translate")

        request.json = self._check_language_and_formality(
            source_lang,
            target_lang,
            formality,
            glossary,
        )
        request.json["text"] = text

        if context is not None:
            request.json["context"] = context
        if split_sentences is not None:
            request.json["split_sentences"] = str(split_sentences)
        if preserve_formatting is not None:
            request.json["preserve_formatting"] = bool(preserve_formatting)
        if tag_handling is not None:
            request.json["tag_handling"] = tag_handling
        if outline_detection is not None:
            request.json["outline_detection"] = bool(outline_detection)

        def join_tags(tag_argument: Union[str, Iterable[str]]) -> List[str]:
            if isinstance(tag_argument, str):
                tag_argument = [tag_argument]
            return [
                tag
                for arg_string in tag_argument
                for tag in arg_string.split(",")
            ]

        if non_splitting_tags is not None:
            request.json["non_splitting_tags"] = join_tags(non_splitting_tags)
        if splitting_tags is not None:
            request.json["splitting_tags"] = join_tags(splitting_tags)
        if ignore_tags is not None:
            request.json["ignore_tags"] = join_tags(ignore_tags)

        context = BaseContext()
        context.multi_input = multi_input

        return request, context

    def _translate_text_post(
        self, response: HttpResponse, context: BaseContext
    ) -> Union[TextResult, List[TextResult]]:
        self._raise_for_status(response)

        translations = response.json.get("translations", [])
        output = []
        for translation in translations:
            text = translation.get("text")
            lang = translation.get("detected_source_language")
            output.append(TextResult(text, detected_source_lang=lang))

        multi_input = context.multi_input

        return output if multi_input else output[0]

    def _translate_text_with_glossary_pre(
        self,
        text: Union[str, Iterable[str]],
        glossary: GlossaryInfo,
        target_lang: Union[str, Language, None] = None,
        **kwargs,
    ) -> tuple[HttpRequest, BaseContext]:
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

        return self._translate_text_pre(
            text,
            source_lang=glossary.source_lang,
            target_lang=target_lang,
            glossary=glossary,
            **kwargs,
        )

    def _translate_text_with_glossary_post(
        self, response: HttpResponse, context: BaseContext
    ) -> Union[TextResult, List[TextResult]]:
        return self._translate_text_post(response, context)

    def _translate_document_upload_pre(
        self,
        input_document: Union[TextIO, BinaryIO, str, bytes, Any],
        *,
        source_lang: Optional[str] = None,
        target_lang: str,
        formality: Union[str, Formality, None] = None,
        glossary: Union[str, GlossaryInfo, None] = None,
        filename: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> tuple[HttpRequest, BaseContext]:
        request = self._prepare_http_request("v2/document")
        request.data = self._check_language_and_formality(
            source_lang, target_lang, formality, glossary
        )
        if output_format:
            request.data["output_format"] = output_format

        if isinstance(input_document, (str, bytes)):
            if filename is None:
                raise ValueError(
                    "filename is required if uploading file content as string "
                    "or bytes"
                )
            request.files = {"file": (filename, input_document)}
        else:
            request.files = {"file": input_document}
        return request, BaseContext()

    def _translate_document_upload_post(
        self, response: HttpResponse, context: BaseContext
    ) -> DocumentHandle:
        self._raise_for_status(response)
        json = response.json

        if not json:
            json = {}
        return DocumentHandle(
            json.get("document_id", ""), json.get("document_key", "")
        )

    def _translate_document_get_status_pre(
        self, handle: DocumentHandle
    ) -> tuple[HttpRequest, BaseContext]:
        request = self._prepare_http_request(
            f"v2/document/{handle.document_id}",
            json={"document_key": handle.document_key},
        )
        context = BaseContext()
        context.handle = handle
        return request, context

    def _translate_document_get_status_post(
        self, response: HttpResponse, context: BaseContext
    ) -> DocumentStatus:
        self._raise_for_status(response)
        json = response.json
        handle = context.handle

        status = (
            json.get("status", None)
            if (json and isinstance(json, dict))
            else None
        )
        if not status:
            raise DocumentTranslationException(
                "Querying document status gave an empty response", handle
            )
        seconds_remaining = (
            json.get("seconds_remaining", None)
            if (json and isinstance(json, dict))
            else None
        )
        billed_characters = (
            json.get("billed_characters", None)
            if (json and isinstance(json, dict))
            else None
        )
        error_message = (
            json.get("error_message", None)
            if (json and isinstance(json, dict))
            else None
        )
        return DocumentStatus(
            status, seconds_remaining, billed_characters, error_message
        )

    def _translate_document_download_pre(
        self,
        handle: DocumentHandle,
        output_file: Union[TextIO, BinaryIO, Any, None] = None,
        chunk_size: int = 1,
    ) -> tuple[HttpRequest, BaseContext]:
        request = self._prepare_http_request(
            f"v2/document/{handle.document_id}/result",
            json={"document_key": handle.document_key},
            stream=output_file is None,
            stream_chunks=output_file.write if output_file else None,
        )
        context = BaseContext()
        context.output_file = output_file
        return request, context

    def _translate_document_download_post(
        self, response: HttpResponse, context: BaseContext
    ) -> Optional[Any]:
        output_file = context.output_file
        self._raise_for_status(response, downloading_document=True)

        if output_file:
            return None
        else:
            return response.raw_response()

    def _get_source_languages_pre(self) -> tuple[HttpRequest, BaseContext]:
        return (
            self._prepare_http_request("v2/languages", method="GET"),
            BaseContext(),
        )

    def _get_source_languages_post(
        self, response: HttpResponse, context: BaseContext
    ) -> List[Language]:
        self._raise_for_status(response)
        json = response.json
        languages = json if (json and isinstance(json, list)) else []
        return [
            Language(
                language["language"],
                language["name"],
            )
            for language in languages
        ]

    def _get_target_languages_pre(self) -> tuple[HttpRequest, BaseContext]:
        return (
            self._prepare_http_request(
                "v2/languages", method="GET", data={"type": "target"}
            ),
            BaseContext(),
        )

    def _get_target_languages_post(
        self, response: HttpResponse, context: BaseContext
    ) -> List[Language]:
        self._raise_for_status(response)
        json = response.json
        languages = json if (json and isinstance(json, list)) else []
        return [
            Language(
                language["language"],
                language["name"],
                language.get("supports_formality", None),
            )
            for language in languages
        ]

    def _get_glossary_languages_pre(self) -> tuple[HttpRequest, BaseContext]:
        return (
            self._prepare_http_request(
                "v2/glossary-language-pairs", method="GET"
            ),
            BaseContext(),
        )

    def _get_glossary_languages_post(
        self, response: HttpResponse, context: BaseContext
    ) -> List[GlossaryLanguagePair]:
        self._raise_for_status(response)
        json = response.json

        supported_languages = (
            json.get("supported_languages", [])
            if (json and isinstance(json, dict))
            else []
        )
        return [
            GlossaryLanguagePair(
                language_pair["source_lang"], language_pair["target_lang"]
            )
            for language_pair in supported_languages
        ]

    def _get_usage_pre(self) -> tuple[HttpRequest, BaseContext]:
        return (
            self._prepare_http_request("v2/usage", method="GET"),
            BaseContext(),
        )

    def _get_usage_post(
        self, response: HttpResponse, context: BaseContext
    ) -> Usage:
        self._raise_for_status(response)

        json = response.json
        if not isinstance(json, dict):
            json = {}
        return Usage(json)

    def _create_glossary_pre(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        entries: Dict[str, str],
    ) -> tuple[HttpRequest, BaseContext]:
        if not entries:
            raise ValueError("glossary entries must not be empty")

        return self._create_glossary_pre_common(
            name,
            source_lang,
            target_lang,
            "tsv",
            util.convert_dict_to_tsv(entries),
        )

    def _create_glossary_post(
        self, response: HttpResponse, context: BaseContext
    ) -> GlossaryInfo:
        self._raise_for_status(response)
        return GlossaryInfo.from_json(response.json)

    def _create_glossary_from_csv_pre(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        csv_data: Union[TextIO, BinaryIO, str, bytes, Any],
    ) -> tuple[HttpRequest, BaseContext]:
        entries = (
            csv_data if isinstance(csv_data, (str, bytes)) else csv_data.read()
        )

        if not isinstance(entries, (bytes, str)):
            raise ValueError("Entries of the glossary are invalid")

        return self._create_glossary_pre_common(
            name, source_lang, target_lang, "csv", entries
        )

    def _create_glossary_pre_common(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        entries_format: str,
        entries: Union[str, bytes],
    ) -> tuple[HttpRequest, BaseContext]:
        # glossaries are only supported for base language types
        source_lang = Language.remove_regional_variant(source_lang)
        target_lang = Language.remove_regional_variant(target_lang)

        if not name:
            raise ValueError("glossary name must not be empty")

        request_data = {
            "name": name,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "entries_format": entries_format,
            "entries": entries,
        }
        return (
            self._prepare_http_request("v2/glossaries", json=request_data),
            BaseContext(),
        )

    def _create_glossary_from_csv_post(
        self, response: HttpResponse, context: BaseContext
    ) -> GlossaryInfo:
        return self._create_glossary_post(response, context)

    def _get_glossary_pre(
        self, glossary_id: str
    ) -> tuple[HttpRequest, BaseContext]:
        return (
            self._prepare_http_request(
                f"v2/glossaries/{glossary_id}", method="GET"
            ),
            BaseContext(),
        )

    def _get_glossary_post(
        self, response: HttpResponse, context: BaseContext
    ) -> GlossaryInfo:
        self._raise_for_status(response, glossary_management=True)
        return GlossaryInfo.from_json(response.json)

    def _list_glossaries_pre(self) -> tuple[HttpRequest, BaseContext]:
        return (
            self._prepare_http_request("v2/glossaries", method="GET"),
            BaseContext(),
        )

    def _list_glossaries_post(
        self, response: HttpResponse, context: BaseContext
    ) -> List[GlossaryInfo]:
        self._raise_for_status(response, glossary_management=True)
        json = response.json
        glossaries = (
            json.get("glossaries", [])
            if (json and isinstance(json, dict))
            else []
        )
        return [GlossaryInfo.from_json(glossary) for glossary in glossaries]

    def _get_glossary_entries_pre(
        self, glossary: Union[str, GlossaryInfo]
    ) -> tuple[HttpRequest, BaseContext]:
        if isinstance(glossary, GlossaryInfo):
            glossary_id = glossary.glossary_id
        else:
            glossary_id = glossary

        return (
            self._prepare_http_request(
                f"v2/glossaries/{glossary_id}/entries",
                method="GET",
                headers={"Accept": "text/tab-separated-values"},
            ),
            BaseContext(),
        )

    def _get_glossary_entries_post(
        self, response: HttpResponse, context: BaseContext
    ) -> dict:
        self._raise_for_status(response, glossary_management=True)
        if not isinstance(response.text, str):
            raise DeepLException(
                "Could not get the glossary content as a string",
                http_status_code=response.status_code,
            )
        return util.convert_tsv_to_dict(response.text)

    def _delete_glossary_pre(
        self, glossary: Union[str, GlossaryInfo]
    ) -> tuple[HttpRequest, BaseContext]:
        if isinstance(glossary, GlossaryInfo):
            glossary_id = glossary.glossary_id
        else:
            glossary_id = glossary

        return (
            self._prepare_http_request(
                f"v2/glossaries/{glossary_id}", method="DELETE"
            ),
            BaseContext(),
        )

    def _delete_glossary_post(
        self, response: HttpResponse, context: BaseContext
    ) -> None:
        self._raise_for_status(response, glossary_management=True)

    @property
    def server_url(self):
        return self._server_url


@lru_cache(maxsize=4)
def _generate_user_agent(
    user_agent_str: Optional[str],
    send_platform_info: bool,
    app_info_name: Optional[str],
    app_info_version: Optional[str],
):
    if user_agent_str:
        library_info_str = user_agent_str
    else:
        library_info_str = f"deepl-python/{version.VERSION}"
        if send_platform_info:
            try:
                library_info_str += (
                    f" ({platform.platform()}) "
                    f"python/{platform.python_version()} "
                    f"requests/{requests.__version__}"
                )
            except Exception:
                util.log_info(
                    "Exception when querying platform information:\n"
                    + traceback.format_exc()
                )
    if app_info_name and app_info_version:
        library_info_str += f" {app_info_name}/{app_info_version}"
    return library_info_str
