# Copyright 2021 DeepL GmbH (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from .conftest import *
import datetime
import deepl
import pytest

INVALID_GLOSSARY_ID = "invalid_glossary_id"
NONEXISTENT_GLOSSARY_ID = "96ab91fd-e715-41a1-adeb-5d701f84a483"


def test_glossary_create(translator):
    name = "test"
    source_lang = "EN"
    target_lang = "DE"
    glossary = translator.create_glossary(
        name, source_lang, target_lang, {"Hello": "Hallo"}
    )
    assert glossary.name == name
    assert glossary.source_lang == source_lang
    assert glossary.target_lang == target_lang
    # Note: ready field is indeterminate
    # Note: creation_time according to server might differ from local clock
    assert glossary.entry_count == 1

    get_result = translator.get_glossary(glossary.glossary_id)
    assert get_result.name == glossary.name
    assert get_result.source_lang == glossary.source_lang
    assert get_result.target_lang == glossary.target_lang
    assert get_result.creation_time == glossary.creation_time
    assert get_result.entry_count == glossary.entry_count


def test_glossary_create_invalid(translator):
    name = "test"
    with pytest.raises(ValueError):
        translator.create_glossary("", "EN", "DE", {"Hello": "Hallo"})
    with pytest.raises(deepl.DeepLException):
        translator.create_glossary(name, "EN", "JA", {"Hello": "Hallo"})
    with pytest.raises(deepl.DeepLException):
        translator.create_glossary(name, "JA", "DE", {"Hello": "Hallo"})
    with pytest.raises(deepl.DeepLException):
        translator.create_glossary(name, "EN", "XX", {"Hello": "Hallo"})
    with pytest.raises(ValueError):
        translator.create_glossary(name, "EN", "DE", {})


def test_glossary_get(translator, glossary_name):
    source_lang = "EN"
    target_lang = "DE"
    entries = {"Hello": "Hallo"}
    created_glossary = create_glossary(
        translator,
        glossary_name,
        source_lang=source_lang,
        target_lang=target_lang,
        entries=entries,
    )

    glossary = translator.get_glossary(created_glossary.glossary_id)
    assert glossary.glossary_id == created_glossary.glossary_id
    assert glossary.name == glossary_name
    assert glossary.source_lang == source_lang
    assert glossary.target_lang == target_lang
    assert glossary.entry_count == len(entries)

    with pytest.raises(deepl.DeepLException):
        translator.get_glossary(INVALID_GLOSSARY_ID)
    with pytest.raises(deepl.GlossaryNotFoundException):
        translator.get_glossary(NONEXISTENT_GLOSSARY_ID)


def test_glossary_get_entries(translator, glossary_name):
    source_lang = "EN"
    target_lang = "DE"
    entries = {"Apple": "Apfel", "Banana": "Banane"}
    created_glossary = create_glossary(
        translator,
        glossary_name,
        source_lang=source_lang,
        target_lang=target_lang,
        entries=entries,
    )
    assert translator.get_glossary_entries(created_glossary) == entries
    assert (
        translator.get_glossary_entries(created_glossary.glossary_id)
        == entries
    )

    with pytest.raises(deepl.DeepLException):
        translator.get_glossary_entries(INVALID_GLOSSARY_ID)
    with pytest.raises(deepl.GlossaryNotFoundException):
        translator.get_glossary_entries(NONEXISTENT_GLOSSARY_ID)


def test_glossary_list(translator, glossary_name):
    source_lang = "EN"
    target_lang = "DE"
    translator.create_glossary(
        glossary_name, source_lang, target_lang, {"Hello": "Hallo"}
    )
    glossaries = translator.list_glossaries()
    assert any(glossary.name == glossary_name for glossary in glossaries)


