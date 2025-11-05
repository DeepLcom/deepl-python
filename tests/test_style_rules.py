# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from .conftest import example_text, needs_mock_server

DEFAULT_STYLE_ID = "dca2e053-8ae5-45e6-a0d2-881156e7f4e4"


@needs_mock_server
def test_get_all_style_rules(deepl_client):
    style_rules = deepl_client.get_all_style_rules(detailed=True)

    assert isinstance(style_rules, list)
    assert len(style_rules) == 1
    assert style_rules[0].style_id == DEFAULT_STYLE_ID
    assert style_rules[0].name == "Default Style Rule"
    assert style_rules[0].creation_time is not None
    assert style_rules[0].updated_time is not None
    assert style_rules[0].language == "en"
    assert style_rules[0].version == 1
    assert style_rules[0].configured_rules is not None
    assert style_rules[0].custom_instructions is not None


@needs_mock_server
def test_translate_text_with_style_rule(deepl_client):
    # Note: this test may use the mock server that will not translate the text,
    # therefore we do not check the translated result.
    _ = deepl_client.translate_text(
        example_text["DE"], target_lang="EN-US", style_rule=DEFAULT_STYLE_ID
    )
