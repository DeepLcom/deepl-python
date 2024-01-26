# Copyright 2022-2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
from abc import abstractmethod
from functools import lru_cache

from . import version
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
from .exceptions import (
    DocumentNotReadyException,
    GlossaryNotFoundException,
    QuotaExceededException,
    TooManyRequestsException,
    DeepLException,
    AuthorizationException,
    DocumentTranslationException,
)
import http
import http.client
import json as json_module
import os
import pathlib
import platform
import traceback
import requests  # type: ignore
import time
from typing import (
    Any,
    BinaryIO,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    TextIO,
    Tuple,
    Union,
    Type,
)
import urllib.parse


class HttpRequest:
    def __init__(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        data: Optional[dict], # TODO Maybe data is unnecessary
        json: Optional[dict],
    ):
        # TODO files, stream
        self.method = method
        self.url = url
        self.headers = headers
        self.data = data
        self.json = json


class HttpResponse:
    def __init__(
        self, status_code: int, content: Optional[str], headers: Dict[str, str]
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers  # TODO headers needs to be a case insensitive dict

        content_type = "Content-Type"
        if content_type in self.headers and self.headers[
            content_type
        ].startswith(
            "application/json"
        ):  # TODO improve json-compatible check
            self.json = json_module.loads(self.content)
        else:
            self.json = None

        # TODO Handle streams


class BaseContext:
    """
    Used by TranslatorBase to include extra context among pre, status-check, and post functions.
    """

    def __init__(        self,    ):
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
    ) -> HttpRequest:
        if data is not None and json is not None:
            raise ValueError("cannot accept both json and data")

        url = urllib.parse.urljoin(self._server_url, url)
        if data is None:
            data = {}

        if headers is None:
            headers = {}
        headers.update(
            {k: v for k, v in self.headers.items() if k not in headers}
        )
        return HttpRequest(method, url, headers, data, json)

    def _raise_for_status(
        self,
        response: HttpResponse,
        glossary_management: bool = False,
        downloading_document: bool = False,
        # status_code: int,
        # content: Union[str, requests.Response],
        # json: Any,
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
            content_str = (
                response.content
            )  # if isinstance(response.content, str) else response.content.text
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
    ):
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
            translations, that is not translated itself. Note: this is an alpha
            feature: it may be deprecated at any time, or incur charges if it
            becomes generally available. See the API documentation for more
            information and example usage.
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

    # TODO translate_document_upload
    # TODO _translate_document_upload_pre
    # TODO _translate_document_upload_post
    # TODO translate_document_get_status
    # TODO _translate_document_get_status_pre
    # TODO _translate_document_get_status_post
    # TODO translate_document_download
    # TODO _translate_document_download_pre
    # TODO _translate_document_download_post

    @abstractmethod
    def get_source_languages(self, skip_cache=False) -> List[Language]:
        """Request the list of available source languages.

        :param skip_cache: Deprecated, and now has no effect as the
            corresponding internal functionality has been removed. This
            parameter will be removed in a future version.
        :return: List of supported source languages.
        """

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

    @abstractmethod
    def get_target_languages(self, skip_cache=False) -> List[Language]:
        """Request the list of available target languages.

        :param skip_cache: Deprecated, and now has no effect as the
            corresponding internal functionality has been removed. This
            parameter will be removed in a future version.
        :return: List of supported target languages.
        """

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

    @abstractmethod
    def get_glossary_languages(self) -> List[GlossaryLanguagePair]:
        """Request the list of language pairs supported for glossaries."""

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

    @abstractmethod
    def get_usage(self) -> Usage:
        """Requests the current API usage."""

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

    def _create_glossary_pre(
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

    def _create_glossary_post(
        self, response: HttpResponse, context: BaseContext
    ) -> GlossaryInfo:
        self._raise_for_status(response)
        return GlossaryInfo.from_json(response.json)

    # TODO create_glossary

    @abstractmethod
    def get_glossary(self, glossary_id: str) -> GlossaryInfo:
        """Retrieves GlossaryInfo for the glossary with specified ID.

        :param glossary_id: ID of glossary to retrieve.
        :return: GlossaryInfo with information about specified glossary.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        """

    def _get_glossary_pre(self, glossary_id: str) -> tuple[HttpRequest, BaseContext]:
        return (
                self._prepare_http_request(f"v2/glossaries/{glossary_id}", method="GET"),
                BaseContext(),
            )
    def _get_glossary_post(self, response: HttpResponse, context: BaseContext) -> GlossaryInfo:
        self._raise_for_status(response, glossary_management=True)
        return GlossaryInfo.from_json(response.json)


    @abstractmethod
    def list_glossaries(self) -> List[GlossaryInfo]:
        """Retrieves GlossaryInfo for all available glossaries.

        :return: list of GlossaryInfo for all available glossaries.
        """

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

    # TODO get_glossary_entries
    # TODO delete_glossary


        # def _get_usage_pre(self) -> tuple[HttpRequest, BaseContext]:
        #     return (
        #         self._prepare_http_request("v2/usage", method="GET"),
        #         BaseContext(),
        #     )
        #
        # def _get_usage_post(
        #         self, response: HttpResponse, context: BaseContext
        # ) -> Usage:
        #     self._raise_for_status(response, context)
        #
        #     json = response.json
        #     if not isinstance(json, dict):
        #         json = {}
        #     return Usage(json)

    def set_app_info(self, app_info_name: str, app_info_version: str):
        self._set_user_agent(app_info_name, app_info_version)

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
