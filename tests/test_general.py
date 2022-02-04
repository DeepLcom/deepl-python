# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from .conftest import example_text, needs_mock_server, needs_mock_proxy_server
import deepl
import pathlib
import pytest


def test_version():
    assert "1.4.1" == deepl.__version__


@pytest.mark.parametrize(
    "lang",
    [k for k in example_text.keys()],
)
def test_example_translation(lang, translator):
    """Tests translations of pre-prepared example texts to ensure translation
    is working.

    The texts are translations of "proton beam"."""

    input_text = example_text[lang]
    result_text = translator.translate_text(
        input_text, target_lang="EN-US"
    ).text.lower()
    assert "proton" in result_text


def test_translate_with_enums(translator):
    result = translator.translate_text(
        example_text["EN"],
        source_lang=deepl.Language.ENGLISH,
        target_lang=deepl.Language.GERMAN,
    )
    assert example_text["DE"] == result.text


def test_invalid_authkey(server):
    translator = deepl.Translator("invalid", server_url=server.server_url)
    with pytest.raises(deepl.exceptions.AuthorizationException):
        translator.get_usage()


def test_invalid_server_url(server):
    translator = deepl.Translator("invalid", server_url="http:/api.deepl.com")
    with pytest.raises(deepl.exceptions.DeepLException):
        translator.get_usage()


def test_usage(translator):
    usage = translator.get_usage()
    assert "Usage this billing period" in str(usage)


def test_language(translator):
    source_languages = translator.get_source_languages()
    for source_language in source_languages:
        if source_language.code == "EN":
            assert source_language.name == "English"
        assert str(source_language) == source_language.code
        assert source_language.supports_formality is None

    target_languages = translator.get_target_languages()
    for target_language in target_languages:
        if target_language.code == "DE":
            assert target_language.supports_formality
        assert target_language.supports_formality is not None


def test_glossary_languages(translator):
    glossary_languages = translator.get_glossary_languages()
    assert len(glossary_languages) > 0
    for language_pair in glossary_languages:
        assert len(language_pair.source_lang) > 0
        assert len(language_pair.target_lang) > 0


def test_server_url_selected_based_on_auth_key(server):
    translator_normal = deepl.Translator("ABCD")
    translator_free = deepl.Translator("ABCD:fx")
    assert translator_normal.server_url == "https://api.deepl.com"
    assert translator_free.server_url == "https://api-free.deepl.com"


@needs_mock_proxy_server
def test_proxy_usage(
    server,
    translator_with_random_auth_key,
    translator_with_random_auth_key_and_proxy,
):
    server.expect_proxy()

    translator_with_random_auth_key_and_proxy.get_usage()

    with pytest.raises(deepl.DeepLException):
        translator_with_random_auth_key.get_usage()


@needs_mock_server
def test_usage_no_response(translator, server, monkeypatch):
    server.no_response(2)

    # Lower the retry count and timeout for this test, and restore after test
    monkeypatch.setattr(deepl.http_client, "max_network_retries", 0)
    monkeypatch.setattr(deepl.http_client, "min_connection_timeout", 1.0)

    with pytest.raises(deepl.exceptions.ConnectionException):
        translator.get_usage()


@needs_mock_server
def test_translate_too_many_requests(translator, server, monkeypatch):
    server.respond_with_429(2)
    # Lower the retry count and timeout for this test, and restore after test
    monkeypatch.setattr(deepl.http_client, "max_network_retries", 1)
    monkeypatch.setattr(deepl.http_client, "min_connection_timeout", 1.0)

    with pytest.raises(deepl.exceptions.TooManyRequestsException):
        translator.translate_text(example_text["EN"], target_lang="DE")


@needs_mock_server
def test_usage_overrun(translator_with_random_auth_key, server, tmpdir):
    character_limit = 20
    document_limit = 1
    server.init_character_limit(character_limit)
    server.init_document_limit(document_limit)

    translator = translator_with_random_auth_key
    usage = translator.get_usage()
    assert usage.character.limit == character_limit
    assert usage.document.limit == document_limit
    assert "Characters: 0 of 20" in str(usage)
    assert "Documents: 0 of 1" in str(usage)

    tmpdir = pathlib.Path(tmpdir)
    input_path = tmpdir / "example_document.txt"
    input_path.write_text("a" * character_limit)
    output_path = tmpdir / "example_document_output.txt"
    translator.translate_document_from_filepath(
        input_path, output_path, target_lang="DE"
    )

    usage = translator.get_usage()
    assert usage.any_limit_exceeded
    assert usage.document.limit_exceeded
    assert usage.character.limit_exceeded
    assert not usage.team_document.limit_exceeded

    with pytest.raises(deepl.exceptions.QuotaExceededException):
        translator.translate_document_from_filepath(
            input_path, output_path, target_lang="DE"
        )

    with pytest.raises(deepl.exceptions.QuotaExceededException):
        translator.translate_text(example_text["EN"], target_lang="DE")


@needs_mock_server
def test_usage_team_document_limit(
    translator_with_random_auth_key, server, tmpdir
):
    team_document_limit = 1
    server.init_character_limit(0)
    server.init_document_limit(0)
    server.init_team_document_limit(team_document_limit)

    translator = translator_with_random_auth_key
    usage = translator.get_usage()
    assert not usage.any_limit_exceeded
    assert "Characters" not in str(usage)
    assert "Documents" not in str(usage)
    assert "Team documents: 0 of 1" in str(usage)

    tmpdir = pathlib.Path(tmpdir)
    input_path = tmpdir / "example_document.txt"
    input_path.write_text("a")
    output_path = tmpdir / "example_document_output.txt"
    translator.translate_document_from_filepath(
        input_path, output_path, target_lang="DE"
    )

    usage = translator.get_usage()
    assert usage.any_limit_exceeded
    assert not usage.document.limit_exceeded
    assert not usage.character.limit_exceeded
    assert usage.team_document.limit_exceeded
