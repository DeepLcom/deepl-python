# Copyright 2021 DeepL GmbH (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

import deepl
import os
from pydantic import BaseSettings
import pytest
import uuid


# Set environment variables to change this configuration.
# Example: export DEEPL_SERVER_URL=http://localhost:3000/
#          export DEEPL_MOCK_SERVER_PORT=3000
#
# supported use cases:
#  - using real API
#      - user needs to configure their auth_key
#  - using a local mock server
#      - user needs to configure: server_url and set mock_server_port
#      - auth_key can be set empty
#  - using a real server with different IP (e.g. for testing)
#      - user needs to configure their auth_key and server_url
class Config(BaseSettings):
    auth_key: str = None
    server_url: str = None
    mock_server_port: int = None

    class Config:
        env_prefix = "DEEPL_"


@pytest.fixture
def config():
    return Config()


@pytest.fixture
def server(config):
    class Server:
        def __init__(self):
            self.headers = {}
            if config.mock_server_port is not None:
                self.server_url = config.server_url
                self.auth_key = "mock_server"
                uu = str(uuid.uuid1())
                session_uuid = f"{os.getenv('PYTEST_CURRENT_TEST')}/{uu}"
                self.headers["mock-server-session"] = session_uuid
            else:
                self.auth_key = config.auth_key
                self.server_url = config.server_url

        def no_response(self, count):
            """Instructs the mock server to ignore N requests from this
            session, giving no response."""
            if config.mock_server_port is not None:
                self.headers["mock-server-session-no-response-count"] = str(
                    count
                )

        def respond_with_429(self, count):
            """Instructs the mock server to reject N /translate requests from
            this session with 429 status codes."""
            if config.mock_server_port is not None:
                self.headers["mock-server-session-429-count"] = str(count)

        def init_character_limit(self, count):
            """Instructs the mock server to initialize user accounts created by
            this session with given character limit."""
            if config.mock_server_port is not None:
                self.headers["mock-server-session-init-character-limit"] = str(
                    count
                )

        def init_document_limit(self, count):
            """Instructs the mock server to initialize user accounts created by
            this session with given document limit."""
            if config.mock_server_port is not None:
                self.headers["mock-server-session-init-document-limit"] = str(
                    count
                )

        def init_team_document_limit(self, count):
            """Instructs the mock server to initialize user accounts created by
            this session with given team document limit."""
            if config.mock_server_port is not None:
                self.headers[
                    "mock-server-session-init-team-document-limit"
                ] = str(count)

        def set_doc_failure(self, count):
            """Instructs the mock server to fail during translation of N
            documents during this session."""
            if config.mock_server_port is not None:
                self.headers["mock-server-session-doc-failure"] = str(count)

        def set_doc_queue_time(self, milliseconds):
            """Instructs the mock server to queue documents for specified time
            before translation."""
            if config.mock_server_port is not None:
                self.headers["mock-server-session-doc-queue-time"] = str(
                    milliseconds
                )

        def set_doc_translate_time(self, milliseconds):
            """Instructs the mock server to translate documents within
            specified time."""
            if config.mock_server_port is not None:
                self.headers["mock-server-session-doc-translate-time"] = str(
                    milliseconds
                )

    return Server()


def _make_translator(server, auth_key=None):
    """Returns a deepl.Translator for the specified server test fixture.
    The server auth_key is used unless specifically overridden."""
    if auth_key is None:
        auth_key = server.auth_key
    translator = deepl.Translator(auth_key, server_url=server.server_url)

    # If the server test fixture has custom headers defined, update the
    # translator headers and replace with the server headers dictionary.
    # Note: changing the underlying object is necessary because some tests
    # make changes to the headers during tests.
    if server.headers:
        server.headers.update(translator.headers)
        translator.headers = server.headers
    return translator


@pytest.fixture
def translator(server):
    """Returns a deepl.Translator to use in all tests taking a parameter 'translator'."""
    return _make_translator(server)


@pytest.fixture
def translator_with_random_auth_key(server):
    """Returns a deepl.Translator with randomized authentication key,
    for use in mock-server tests."""
    return _make_translator(server, auth_key=str(uuid.uuid1()))


# Decorate test functions with "@needs_mock_server" to skip them if a real
#  server is used
needs_mock_server = pytest.mark.skipif(
    Config().mock_server_port is None,
    reason="this test requires a mock server",
)
# Decorate test functions with "@needs_real_server" to skip them if a mock
#  server is used
needs_real_server = pytest.mark.skipif(
    not (Config().mock_server_port is None),
    reason="this test requires a real server",
)


example_text = {
    "BG": "протонен лъч",
    "CS": "protonový paprsek",
    "DA": "protonstråle",
    "DE": "Protonenstrahl",
    "EL": "δέσμη πρωτονίων",
    "EN": "proton beam",
    "EN-US": "proton beam",
    "EN-GB": "proton beam",
    "ES": "haz de protones",
    "ET": "prootonikiirgus",
    "FI": "protonisäde",
    "FR": "faisceau de protons",
    "HU": "protonnyaláb",
    "IT": "fascio di protoni",
    "JA": "陽子ビーム",
    "LT": "protonų spindulys",
    "LV": "protonu staru kūlis",
    "NL": "protonenbundel",
    "PL": "wiązka protonów",
    "PT": "feixe de prótons",
    "PT-BR": "feixe de prótons",
    "PT-PT": "feixe de prótons",
    "RO": "fascicul de protoni",
    "RU": "протонный луч",
    "SK": "protónový lúč",
    "SL": "protonski žarek",
    "SV": "protonstråle",
    "ZH": "质子束",
}
