# Copyright 2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
from .aiohttp_http_client import AioHttpHttpClient
from .iasync_http_client import IAsyncHttpClient
from . import http_client, util
from .translator_base import TranslatorBase, HttpRequest, HttpResponse
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

    async def translate_text(self, *args, **kwargs):
        request, base_context = self._translate_text_pre(*args, **kwargs)
        response = await self._client.request_with_backoff(request)
        return self._translate_text_post(response, base_context)
