# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

import os
import pathlib
import time
from typing import (
    Any,
    BinaryIO,
    Dict,
    Iterable,
    List,
    Optional,
    TextIO,
    Union,
)

import requests  # type: ignore

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
from .ihttp_client import IHttpClient
from . import util
from .exceptions import (
    DocumentTranslationException,
)
from .requests_http_client import RequestsHttpClient
from .translator_base import TranslatorBase


def with_base_pre_and_post(func):
    pre_func = getattr(TranslatorBase, f"_{func.__name__}_pre")
    post_func = getattr(TranslatorBase, f"_{func.__name__}_post")

    def wrapped(self: "Translator", *args, **kwargs):
        request, base_context = pre_func(self, *args, **kwargs)
        response = self._client.request_with_backoff(request)
        return post_func(self, response, base_context)

    return wrapped


class Translator(TranslatorBase):
    """Wrapper for the DeepL API for language translation.

    You must create an instance of Translator to use the DeepL API.

    :param auth_key: Authentication key as found in your DeepL API account.
    :param server_url: (Optional) Base URL of DeepL API, can be overridden e.g.
        for testing purposes.
    :param proxy: (Optional) Proxy server URL string or dictionary containing
        URL strings for the 'http' and 'https' keys. This is passed to the
        underlying requests session, see the requests proxy documentation for
        more information.
    :param send_platform_info: (Optional) boolean that indicates if the client
        library can send basic platform info (python version, OS, http library
        version) to the DeepL API. True = send info, False = only send client
        library version
    :param verify_ssl: (Optional) Controls how requests verifies SSL
        certificates. This is passed to the underlying requests session, see
        the requests verify documentation for more information.
    :param http_client: (Optional) Custom HTTP client implementation to use.
    :param skip_language_check: Deprecated, and now has no effect as the
        corresponding internal functionality has been removed. This parameter
        will be removed in a future version.

    All functions may raise DeepLException or a subclass if a connection error
    occurs.
    """

    def __init__(
        self,
        auth_key: str,
        *,
        server_url: Optional[str] = None,
        proxy: Union[Dict, str, None] = None,
        send_platform_info: bool = True,
        verify_ssl: Union[bool, str, None] = None,
        http_client: Optional[IHttpClient] = None,
        skip_language_check: bool = False,
    ):
        super().__init__(
            auth_key,
            server_url=server_url,
            send_platform_info=send_platform_info,
        )

        if http_client:
            self._client = http_client  # TODO proxy, verify_ssl?
        else:
            self._client = RequestsHttpClient(proxy, verify_ssl)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        if hasattr(self, "_client"):
            self._client.close()

    @with_base_pre_and_post
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
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def translate_text_with_glossary(
        self,
        text: Union[str, Iterable[str]],
        glossary: GlossaryInfo,
        target_lang: Union[str, Language, None] = None,
        **kwargs,
    ) -> Union[TextResult, List[TextResult]]:
        raise NotImplementedError("replaced by decorator")

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
            Formality enum, "less", "more", "prefer_less", or "prefer_more".
        :param glossary: (Optional) glossary or glossary ID to use for
            translation. Must match specified source_lang and target_lang.
        :return: DocumentStatus when document translation completed, this
            allows the number of billed characters to be queried.

        :raises DocumentTranslationException: If an error occurs during
            translation. The exception includes information about the document
            request.
        """
        # Determine output_format from output path
        in_ext = pathlib.PurePath(input_path).suffix.lower()
        out_ext = pathlib.PurePath(output_path).suffix.lower()
        output_format = None if in_ext == out_ext else out_ext[1:]

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
                        output_format=output_format,
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
        filename: Optional[str] = None,
        output_format: Optional[str] = None,
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
            Formality enum, "less", "more", "prefer_less", or "prefer_more".
        :param glossary: (Optional) glossary or glossary ID to use for
            translation. Must match specified source_lang and target_lang.
        :param filename: (Optional) Filename including extension, only required
            if uploading string or bytes containing file content.
        :param output_format: (Optional) Desired output file extension, if
            it differs from the input file format.
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
            filename=filename,
            output_format=output_format,
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

    @with_base_pre_and_post
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
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def translate_document_get_status(
        self, handle: DocumentHandle
    ) -> DocumentStatus:
        raise NotImplementedError("replaced by decorator")

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
            secs = 5.0  # seconds_remaining is currently unreliable, so just
            # poll equidistantly
            util.log_info(
                f"Rechecking document translation status "
                f"after sleeping for {secs:.3f} seconds."
            )
            time.sleep(secs)
            status = self.translate_document_get_status(handle)
        return status

    @with_base_pre_and_post
    def translate_document_download(
        self,
        handle: DocumentHandle,
        output_file: Union[TextIO, BinaryIO, Any, None] = None,
        chunk_size: int = 1,
    ) -> Optional[Any]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def get_usage(self) -> Usage:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def get_source_languages(self, skip_cache=False) -> List[Language]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def get_target_languages(self, skip_cache=False) -> List[Language]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def get_glossary_languages(self) -> List[GlossaryLanguagePair]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def create_glossary(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        entries: Dict[str, str],
    ) -> GlossaryInfo:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def create_glossary_from_csv(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        csv_data: Union[TextIO, BinaryIO, str, bytes, Any],
    ) -> GlossaryInfo:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def get_glossary(self, glossary_id: str) -> GlossaryInfo:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def list_glossaries(self) -> List[GlossaryInfo]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def get_glossary_entries(self, glossary: Union[str, GlossaryInfo]) -> dict:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def delete_glossary(self, glossary: Union[str, GlossaryInfo]) -> None:
        raise NotImplementedError("replaced by decorator")
