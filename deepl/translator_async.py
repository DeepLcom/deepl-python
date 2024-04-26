# Copyright 2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
from .api_data import GlossaryLanguagePair, SplitSentences, Formality
from deepl import Usage, GlossaryInfo, Language, TextResult
from .aiohttp_http_client import AioHttpHttpClient
from .iasync_http_client import IAsyncHttpClient
from .translator_base import TranslatorBase
from typing import (
    Dict,
    Iterable,
    List,
    Optional,
    Union,
    TextIO,
    BinaryIO,
    Any,
)


def with_base_pre_and_post(func):
    pre_func = getattr(TranslatorBase, f"_{func.__name__}_pre")
    post_func = getattr(TranslatorBase, f"_{func.__name__}_post")

    async def wrapped(self: "TranslatorAsync", *args, **kwargs):
        request, base_context = pre_func(self, *args, **kwargs)
        response = await self._client.request_with_backoff_async(request)
        return post_func(self, response, base_context)

    return wrapped


class TranslatorAsync(TranslatorBase):
    """Async wrapper for the DeepL API for language translation.

    You must create an instance of Translator or TranslatorAsync to use the
    DeepL API.

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
    ):
        super().__init__(
            auth_key,
            server_url=server_url,
            send_platform_info=send_platform_info,
        )

        self._client: IAsyncHttpClient = AioHttpHttpClient(proxy, verify_ssl)

    async def __aenter__(self) -> "TranslatorAsync":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self):
        if hasattr(self, "_client"):
            await self._client.close()

    @with_base_pre_and_post
    async def translate_text(
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
    async def translate_text_with_glossary(
        self,
    ) -> Union[TextResult, List[TextResult]]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    async def get_usage(self) -> Usage:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    async def get_source_languages(self) -> List[Language]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    async def get_target_languages(self) -> List[Language]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    async def get_glossary_languages(self) -> List[GlossaryLanguagePair]:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    async def create_glossary(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        entries: Dict[str, str],
    ) -> GlossaryInfo:
        raise NotImplementedError("replaced by decorator")

    @with_base_pre_and_post
    async def create_glossary_from_csv(
        self,
        name: str,
        source_lang: Union[str, Language],
        target_lang: Union[str, Language],
        csv_data: Union[TextIO, BinaryIO, str, bytes, Any],
    ) -> GlossaryInfo:
        raise NotImplementedError("replaced by decorator")
