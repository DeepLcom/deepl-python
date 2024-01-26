# Copyright 2022-2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
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
        data: Optional[dict],
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
        self.headers = headers

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

    def __init__(
        self,
        glossary_management: bool = False,
        downloading_document: bool = False,
    ):
        self.glossary_management = glossary_management
        self.downloading_document = downloading_document


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
        context: BaseContext
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
            if context.glossary_management:
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
            if context.downloading_document:
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

        request.data = self._check_language_and_formality(
            source_lang,
            target_lang,
            formality,
            glossary,
        )
        request.data["text"] = text

        if context is not None:
            request.data["context"] = context
        if split_sentences is not None:
            request.data["split_sentences"] = str(split_sentences)
        if preserve_formatting is not None:
            request.data["preserve_formatting"] = bool(preserve_formatting)
        if tag_handling is not None:
            request.data["tag_handling"] = tag_handling
        if outline_detection is not None:
            request.data["outline_detection"] = bool(outline_detection)

        def join_tags(tag_argument: Union[str, Iterable[str]]) -> List[str]:
            if isinstance(tag_argument, str):
                tag_argument = [tag_argument]
            return [
                tag
                for arg_string in tag_argument
                for tag in arg_string.split(",")
            ]

        if non_splitting_tags is not None:
            request.data["non_splitting_tags"] = join_tags(non_splitting_tags)
        if splitting_tags is not None:
            request.data["splitting_tags"] = join_tags(splitting_tags)
        if ignore_tags is not None:
            request.data["ignore_tags"] = join_tags(ignore_tags)

        context = BaseContext()
        context.multi_input = multi_input

        return request, context

    def _translate_text_post(
        self, response: HttpResponse, context: BaseContext
    ) -> Union[TextResult, List[TextResult]]:
        self._raise_for_status(response, context)

        translations = response.json.get("translations", [])
        output = []
        for translation in translations:
            text = translation.get("text")
            lang = translation.get("detected_source_language")
            output.append(TextResult(text, detected_source_lang=lang))

        multi_input = context.multi_input

        return output if multi_input else output[0]

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
