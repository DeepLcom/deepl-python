# Copyright 2025 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from .conftest import example_text


def test_single_text(deepl_client):
    result = deepl_client.rephrase_text(
        example_text["EN"], target_lang="EN-GB"
    )
    assert result.detected_source_language.upper() == "EN"
    epsilon = 0.2
    n_original = len(example_text["EN"])
    n_improved = len(result.text)
    assert 1 / (1.0 + epsilon) <= n_improved / n_original <= (1.0 + epsilon)
