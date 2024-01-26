# Copyright 2022-2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import time
from abc import abstractmethod, ABC

from . import http_client
from .backoff_timer import BackoffTimer
from .translator_base import HttpRequest, HttpResponse
from .exceptions import ConnectionException, DeepLException
import http
from typing import Dict, Optional, Tuple, Union, Any
from .util import log_info
from deepl import util
import json as json_module


class IPreparedRequest(ABC):
    def __init__(self, request: HttpRequest):
        self.request = request


class IHttpClient(ABC):
    @abstractmethod
    def prepare_request(self, request: HttpRequest) -> IPreparedRequest:
        """
        Implementations should prepare the given request suitable for their purposes.
        Any exceptions can be thrown, they will be rethrown up.
        """
        pass

    @abstractmethod
    def send_request(
        self, prepared_request: IPreparedRequest, timeout: float
    ) -> HttpResponse:
        """
        Implementations should send the given prepared request, respecting the given timeout.

        Sending the request should be retryable: the prepared request must not be consumed by
        this operation. This is particularly relevant when streaming file data.

        Any failures should throw a deepl.ConnectionException with should_retry set sensibly.
        """
        pass

    def request_with_backoff(self, request: HttpRequest) -> HttpResponse:
        """Makes API request, retrying if necessary, and returns response.

        Return and exceptions are the same as function request()."""

        try:
            prepared_request = self.prepare_request(request)
        except Exception as e:
            raise DeepLException(
                f"Error occurred while preparing request: {e}"
            ) from e

        backoff = BackoffTimer()
        while True:
            response: Optional[HttpResponse]
            exception: Optional[ConnectionException]
            try:
                response = self.send_request(
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
            time.sleep(backoff.get_time_until_wakeup())

    # def request(
    #     self,
    #     method: str,
    #     url: str,
    #     data: Optional[dict],
    #     json: Optional[dict],
    #     headers: dict,
    #     stream: bool = False,
    #     **kwargs,
    # ) -> Tuple[int, Union[str, requests.Response]]:
    #     """Makes API request and returns response content.
    #
    #     Response is returned as HTTP status code and either content string (if
    #     stream is False) or response (if stream is True).
    #
    #     If no response is received will raise ConnectionException."""
    #
    #     request = self._prepare_request(
    #         method, url, data, json, headers, **kwargs
    #     )
    #     return self._internal_request(request, stream)

    def _should_retry(
        self,
        response: Optional[HttpResponse],
        exception: Optional[ConnectionException],
        num_retries: int,
    ) -> bool:
        if num_retries >= http_client.max_network_retries:
            return False

        if exception is not None:
            return exception.should_retry

        status_code = response.status_code
        # Retry on Too-Many-Requests error and internal errors
        return status_code == http.HTTPStatus.TOO_MANY_REQUESTS or (
            status_code >= http.HTTPStatus.INTERNAL_SERVER_ERROR
        )
