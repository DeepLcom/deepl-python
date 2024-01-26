# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from typing import Union, Dict

import requests

from .exceptions import ConnectionException
from .ihttp_client import IHttpClient, IPreparedRequest
from .translator_base import HttpResponse, HttpRequest


class RequestPreparedRequest(IPreparedRequest):
    def __init__(self, request: HttpRequest):
        super().__init__(request)
        kwargs = {}
        data = request.data
        # TODO review when minimum Python version is raised
        if tuple(map(int, requests.__version__.split("."))) >= (2, 4, 2):
            kwargs["json"] = request.json
        elif request.json is not None:
            # This is fine, see official docs
            # https://requests.readthedocs.io/en/latest/user/quickstart/#more-complicated-post-requests
            data = json_module.dumps(json)  # type: ignore[assignment]
            request.headers["Content-Type"] = "application/json"
        self.prepared_request = requests.Request(
            request.method,
            request.url,
            data=data,
            headers=request.headers,
            **kwargs,
        ).prepare()


class RequestsHttpClient(IHttpClient):
    def __init__(
        self,
        proxy: Union[Dict, str, None] = None,
        verify_ssl: Union[bool, str, None] = None,
    ):
        self._session = requests.Session()
        if proxy:
            if not isinstance(proxy, dict):
                raise ValueError(
                    "proxy may be specified as a URL string or dictionary "
                    "containing URL strings for the http and https keys."
                )
            self._session.proxies.update(proxy)
        if verify_ssl is not None:
            self._session.verify = verify_ssl

        super().__init__()

    def close(self):
        self._session.close()

    def prepare_request(self, request: HttpRequest) -> IPreparedRequest:
        return RequestPreparedRequest(request)

    def send_request(
        self, prepared_request: IPreparedRequest, timeout: float
    ) -> HttpResponse:
        prepared_request: RequestPreparedRequest
        stream = False  #  TODO prepared_request.request.stream
        try:
            response = self._session.send(
                prepared_request.prepared_request,
                stream=stream,
                timeout=timeout,
            )
            if stream:
                return HttpResponse(
                    response.status_code, None, dict(response.headers.items())
                )  # TODO handle streams
            else:
                try:
                    response.encoding = "UTF-8"
                    return HttpResponse(
                        response.status_code,
                        response.text,
                        dict(response.headers.items()),
                    )
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
