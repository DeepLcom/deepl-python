# Copyright 2025 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from deepl.api_data import (
    Language,
    WriteResult,
)
from deepl.translator import Translator
from typing import (
    Dict,
    Iterable,
    List,
    Optional,
    Union,
)


class DeepLClient(Translator):
    def __init__(
        self,
        auth_key: str,
        *,
        server_url: Optional[str] = None,
        proxy: Union[Dict, str, None] = None,
        send_platform_info: bool = True,
        verify_ssl: Union[bool, str, None] = None,
        skip_language_check: bool = False,
    ):
        super().__init__(
            auth_key,
            server_url=server_url,
            proxy=proxy,
            send_platform_info=send_platform_info,
            verify_ssl=verify_ssl,
            skip_language_check=skip_language_check,
        )

    def rephrase_text(
        self,
        text: Union[str, Iterable[str]],
        *,
        target_lang: Union[None, str, Language] = None,
        style: Optional[str] = None,
        tone: Optional[str] = None,
    ) -> Union[WriteResult, List[WriteResult]]:
        """Improve the text(s) and optionally convert them to the variant of
        the `target_lang` (requires source lang to match target_lang, excluding
        variants).

        :param text: Text to improve.
        :type text: UTF-8 :class:`str`; string sequence (list, tuple, iterator,
            generator)
        :param target_lang: language code the final text should be in, for
            example "DE", "EN-US", "FR".
        :param style: Writing style to be used for the improvement. Either
            style OR tone can be used.
        :param tone: Tone to be used for the improvement. Either style OR tone
            can be used.
        :return: List of WriteResult objects containing results, unless input
            text was one string, then a single WriteResult object is returned.
        """

        if isinstance(text, str):
            if len(text) == 0:
                raise ValueError("text must not be empty")
            text = [text]
            multi_input = False
        elif hasattr(text, "__iter__"):
            multi_input = True
            text = list(text)
        else:
            raise TypeError(
                "text parameter must be a string or an iterable of strings"
            )

        request_data: dict = {"text": text}
        if target_lang:
            request_data["target_lang"] = target_lang
        if style:
            request_data["writing_style"] = style
        if tone:
            request_data["tone"] = tone

        status, content, json = self._api_call(
            "v2/write/rephrase", json=request_data
        )

        self._raise_for_status(status, content, json)

        improvements = (
            json.get("improvements", [])
            if (json and isinstance(json, dict))
            else []
        )
        output = []
        for improvement in improvements:
            text = improvement.get("text", "") if improvement else ""
            detected_source_language = (
                improvement.get("detected_source_language", "")
                if improvement
                else ""
            )
            target_language = (
                improvement.get("target_language", "") if improvement else ""
            )
            output.append(
                WriteResult(text, detected_source_language, target_language)
            )

        return output if multi_input else output[0]