def test_glossary_delete(translator, glossary_name):
    glossary = create_glossary(translator, glossary_name)
    translator.delete_glossary(glossary)
    with pytest.raises(deepl.GlossaryNotFoundException):
        translator.get_glossary(glossary.glossary_id)

    with pytest.raises(deepl.DeepLException):
        translator.delete_glossary(INVALID_GLOSSARY_ID)
    with pytest.raises(deepl.GlossaryNotFoundException):
        translator.delete_glossary(NONEXISTENT_GLOSSARY_ID)


@needs_real_server
def test_glossary_translate_text_sentence(translator, glossary_name):
    source_lang = "EN"
    target_lang = "DE"
    input_text = "The artist was awarded a prize."
    glossary = translator.create_glossary(
        glossary_name,
        source_lang,
        target_lang,
        {"artist": "Maler", "prize": "Gewinn"},
    )
    result = translator.translate_text(
        input_text, source_lang="EN", target_lang="DE", glossary=glossary
    )
    assert "Maler" in result.text
    assert "Gewinn" in result.text


def test_glossary_translate_text_basic(translator, glossary_name):
    texts_en = ["Apple", "Banana"]
    texts_de = ["Apfel", "Banane"]
    entries_ende = {en: de for en, de in zip(texts_en, texts_de)}
    entries_deen = {de: en for de, en in zip(texts_de, texts_en)}
    glossary_ende = create_glossary(
        translator,
        f"{glossary_name}_ende",
        entries=entries_ende,
        source_lang="EN",
        target_lang="DE",
    )
    glossary_deen = create_glossary(
        translator,
        f"{glossary_name}_deen",
        entries=entries_deen,
        source_lang="DE",
        target_lang="EN",
    )

    result = translator.translate_text_with_glossary(texts_en, glossary_ende)
    assert [r.text for r in result] == texts_de

    # Using glossary with target=EN is possible, British English is assumed
    result = translator.translate_text_with_glossary(texts_de, glossary_deen)
    assert [r.text for r in result] == texts_en

    # Can override to American English
    result = translator.translate_text_with_glossary(
        texts_de, glossary_deen, target_lang="EN-US"
    )
    assert [r.text for r in result] == texts_en

    result = translator.translate_text(
        texts_de,
        source_lang="DE",
        target_lang="EN-US",
        glossary=glossary_deen.glossary_id,
    )
    assert [r.text for r in result] == texts_en
    result = translator.translate_text(
        texts_de, source_lang="DE", target_lang="EN-US", glossary=glossary_deen
    )
    assert [r.text for r in result] == texts_en


def test_glossary_translate_document(
    translator,
    glossary_name,
    example_document_path,
    output_document_path,
):
    input_text = "artist\nprize"
    expected_output_text = "Maler\nGewinn"

    glossary = create_glossary(
        translator,
        glossary_name,
        entries={"artist": "Maler", "prize": "Gewinn"},
        source_lang="EN",
        target_lang="DE",
    )
    example_document_path.write_text(input_text)
    translator.translate_document_from_filepath(
        example_document_path,
        output_path=output_document_path,
        source_lang="EN",
        target_lang="DE",
        glossary=glossary,
    )
    assert expected_output_text == output_document_path.read_text()


def test_glossary_translate_text_invalid(translator, glossary_name):
    glossary_ende = create_glossary(
        translator, f"{glossary_name}_ende", source_lang="EN", target_lang="DE"
    )
    glossary_deen = create_glossary(
        translator, f"{glossary_name}_deen", source_lang="DE", target_lang="EN"
    )
    text = "Test"

    with pytest.raises(ValueError, match="source_lang is required"):
        translator.translate_text(
            text, target_lang="DE", glossary=glossary_ende
        )

    with pytest.raises(ValueError, match="lang must match glossary"):
        translator.translate_text(
            text, source_lang="DE", target_lang="EN", glossary=glossary_ende
        )

    with pytest.raises(
        deepl.DeepLException, match='target_lang="EN" is deprecated'
    ):
        translator.translate_text(
            text,
            source_lang="DE",
            target_lang="EN",
            glossary=glossary_deen.glossary_id,
        )
