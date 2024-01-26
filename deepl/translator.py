# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

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
from .requests_http_client import RequestsHttpClient
from . import http_client, util, translator_base
from .exceptions import (
    DocumentNotReadyException,
    GlossaryNotFoundException,
    QuotaExceededException,
    TooManyRequestsException,
    DeepLException,
    AuthorizationException,
    DocumentTranslationException,
)
from .translator_base import TranslatorBase, HttpRequest, HttpResponse

import json as json_module
import os
import pathlib
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
)


def with_base_pre_and_post(func):
    pre_func = getattr(TranslatorBase, f"_{func.__name__}_pre")
    post_func = getattr(TranslatorBase, f"_{func.__name__}_post")

    def wrapped(self, *args, **kwargs):
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
        skip_language_check: bool = False,
    ):
        super().__init__(
            auth_key,
            server_url=server_url,
            send_platform_info=send_platform_info,
        )
        self._client = RequestsHttpClient(proxy, verify_ssl)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    # def _api_call(
    #     self,
    #     url: str,
    #     *,
    #     method: str = "POST",
    #     data: Optional[dict] = None,
    #     json: Optional[dict] = None,
    #     stream: bool = False,
    #     headers: Optional[dict] = None,
    #     **kwargs,
    # ) -> Tuple[int, Union[str, requests.Response], Any]:
    #     """
    #     Makes a request to the API, and returns response as status code,
    #     content and JSON object.
    #     """
    #
    #     util.log_info("Request to DeepL API", method=method, url=url)
    #     util.log_debug("Request details", data=data, json=json)
    #
    #     status_code, content = self._client.request_with_backoff(
    #         request,
    #         method,
    #         url,
    #         data=data,
    #         json=json,
    #         stream=stream,
    #         headers=headers,
    #         **kwargs,
    #     )
    #
    #     json = None
    #     if isinstance(content, str):
    #         content_str = content
    #         try:
    #             json = json_module.loads(content)
    #         except json_module.JSONDecodeError:
    #             pass
    #     else:
    #         content_str = content.text
    #
    #     util.log_info("DeepL API response", url=url, status_code=status_code)
    #     util.log_debug("Response details", content=content_str)
    #
    #     return post(status_code, content, json)

    def _create_glossary_internal(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        entries_format: str,
        entries: Union[str, bytes],
    ) -> GlossaryInfo:
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

        status, content, json = self._api_call(
            "v2/glossaries", json=request_data
        )
        self._raise_for_status(status, json, glossary=True)
        return GlossaryInfo.from_json(json)

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

        request_data = self._check_language_and_formality(
            source_lang, target_lang, formality, glossary
        )
        if output_format:
            request_data["output_format"] = output_format

        files: Dict[str, Any] = {}
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
        self._raise_for_status(status, json)

        if not json:
            json = {}
        return DocumentHandle(
            json.get("document_id", ""), json.get("document_key", "")
        )

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

        data = {"document_key": handle.document_key}
        url = f"v2/document/{handle.document_id}"

        status_code, content, json = self._api_call(url, json=data)

        self._raise_for_status(status_code, json)

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
            url, json=data, stream=True
        )
        # TODO: once we drop py3.6 support, replace this with @overload
        # annotations in `_api_call` and chained private functions.
        # See for example https://stackoverflow.com/a/74070166/4926599
        # In addition, drop the type: ignore annotation on the
        # `import requests` / `from requests`
        assert isinstance(response, requests.Response)

        self._raise_for_status(
            status_code, json, downloading_document=True
        )

        if output_file:
            chunks = response.iter_content(chunk_size=chunk_size)
            for chunk in chunks:
                output_file.write(chunk)
            return None
        else:
            return response

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
    def get_usage(self) -> Usage:
        raise NotImplementedError("replaced by decorator")

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
        if not entries:
            raise ValueError("glossary entries must not be empty")

        return self._create_glossary_internal(
            name,
            source_lang,
            target_lang,
            "tsv",
            util.convert_dict_to_tsv(entries),
        )

    def create_glossary_from_csv(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        csv_data: Union[TextIO, BinaryIO, str, bytes, Any],
    ) -> GlossaryInfo:
        """Creates a glossary with given name for the source and target
        languages, containing the entries in the given CSV data.
        The glossary may be used in the translate_text functions.

        Only certain language pairs are supported. The available language pairs
        can be queried using get_glossary_languages(). Glossaries are not
        regional specific: a glossary with target language EN may be used to
        translate texts into both EN-US and EN-GB.

        This function allows you to upload a glossary CSV file that you have
        downloaded from the DeepL website.

        Information about the expected CSV format can be found in the API
        documentation: https://www.deepl.com/docs-api/managing-glossaries/supported-glossary-formats/  # noqa

        :param name: user-defined name to attach to glossary.
        :param source_lang: Language of source terms.
        :param target_lang: Language of target terms.
        :param csv_data: CSV data containing glossary entries, either as a
            file-like object or string or bytes containing file content.
        :return: GlossaryInfo containing information about created glossary.

        :raises ValueError: If the glossary name is empty, or entries are
            empty or invalid.
        :raises DeepLException: If source and target language pair are not
            supported for glossaries.
        """

        entries = (
            csv_data if isinstance(csv_data, (str, bytes)) else csv_data.read()
        )

        if not isinstance(entries, (bytes, str)):
            raise ValueError("Entries of the glossary are invalid")
        return self._create_glossary_internal(
            name, source_lang, target_lang, "csv", entries
        )

    @with_base_pre_and_post
    def get_glossary(self, glossary_id: str) -> GlossaryInfo:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    def list_glossaries(self) -> List[GlossaryInfo]:
        raise NotImplementedError("replaced by decorator")

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
        if isinstance(glossary, GlossaryInfo):
            glossary_id = glossary.glossary_id
        else:
            glossary_id = glossary

        status, content, json = self._api_call(
            f"v2/glossaries/{glossary_id}/entries",
            method="GET",
            headers={"Accept": "text/tab-separated-values"},
        )
        self._raise_for_status(status, json, glossary=True)
        if not isinstance(content, str):
            raise DeepLException(
                "Could not get the glossary content as a string",
                http_status_code=status,
            )
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
        self._raise_for_status(status, json, glossary=True)
