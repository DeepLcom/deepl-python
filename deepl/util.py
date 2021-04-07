import logging
from typing import Optional

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
