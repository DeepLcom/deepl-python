# Copyright 2021 DeepL GmbH (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from . import version
from .exceptions import ConnectionException
import http
import random
import requests
import time
from typing import Optional, Tuple, Union
from .util import log_info


user_agent = f"deepl-python/{version.VERSION}"
max_network_retries = 5
min_connection_timeout = 10.0


class _BackoffTimer:
    """Implements exponential-backoff strategy.
    This strategy is based on the GRPC Connection Backoff Protocol:
    https://github.com/grpc/grpc/blob/master/doc/connection-backoff.md"""

    BACKOFF_INITIAL = 1.0
    BACKOFF_MAX = 120.0
    BACKOFF_JITTER = 0.23
    BACKOFF_MULTIPLIER = 1.6

    def __init__(self):
        self._num_retries = 0
        self._backoff = self.BACKOFF_INITIAL
        self._deadline = time.time() + self._backoff

    def get_num_retries(self):
        return self._num_retries

    def get_timeout(self):
        return max(self.get_time_until_deadline(), min_connection_timeout)

    def get_time_until_deadline(self):
        return max(self._deadline - time.time(), 0.0)

    def sleep_until_deadline(self):
        time.sleep(self.get_time_until_deadline())

        # Apply multiplier to current backoff time
        self._backoff = min(
            self._backoff * self.BACKOFF_MULTIPLIER, self.BACKOFF_MAX
        )

        # Get deadline by applying jitter as a proportion of backoff:
        # if jitter is 0.1, then multiply backoff by random value in [0.9, 1.1]
        self._deadline = time.time() + self._backoff * (
            1 + self.BACKOFF_JITTER * random.uniform(-1, 1)
        )
        self._num_retries += 1


class HttpClient:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers = {"User-Agent": user_agent}
        pass

    def close(self):
        self._session.close()

    def request_with_backoff(
        self, method: str, url: str, data: Optional[dict], **kwargs
    ) -> Tuple[int, Union[str, requests.Response]]:
        """Makes API request, retrying if necessary, and returns response.

        Return and exceptions are the same as function request()."""
        backoff = _BackoffTimer()
        while True:
            response: Optional[Tuple[int, Union[str, requests.Response]]]
            try:
                response = self.request(
                    method, url, data, timeout=backoff.get_timeout(), **kwargs
                )
                exception = None
            except Exception as e:
                response = None
                exception = e

            if not self._should_retry(
                response, exception, backoff.get_num_retries()
            ):
                if response is not None:
                    return response
                else:
                    raise exception

            if exception is not None:
                log_info(
                    f"Encountered a retryable-exception: {str(exception)}"
                )

            log_info(
                f"Starting retry {backoff.get_num_retries() + 1} for request {method} {url} "
                f"after sleeping for {backoff.get_time_until_deadline():.2f} seconds."
            )
            backoff.sleep_until_deadline()

    def request(
        self,
        method: str,
        url: str,
        data: Optional[dict],
        timeout: float,
        stream: bool = False,
        **kwargs,
    ) -> Tuple[int, Union[str, requests.Response]]:
        """Makes API request and returns response content.

        Response is returned as HTTP status code and either content string (if
        stream is False) or response (if stream is True).

        If no response is received will raise ConnectionException."""
        try:
            if stream:
                response = self._session.request(
                    method,
                    url,
                    data=data,
                    timeout=timeout,
                    stream=True,
                    **kwargs,
                )
                return response.status_code, response

            else:
                with self._session.request(
                    method, url, data=data, timeout=timeout, **kwargs
                ) as response:
                    response.encoding = "UTF-8"
                    return response.status_code, response.text

        except requests.exceptions.ConnectionError as e:
            message = f"Connection failed: {e}"
            raise ConnectionException(message, should_retry=True) from e
        except requests.exceptions.Timeout as e:
            message = f"Request timed out: {e}"
            raise ConnectionException(message, should_retry=True) from e
        except requests.exceptions.RequestException as e:
            message = f"Request failed: {e}"
            raise ConnectionException(message, should_retry=False) from e
        except Exception as e:
            message = f"Unexpected request failure: {e}"
            raise ConnectionException(message, should_retry=False) from e

    def _should_retry(self, response, exception, num_retries):
        if num_retries >= max_network_retries:
            return False

        if response is None:
            return exception.should_retry

        status_code, _ = response
        # Retry on Too-Many-Requests error and internal errors except
        # Service-Unavailable errors
        return status_code == http.HTTPStatus.TOO_MANY_REQUESTS or (
            status_code >= http.HTTPStatus.INTERNAL_SERVER_ERROR
            and status_code != http.HTTPStatus.SERVICE_UNAVAILABLE
        )
