# Copyright 2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from typing import Union, Dict, Iterator

from .translator_base import HttpResponse
from .iasync_http_client import IAsyncHttpClient
from .ihttp_client import IPreparedRequest
from .translator_base import HttpRequest

try:
    import aiohttp
except ImportError as import_error:
    aiohttp = None
    aiohttp_import_error = import_error


class AioHttpResponse(HttpResponse):
    def iter_content(self, chunk_size) -> Iterator:
        return self.raw_response.iter_content(chunk_size)

    def __init__(self, response: "aiohttp.ClientResponse", stream: bool):
        if stream:
            super().__init__(response.status, None, response.headers, response)
        else:
            try:
                response.encoding = "UTF-8"
                super().__init__(
                    response.status_code, response.text, response.headers, None
                )
            finally:
                response.close()


class AioHttpHttpClient(IAsyncHttpClient):
    def __init__(
        self,
        proxy: Union[Dict, str, None] = None,
        verify_ssl: Union[bool, str, None] = None,
    ):
        if aiohttp is None:
            raise ImportError(
                "aiohttp import failed, cannot use aiohttp client"
            ) from aiohttp_import_error

        self._session = aiohttp.ClientSession()
        # TODO proxy, verify_ssl

        super().__init__()

    async def close(self):
        await self._session.close()

    def prepare_request(self, request: HttpRequest) -> IPreparedRequest:
        return IPreparedRequest(request)

    async def send_request_async(
        self, prepared_request: IPreparedRequest, timeout: float
    ) -> HttpResponse:
        request = prepared_request.request

        async with self._session.request(
            request.method,
            request.url,
            headers=request.headers,
            data=request.data,
            json=request.json,
        ) as response:
            if prepared_request.request.stream:
                raise NotImplementedError()
            else:
                content = await response.text()
                return HttpResponse(
                    response.status, content, dict(response.headers), None
                )
