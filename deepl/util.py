# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import itertools
import logging
from typing import Dict, Optional

logger = logging.getLogger("deepl")


def _get_log_text(message, **kwargs):
    return (
        message
        + " "
        + " ".join(f"{key}={value}" for key, value in sorted(kwargs.items()))
    )


def log_debug(message, **kwargs):
    text = _get_log_text(message, **kwargs)
    logger.debug(text)


def log_info(message, **kwargs):
    text = _get_log_text(message, **kwargs)
    logger.info(text)


def get_int_safe(d: dict, key: str) -> Optional[int]:
    """Returns value in dictionary with given key as int, or None."""
    try:
        return int(d.get(key))
    except (TypeError, ValueError):
        return None


def auth_key_is_free_account(auth_key: str) -> bool:
    """Returns True if the given authentication key belongs to a DeepL API Free
    account, otherwise False."""
    return auth_key.endswith(":fx")


def validate_glossary_term(term: str) -> None:
    """Checks if the given glossary term contains any disallowed characters.

    :param term: Glossary term to check for validity.
    :raises ValueError: If the term is not valid or a disallowed character is
    found."""
    if len(term) == 0:
        raise ValueError(f'Term "{term}" is not a valid string')
    if any(
        (
            0 <= ord(char) <= 31  # C0 control characters
            or 128 <= ord(char) <= 159  # C1 control characters
            or char in "\u2028\u2029"  # Unicode newlines
        )
        for char in term
    ):
        raise ValueError(f'Term "{term}" contains invalid character')


def convert_tsv_to_dict(
    tsv: str, term_separator: str = "\t", skip_checks: bool = False
) -> dict:
    """Converts the given tab-separated values (TSV) string to an entries
    dictionary for use in a glossary. Each line should contain a source and
    target term separated by a tab. Empty lines are ignored.

    :param tsv: string containing TSV to parse.
    :param term_separator: optional term separator to use.
    :param skip_checks: set to True to override entry validation.
    :return: dictionary containing parsed entries.
    """
    entries_dict = {}
    for line, index in zip(tsv.splitlines(), itertools.count(1)):
        if not line:
            continue
        if term_separator not in line:
            raise ValueError(
                f"Entry {index} does not contain separator: {line}"
            )
        source, target = line.split(term_separator, 1)
        source, target = source.strip(), target.strip()
        if source in entries_dict:
            raise ValueError(
                f'Entry {index} duplicates source term "{source}"'
            )
        if term_separator in target:
            raise ValueError(
                f"Entry {index} contains more than one term separator: {line}"
            )
        if not skip_checks:
            validate_glossary_term(source)
            validate_glossary_term(target)
        entries_dict[source] = target
    return entries_dict


def convert_dict_to_tsv(
    entry_dict: Dict[str, str], skip_checks: bool = False
) -> str:
    """Converts the given glossary entries dictionary to a tab-separated values
    (TSV) string.

    :param entry_dict: dictionary containing glossary entries.
    :param skip_checks: set to True to override entry validation.
    :return: string containing entries in TSV format.
    """
    if not skip_checks:
        for source, target in entry_dict.items():
            validate_glossary_term(source.strip())
            validate_glossary_term(target.strip())

    return "\n".join(
        f"{s.strip()}\t{t.strip()}" for s, t in entry_dict.items()
    )
