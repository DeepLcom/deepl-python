# Copyright 2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from . import backoff_timer
from .exceptions import DeepLException, ConnectionException
from .ihttp_client import IHttpClient, IPreparedRequest
from .translator_base import HttpRequest, HttpResponse
from .util import log_info


class IAsyncHttpClient(IHttpClient, ABC):
    @abstractmethod
    async def send_request_async(
        self, prepared_request: IPreparedRequest, timeout: float
    ) -> HttpResponse:
        """
        Async implementations should this instead of send_request.
        """
        pass

    @abstractmethod
    async def prepare_request(self, request: HttpRequest) -> IPreparedRequest:
        """
        Implementations should prepare the given request suitable for their
        purposes. Any exceptions can be thrown, they will be rethrown.
        """
        pass

    @abstractmethod
    async def close(self):
        """
        Async implementations may implement this, e.g. to clean up sessions.
        """
        pass

    async def request_with_backoff_async(
        self, request: HttpRequest
    ) -> HttpResponse:
        """
        Makes API request, retrying if necessary, and returns response.
        """

        self._log_request(request)
        try:
            prepared_request = await self.prepare_request(request)
        except Exception as e:
            raise DeepLException(
                f"Error occurred while preparing request: {e}"
            ) from e

        backoff = backoff_timer.BackoffTimer()
        while True:
            response: Optional[HttpResponse]
            exception: Optional[ConnectionException]
            try:
                response = await self.send_request_async(
                    prepared_request, timeout=backoff.get_timeout()
                )
                exception = None
            except ConnectionException as e:
                response = None
                exception = e
            except Exception as e:
                raise DeepLException(
                    f"Unexpected error raised while sending request: {e}"
                ) from e

            if not self._should_retry(
                response, exception, backoff.get_num_retries()
            ):
                if response is not None:
                    self._log_response(request, response)
                    return response
                else:
                    raise exception  # type: ignore[misc]

            if exception is not None:
                log_info(
                    f"Encountered a retryable-exception: {str(exception)}"
                )

            log_info(
                f"Starting retry {backoff.get_num_retries() + 1} for request "
                f"{request.method} {request.url} after sleeping for "
                f"{backoff.get_time_until_deadline():.2f} seconds."
            )
            await asyncio.sleep(backoff.get_time_until_wakeup())

        pass

    def request_with_backoff(self, **kwargs):
        raise NotImplementedError(
            "IAsyncHttpClient implements request_with_backoff_async instead "
            "of request_with_backoff"
        )

    def send_request(
        self, prepared_request: IPreparedRequest, timeout: float
    ) -> HttpResponse:
        raise NotImplementedError(
            "IAsyncHttpClient implements send_request_async instead of "
            "send_request"
        )
