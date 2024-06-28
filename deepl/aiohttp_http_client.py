# Copyright 2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import asyncio
from typing import Union, Dict, Iterator, Optional

from multidict import CIMultiDictProxy

from deepl import ConnectionException
from .translator_base import HttpResponse
from .iasync_http_client import IAsyncHttpClient
from .ihttp_client import IPreparedRequest
from .translator_base import HttpRequest

try:
    import aiohttp
except ImportError as import_error:
    aiohttp = None
    aiohttp_import_error = import_error


class AioHttpPreparedRequest(IPreparedRequest):
    def __init__(self, request: HttpRequest):
        super().__init__(request)

        if request.files:
            self.data = aiohttp.MultipartWriter("form-data")
            for key, file in request.files.items():
                part = self.data.append(file)
                part.set_content_disposition(
                    "form-data", name=key, filename="test.txt"
                )
            if request.data:
                for key, value in request.data.items():
                    part = self.data.append(value)
                    part.set_content_disposition("form-data", name=key)
            self.json = None
        else:
            self.data = request.data
            self.json = request.json
        self.headers = request.headers

    async def prepare_data_buffer(self):
        class Writer:
            def __init__(self, _buffer):
                self.buffer = _buffer

            async def write(self, data):
                self.buffer.extend(data)

        if self.request.files:
            self.data: aiohttp.MultipartWriter
            buffer = bytearray()
            writer = Writer(buffer)
            await self.data.write(writer)
            self.headers.update(self.data.headers)
            self.data = buffer


class AioHttpResponse(HttpResponse):
    def iter_content(
        self, chunk_size
    ) -> "aiohttp.streams.AsyncStreamIterator[bytes]":
        return self._raw_response.content.iter_chunked(chunk_size)

    def raw_response(self) -> aiohttp.ClientResponse:
        return self._raw_response

    def __init__(
        self,
        status: int,
        text: Optional[str],
        headers: CIMultiDictProxy[str],
        raw_response: "aiohttp.ClientResponse",
    ):
        super().__init__(status, text, dict(headers))
        self._raw_response = raw_response


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

    async def prepare_request(self, request: HttpRequest) -> IPreparedRequest:
        prepared_request = AioHttpPreparedRequest(request)
        await prepared_request.prepare_data_buffer()
        return prepared_request

    async def send_request_async(
        self, prepared_request: IPreparedRequest, timeout: float
    ) -> HttpResponse:
        prepared_request: AioHttpPreparedRequest
        try:
            response = await self._session.request(
                prepared_request.request.method,
                prepared_request.request.url,
                headers=prepared_request.headers,
                data=prepared_request.data,
                json=prepared_request.json,
                timeout=aiohttp.ClientTimeout(total=timeout),
            )
            text = None
            if prepared_request.request.stream_chunks:
                chunks = response.content.iter_chunks()
                async for chunk, _ in chunks:
                    prepared_request.request.stream_chunks(chunk)
                response.close()
            elif not prepared_request.request.stream:
                text = await response.text()
                response.close()
            return AioHttpResponse(
                response.status, text, response.headers, response
            )

        except asyncio.TimeoutError as e:
            message = f"Request timed out: {e}"
            raise ConnectionException(message, should_retry=True) from e
        except aiohttp.ClientConnectionError as e:
            message = f"ClientConnectionError: {e}"
            raise ConnectionException(message, should_retry=True) from e
        except aiohttp.ClientError as e:
            message = f"ClientError: {e}"
            raise ConnectionException(message, should_retry=False) from e
        except Exception as e:
            message = f"Unexpected request failure: {e}"
            raise ConnectionException(message, should_retry=False) from e
