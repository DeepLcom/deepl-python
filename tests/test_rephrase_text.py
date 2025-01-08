# Copyright 2025 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from .conftest import example_text, needs_real_server
from deepl.api_data import WriteResult, WritingStyle


def test_single_text(deepl_client):
    result = deepl_client.rephrase_text(
        example_text["EN"], target_lang="EN-GB"
    )
    _check_sanity_of_improvements(example_text["EN"], result)


@needs_real_server
def test_business_style(deepl_client):
    input_text = "As Gregor Samsa awoke one morning from uneasy dreams he found himself transformed in his bed into a gigantic insect."  # noqa
    result = deepl_client.rephrase_text(
        input_text, target_lang="EN-US", style=WritingStyle.BUSINESS.value
    )
    _check_sanity_of_improvements(input_text, result)


def _check_sanity_of_improvements(
    input_text: str,
    result: WriteResult,
    expected_lang_uppercase="EN",
    epsilon=0.2,
):
    assert result.detected_source_language.upper() == expected_lang_uppercase
    n_improved = len(result.text)
    n_original = len(input_text)
    assert 1 / (1.0 + epsilon) <= n_improved / n_original <= (1.0 + epsilon)
