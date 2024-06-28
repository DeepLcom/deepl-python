# Copyright 2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import pytest
import deepl
from conftest import example_text, needs_async

pytest_plugins = ("pytest_asyncio",)
default_lang_args = {"target_lang": "DE", "source_lang": "EN"}


@needs_async
@pytest.mark.asyncio
async def test_translate_text(async_translator_factory):
    async with async_translator_factory() as async_translator:
        result = await async_translator.translate_text(
            example_text["EN"], target_lang="de"
        )
        assert example_text["DE"] == result.text
        assert "EN" == result.detected_source_lang


@needs_async
@pytest.mark.asyncio
async def test_translate_with_glossary(
    async_translator_factory,
    glossary_name,
    server,
):
    source_lang = "EN"
    target_lang = "DE"
    input_text = "The artist was awarded a prize."
    entries = {"artist": "Maler", "prize": "Gewinn"}

    async with async_translator_factory() as async_translator:
        created_glossary = await async_translator.create_glossary(
            glossary_name,
            source_lang=source_lang,
            target_lang=target_lang,
            entries=entries,
        )

        glossaries = await async_translator.list_glossaries()
        assert any(
            (
                g.name == glossary_name
                and g.glossary_id == created_glossary.glossary_id
            )
            for g in glossaries
        )

        returned_entries = await async_translator.get_glossary_entries(
            created_glossary
        )
        assert returned_entries == entries

        if not server.is_mock_server:
            result = await async_translator.translate_text(
                input_text,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary=created_glossary,
            )
            assert "Maler" in result.text
            assert "Gewinn" in result.text
        await async_translator.delete_glossary(created_glossary)


@needs_async
@pytest.mark.asyncio
async def test_translate_document_with_retry_and_wait(
    async_translator_factory,
    server,
    example_document_path,
    example_document_translation,
    output_document_path,
    monkeypatch,
):
    server.no_response(1)
    server.set_doc_queue_time(2000)
    server.set_doc_translate_time(2000)
    # Lower the timeout for this test, and restore after test
    monkeypatch.setattr(deepl.http_client, "min_connection_timeout", 1.0)

    async with async_translator_factory() as async_translator:
        await async_translator.translate_document_from_filepath(
            example_document_path,
            output_path=output_document_path,
            **default_lang_args,
        )
    assert example_document_translation == output_document_path.read_text()
