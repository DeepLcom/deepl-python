# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

import deepl
import pytest


def test_convert_tsv_to_dict():
    result = deepl.convert_tsv_to_dict("Apple\tApfel\n\nBanana \t Banane  ")
    assert result == {"Apple": "Apfel", "Banana": "Banane"}

    with pytest.raises(ValueError, match="does not contain separator"):
        deepl.convert_tsv_to_dict("no separator")

    with pytest.raises(ValueError, match="more than one term separator"):
        deepl.convert_tsv_to_dict("too\tmany\tseparators")

    with pytest.raises(ValueError, match="duplicates source term"):
        deepl.convert_tsv_to_dict("source\ttarget1\nsource\ttarget2")


def test_convert_dict_to_tsv():
    result = deepl.convert_dict_to_tsv(
        {"Apple": "Apfel", "Banana ": " Banane  "}
    )
    assert result == "Apple\tApfel\nBanana\tBanane"

    with pytest.raises(ValueError, match="invalid character"):
        deepl.convert_dict_to_tsv({"source\t1": "target"})

    with pytest.raises(ValueError, match="not a valid string"):
        deepl.convert_dict_to_tsv({"": "target"})
    with pytest.raises(ValueError, match="not a valid string"):
        deepl.convert_dict_to_tsv({"\t": "target"})
