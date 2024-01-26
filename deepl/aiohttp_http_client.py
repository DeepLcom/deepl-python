# Copyright 2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import aiohttp
from typing import Union, Dict

from .translator_base import HttpResponse
from .iasync_http_client import IAsyncHttpClient
from .ihttp_client import IPreparedRequest
from .translator_base import HttpRequest


class AioHttpHttpClient(IAsyncHttpClient):
    def __init__(
        self,
        proxy: Union[Dict, str, None] = None,
        verify_ssl: Union[bool, str, None] = None,
    ):
        self._session = aiohttp.ClientSession()
        # TODO proxy, verify_ssl

        super().__init__()

    async def close(self):
        await self._session.close()

    def prepare_request(self, request: HttpRequest) -> IPreparedRequest:
        return IPreparedRequest(request)

    async def send_async_request(
        self, prepared_request: IPreparedRequest, timeout: float
    ) -> HttpResponse:
        request = prepared_request.request

        async with self._session.request(
            request.method,
            request.url,
            headers=request.headers,
            data=request.data,
            json=request.json,
            # stream=request.stream, TODO
        ) as response:
            content = await response.text()
            return HttpResponse(
                response.status, content, dict(response.headers)
            )
