# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from . import version
from .exceptions import ConnectionException, DeepLException
import http
import platform
import random
import requests  # type: ignore
import traceback
import time
from functools import lru_cache
from typing import Dict, Optional, Tuple, Union
from .util import log_info
from deepl import util
import json as json_module


user_agent = None
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
    def __init__(
        self,
        proxy: Union[Dict, str, None] = None,
        send_platform_info: bool = True,
        verify_ssl: Union[bool, str, None] = None,
    ):
        self._session = requests.Session()
        if proxy:
            if isinstance(proxy, str):
                proxy = {"http": proxy, "https": proxy}
            if not isinstance(proxy, dict):
                raise ValueError(
                    "proxy may be specified as a URL string or dictionary "
                    "containing URL strings for the http and https keys."
                )
            self._session.proxies.update(proxy)
        if verify_ssl is not None:
            self._session.verify = verify_ssl
        self._send_platform_info = send_platform_info
        self._app_info_name: Optional[str] = None
        self._app_info_version: Optional[str] = None

    def set_app_info(self, app_info_name: str, app_info_version: str):
        self._app_info_name = app_info_name
        self._app_info_version = app_info_version
        return self

    def close(self):
        self._session.close()

    def request_with_backoff(
        self,
        method: str,
        url: str,
        data: Optional[dict],
        json: Optional[dict],
        headers: dict,
        stream: bool = False,
        **kwargs,
    ) -> Tuple[int, Union[str, requests.Response]]:
        """Makes API request, retrying if necessary, and returns response.

        Return and exceptions are the same as function request()."""
        backoff = _BackoffTimer()
        request = self._prepare_request(
            method, url, data, json, headers, **kwargs
        )

        while True:
            response: Optional[Tuple[int, Union[str, requests.Response]]]
            try:
                response = self._internal_request(
                    request, stream=stream, timeout=backoff.get_timeout()
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
                    raise exception  # type: ignore[misc]

            if exception is not None:
                log_info(
                    f"Encountered a retryable-exception: {str(exception)}"
                )

            log_info(
                f"Starting retry {backoff.get_num_retries() + 1} for request "
                f"{method} {url} after sleeping for "
                f"{backoff.get_time_until_deadline():.2f} seconds."
            )
            backoff.sleep_until_deadline()

    def request(
        self,
        method: str,
        url: str,
        data: Optional[dict],
        json: Optional[dict],
        headers: dict,
        stream: bool = False,
        **kwargs,
    ) -> Tuple[int, Union[str, requests.Response]]:
        """Makes API request and returns response content.

        Response is returned as HTTP status code and either content string (if
        stream is False) or response (if stream is True).

        If no response is received will raise ConnectionException."""

        request = self._prepare_request(
            method, url, data, json, headers, **kwargs
        )
        return self._internal_request(request, stream)

    def _internal_request(
        self,
        request: requests.PreparedRequest,
        stream: bool,
        timeout: float = min_connection_timeout,
        **kwargs,
    ) -> Tuple[int, Union[str, requests.Response]]:
        try:
            response = self._session.send(
                request, stream=stream, timeout=timeout, **kwargs
            )
            if stream:
                return response.status_code, response
            else:
                try:
                    response.encoding = "UTF-8"
                    return response.status_code, response.text
                finally:
                    response.close()

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
        # Retry on Too-Many-Requests error and internal errors
        return status_code == http.HTTPStatus.TOO_MANY_REQUESTS or (
            status_code >= http.HTTPStatus.INTERNAL_SERVER_ERROR
        )

    def _prepare_request(
        self,
        method: str,
        url: str,
        data: Optional[dict],
        json: Optional[dict],
        headers: dict,
        **kwargs,
    ) -> requests.PreparedRequest:
        try:
            headers.setdefault(
                "User-Agent",
                _generate_user_agent(
                    user_agent,
                    self._send_platform_info,
                    self._app_info_name,
                    self._app_info_version,
                ),
            )

            # TODO review when minimum Python version is raised
            if tuple(map(int, requests.__version__.split("."))) >= (2, 4, 2):
                kwargs["json"] = json
            elif json is not None:
                # This is fine, see official docs
                # https://requests.readthedocs.io/en/latest/user/quickstart/#more-complicated-post-requests
                data = json_module.dumps(json)  # type: ignore[assignment]
                headers["Content-Type"] = "application/json"
            return requests.Request(
                method, url, data=data, headers=headers, **kwargs
            ).prepare()
        except Exception as e:
            raise DeepLException(
                f"Error occurred while preparing request: {e}"
            ) from e


@lru_cache(maxsize=4)
def _generate_user_agent(
    user_agent_str: Optional[str],
    send_platform_info: bool,
    app_info_name: Optional[str],
    app_info_version: Optional[str],
):
    if user_agent_str:
        library_info_str = user_agent_str
    else:
        library_info_str = f"deepl-python/{version.VERSION}"
        if send_platform_info:
            try:
                library_info_str += (
                    f" ({platform.platform()}) "
                    f"python/{platform.python_version()} "
                    f"requests/{requests.__version__}"
                )
            except Exception:
                util.log_info(
                    "Exception when querying platform information:\n"
                    + traceback.format_exc()
                )
    if app_info_name and app_info_version:
        library_info_str += f" {app_info_name}/{app_info_version}"
    return library_info_str
