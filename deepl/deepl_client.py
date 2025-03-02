# Copyright 2025 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from deepl.api_data import (
    MultilingualGlossaryDictionaryEntries,
    MultilingualGlossaryDictionaryEntriesResponse,
    MultilingualGlossaryDictionaryInfo,
    MultilingualGlossaryInfo,
    Language,
    WriteResult,
)
from deepl.translator import Translator
from deepl import util
from typing import (
    Any,
    BinaryIO,
    Dict,
    Iterable,
    List,
    Optional,
    TextIO,
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

    def create_multilingual_glossary(
        self,
        name: str,
        glossary_dicts: List[MultilingualGlossaryDictionaryEntries],
    ) -> MultilingualGlossaryInfo:
        """Creates a glossary with given name with all of the specified
        dictionaries, each with their own language pair and entries. The
        glossary may be used in the translate_text functions.

        The available glossary language pairs can be queried using
        get_glossary_languages(). Glossaries apply to languages, not specific
        language variants. A glossary for a language applies to any variant
        of that language: a glossary with target language EN may be used to
        translate texts into both EN-US and EN-GB.

        This function requires the glossary entries for each dictionary to be
        provided as a dictionary of source-target terms. To create a glossary
        from a CSV file downloaded from the DeepL website, see
        create_glossary_from_csv().

        :param name: user-defined name to attach to glossary.
        :param dictionaries: a list of MultilingualGlossaryDictionaryEntries
            which each contains entries for a particular language pair
        :return: GlossaryInfo containing information about created glossary.

        :raises ValueError: If the glossary name is empty, or entries are
            empty or invalid.
        :raises DeepLException: If source and target language pair are not
            supported for glossaries.
        """
        if any(map(lambda d: not d.entries, glossary_dicts)):
            raise ValueError("glossary entries must not be empty")

        return self._create_multilingual_glossary(name, glossary_dicts)

    def create_multilingual_glossary_from_csv(
        self,
        name: str,
        source_lang: str,
        target_lang: str,
        csv_data: Union[TextIO, BinaryIO, str, bytes, Any],
    ) -> MultilingualGlossaryInfo:
        """Creates a glossary with given name for the source and target
        languages, containing the entries in the given CSV data.
        The glossary may be used in the translate_text functions.

        The available glossary language pairs can be queried using
        get_glossary_languages(). Glossaries apply to languages, not specific
        language variants. A glossary for a language applies to any variant
        of that language: a glossary with target language EN may be used to
        translate texts into both EN-US and EN-GB.

        This function allows you to upload a glossary CSV file that you have
        downloaded from the DeepL website.

        Information about the expected CSV format can be found in the API
        documentation: https://developers.deepl.com/docs/api-reference/glossaries#csv-comma-separated-values  # noqa

        :param name: user-defined name to attach to glossary.
        :param source_lang: Language of source entries.
        :param target_lang: Language of target entries.
        :param csv_data: CSV data containing glossary entries, either as a
            file-like object or string or bytes containing file content.
        :return: GlossaryInfo containing information about created glossary.

        :raises ValueError: If the glossary name is empty, or entries are
            empty or invalid.
        :raises DeepLException: If source and target language pair are not
            supported for glossaries.
        """
        entries = util.convert_csv_to_dict(csv_data)

        dictionaries = [
            MultilingualGlossaryDictionaryEntries(
                source_lang, target_lang, entries
            )
        ]
        return self._create_multilingual_glossary(name, dictionaries)

    def _create_multilingual_glossary(
        self,
        name: str,
        glossary_dicts: List[MultilingualGlossaryDictionaryEntries],
    ) -> MultilingualGlossaryInfo:
        if not name:
            raise ValueError("glossary name must not be empty")

        req_glossary_dicts = []
        # glossaries are only supported for base language types
        for glossary_dict in glossary_dicts:
            req_glossary_dict = {
                "source_lang": Language.remove_regional_variant(
                    glossary_dict.source_lang
                ),
                "target_lang": Language.remove_regional_variant(
                    glossary_dict.target_lang
                ),
                "entries": util.convert_dict_to_tsv(glossary_dict.entries),
                "entries_format": "tsv",
            }
            req_glossary_dicts.append(req_glossary_dict)

        request_data = {
            "name": name,
            "dictionaries": req_glossary_dicts,
        }

        status, content, json = self._api_call(
            "v3/glossaries", json=request_data
        )
        self._raise_for_status(status, content, json, glossary=True)
        return MultilingualGlossaryInfo.from_json(json)

    def update_multilingual_glossary_name(
        self,
        glossary: Union[str, MultilingualGlossaryInfo],
        name: str,
    ) -> MultilingualGlossaryInfo:
        """Updates the name of a glossary with the provided name.

        :param glossary: GlossaryInfo or ID of glossary to update.
        :param name: The new name of the glossary
        :return: MultilingualGlossaryInfo containing information about updated
            glossary.

        :raises ValueError: If the name is empty or invalid.
        :raises DeepLException: If the glossary cannot be found.
        """
        if not name:
            raise ValueError("glossary name must not be empty")

        if isinstance(glossary, MultilingualGlossaryInfo):
            glossary = glossary.glossary_id
        request_data = {"name": name}

        status, content, json = self._api_call(
            f"v3/glossaries/{glossary}", method="PATCH", json=request_data
        )
        self._raise_for_status(status, content, json, glossary=True)
        return MultilingualGlossaryInfo.from_json(json)

    def update_multilingual_glossary_dictionary(
        self,
        glossary: Union[str, MultilingualGlossaryInfo],
        glossary_dict: MultilingualGlossaryDictionaryEntries,
    ) -> MultilingualGlossaryInfo:
        """Updates or creates a glossary dictionary with given glossary
        dictionary with its entries for the source and target languages.
        Either updates the glossary's entries if they exist for the
        given language pair, or adds any new ones to the dictionary if not.

        The available glossary language pairs can be queried using
        get_glossary_languages(). Glossaries apply to languages, not specific
        language variants. A glossary for a language applies to any variant
        of that language: a glossary with target language EN may be used to
        translate texts into both EN-US and EN-GB.

        This function requires the glossary entries to be provided as a
        dictionary of source-target terms. To create a glossary from a CSV file
        downloaded from the DeepL website, see create_glossary_from_csv().

        :param glossary: GlossaryInfo or ID of glossary to update.
        :param glossary_dict: The new or updated glossary dictionary
        :return: MultilingualGlossaryInfo containing information about updated
            glossary.

        :raises ValueError: If the glossary entries are empty or invalid.
        :raises DeepLException: If source and target language pair are not
            supported for glossaries.
        """
        if not glossary_dict or not glossary_dict.entries:
            raise ValueError("glossary entries must not be empty")

        if isinstance(glossary, MultilingualGlossaryInfo):
            glossary = glossary.glossary_id

        return self._update_multilingual_glossary(glossary, [glossary_dict])

    def update_multilingual_glossary_dictionary_from_csv(
        self,
        glossary: Union[str, MultilingualGlossaryInfo],
        source_lang: str,
        target_lang: str,
        csv_data: Union[TextIO, BinaryIO, str, bytes, Any],
    ) -> MultilingualGlossaryInfo:
        """Updates or creates a glossary dictionary with given entries in
        CSV formatting for the source and target languages. Either updates
        entries if they exist for the given language pair, or adds new ones
        to the dictionary if not.

        The available glossary language pairs can be queried using
        get_glossary_languages(). Glossaries apply to languages, not specific
        language variants. A glossary for a language applies to any variant
        of that language: a glossary with target language EN may be used to
        translate texts into both EN-US and EN-GB.

        This function allows you to upload a glossary CSV file that you have
        downloaded from the DeepL website.

        Information about the expected CSV format can be found in the API
        documentation: https://www.deepl.com/docs-api/managing-glossaries/supported-glossary-formats/  # noqa

        :param glossary: MultilingualGlossaryInfo or ID of glossary to update.
        :param source_lang: Language of source entries.
        :param target_lang: Language of target entries.
        :param csv_data: CSV data containing glossary entries, either as a
            file-like object or string or bytes containing file content.
        :return: MultilingualGlossaryInfo containing information about updated
            glossary.

        :raises ValueError: If the glossary entries are empty or invalid.
        :raises DeepLException: If source and target language pair are not
            supported for glossaries.
        """
        entries = util.convert_csv_to_dict(csv_data)

        if isinstance(glossary, MultilingualGlossaryInfo):
            glossary = glossary.glossary_id

        dictionaries = [
            MultilingualGlossaryDictionaryEntries(
                source_lang, target_lang, entries
            )
        ]
        return self._update_multilingual_glossary(glossary, dictionaries)

    def _update_multilingual_glossary(
        self,
        glossary_id: str,
        dictionaries: List[MultilingualGlossaryDictionaryEntries],
    ) -> MultilingualGlossaryInfo:
        if not glossary_id:
            raise ValueError("glossary id must not be empty")

        req_glossary_dicts = []
        # glossaries are only supported for base language types
        for glossary_dict in dictionaries:
            req_glossary_dict = {
                "source_lang": Language.remove_regional_variant(
                    glossary_dict.source_lang
                ),
                "target_lang": Language.remove_regional_variant(
                    glossary_dict.target_lang
                ),
                "entries": util.convert_dict_to_tsv(glossary_dict.entries),
                "entries_format": "tsv",
            }
            req_glossary_dicts.append(req_glossary_dict)

        request_data = {}

        if dictionaries:
            request_data["dictionaries"] = req_glossary_dicts

        status, content, json = self._api_call(
            f"v3/glossaries/{glossary_id}", method="PATCH", json=request_data
        )
        self._raise_for_status(status, content, json, glossary=True)

        return MultilingualGlossaryInfo.from_json(json)

    def replace_multilingual_glossary_dictionary(
        self,
        glossary: Union[str, MultilingualGlossaryInfo],
        glossary_dict: MultilingualGlossaryDictionaryEntries,
    ) -> MultilingualGlossaryDictionaryInfo:
        """Replaces a glossary dictionary with given entries for the
        source and target languages.

        The available glossary language pairs can be queried using
        get_glossary_languages(). Glossaries apply to languages, not specific
        language variants. A glossary for a language applies to any variant
        of that language: a glossary with target language EN may be used to
        translate texts into both EN-US and EN-GB.

        This function requires the glossary entries to be provided as a
        dictionary of source-target terms. To create a glossary from a CSV file
        downloaded from the DeepL website, see create_glossary_from_csv().

        :param glossary: GlossaryInfo or ID of glossary to update.
        :param glossary_dict: The new glossary dictionary
        :return: MultilingualGlossaryDictionaryInfo containing information
            about the updated dictionary.

        :raises ValueError: If the glossary entries are empty or invalid.
        :raises DeepLException: If source and target language pair are not
            supported for glossaries.
        """
        if not glossary_dict or not glossary_dict.entries:
            raise ValueError("glossary entries must not be empty")

        if isinstance(glossary, MultilingualGlossaryInfo):
            glossary = glossary.glossary_id

        return self._replace_multilingual_glossary_dictionary(
            glossary,
            glossary_dict.source_lang,
            glossary_dict.target_lang,
            glossary_dict.entries,
        )

    def replace_multilingual_glossary_dictionary_from_csv(
        self,
        glossary: Union[str, MultilingualGlossaryInfo],
        source_lang: str,
        target_lang: str,
        csv_data: Union[TextIO, BinaryIO, str, bytes, Any],
    ) -> MultilingualGlossaryDictionaryInfo:
        """Replaces a glossary dictionary with given CSV formatted entries
        for the source and target languages.

        The available glossary language pairs can be queried using
        get_glossary_languages(). Glossaries apply to languages, not specific
        language variants. A glossary for a language applies to any variant
        of that language: a glossary with target language EN may be used to
        translate texts into both EN-US and EN-GB.

        This function allows you to upload a glossary CSV file that you have
        downloaded from the DeepL website.

        Information about the expected CSV format can be found in the API
        documentation: https://www.deepl.com/docs-api/managing-glossaries/supported-glossary-formats/  # noqa

        :param glossary: MultilingualGlossaryInfo or ID of glossary to update.
        :param source_lang: Language of source entries.
        :param target_lang: Language of target entries.
        :param csv_data: CSV data containing glossary entries, either as a
            file-like object or string or bytes containing file content.
        :return: MultilingualGlossaryDictionaryInfo containing information
            about updated dictionary.

        :raises ValueError: If the glossary entries are empty or invalid.
        :raises DeepLException: If source and target language pair are not
            supported for glossaries.
        """
        entries = util.convert_csv_to_dict(csv_data)

        if isinstance(glossary, MultilingualGlossaryInfo):
            glossary = glossary.glossary_id

        return self._replace_multilingual_glossary_dictionary(
            glossary, source_lang, target_lang, entries
        )

    def _replace_multilingual_glossary_dictionary(
        self,
        glossary_id: str,
        source_lang: str,
        target_lang: str,
        entries: Dict[str, str],
    ) -> MultilingualGlossaryDictionaryInfo:
        if not glossary_id:
            raise ValueError("glossary id must not be empty")

        # glossaries are only supported for base language types
        source_lang = Language.remove_regional_variant(source_lang)
        target_lang = Language.remove_regional_variant(target_lang)

        request_data = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "entries": util.convert_dict_to_tsv(entries),
            "entries_format": "tsv",
        }

        status, content, json = self._api_call(
            f"v3/glossaries/{glossary_id}/dictionaries",
            method="PUT",
            json=request_data,
        )
        self._raise_for_status(status, content, json, glossary=True)
        return MultilingualGlossaryDictionaryInfo.from_json(json)

    def get_multilingual_glossary(
        self, glossary_id: str
    ) -> MultilingualGlossaryInfo:
        """Retrieves MultilingualGlossaryInfo for the glossary with specified
        ID.

        :param glossary_id: ID of glossary to retrieve.
        :return: MultilingualGlossaryInfo with information about specified
            glossary.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        """
        status, content, json = self._api_call(
            f"v3/glossaries/{glossary_id}", method="GET"
        )
        self._raise_for_status(status, content, json, glossary=True)
        return MultilingualGlossaryInfo.from_json(json)

    def list_multilingual_glossaries(self) -> List[MultilingualGlossaryInfo]:
        """Retrieves a list of MultilingualGlossaryInfo for all available
        glossaries.

        :return: list of MultilingualGlossaryInfos for all available
            glossaries.
        """
        status, content, json = self._api_call("v3/glossaries", method="GET")
        self._raise_for_status(status, content, json, glossary=True)
        glossaries = (
            json.get("glossaries", [])
            if (json and isinstance(json, dict))
            else []
        )
        return [
            MultilingualGlossaryInfo.from_json(glossary)
            for glossary in glossaries
        ]

    def get_multilingual_glossary_entries(
        self,
        glossary: Union[str, MultilingualGlossaryInfo],
        source_lang: str,
        target_lang: str,
    ) -> MultilingualGlossaryDictionaryEntriesResponse:
        """Retrieves the entries for a given source and target language in the
        specified glossary.

        :param glossary: MultilingualGlossaryInfo or ID of glossary to
            retrieve.
        :param source_lang: Language of source terms.
        :param target_lang: Language of target terms.
        :return: MultilingualGlossaryDictionaryEntriesResponse object
            containing the entries.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        :raises DeepLException: If the glossary could not be retrieved
            in the right format.
        """
        if isinstance(glossary, MultilingualGlossaryInfo):
            glossary = glossary.glossary_id
        source_lang = Language.remove_regional_variant(source_lang)
        target_lang = Language.remove_regional_variant(target_lang)

        status, content, json = self._api_call(
            f"v3/glossaries/{glossary}/entries?source_lang={source_lang}&target_lang={target_lang}",  # noqa: E501
            method="GET",
        )
        self._raise_for_status(status, content, json, glossary=True)
        return MultilingualGlossaryDictionaryEntriesResponse.from_json(json)

    def delete_multilingual_glossary(
        self, glossary: Union[str, MultilingualGlossaryInfo]
    ) -> None:
        """Deletes specified glossary.

        :param glossary: MultilingualGlossaryInfo or ID of glossary to delete.
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        """
        if isinstance(glossary, MultilingualGlossaryInfo):
            glossary = glossary.glossary_id

        status, content, json = self._api_call(
            f"v3/glossaries/{glossary}",
            method="DELETE",
        )
        self._raise_for_status(status, content, json, glossary=True)

    def delete_multilingual_glossary_dictionary(
        self,
        glossary: Union[str, MultilingualGlossaryInfo],
        dictionary: Optional[MultilingualGlossaryDictionaryInfo] = None,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
    ) -> None:
        """Deletes specified glossary dictionary.

        :param glossary: GlossaryInfo or ID of glossary containing the
            dictionary to delete
        :param dictionary: The dictionary to delete. Either the
            MultilingualGlossaryDictionaryInfo or both the source_lang and
            target_lang can be provided to identify the dictionary. However,
            if both are provided, the dictionary takes precendence over
            source_lang and target_lang.
        :param source_lang: Optional parameter representing the source language
            of the dictionary
        :param target_lang: Optional parameter representing the target language
            of the dictionary
        :raises GlossaryNotFoundException: If no glossary with given ID is
            found.
        :raises ValueError: If the dictionary or both the source_lang and
            target_lang were not provided
        """
        if isinstance(glossary, MultilingualGlossaryInfo):
            glossary = glossary.glossary_id

        if not dictionary and not (source_lang and target_lang):
            raise ValueError(
                "must provide dictionary or both source_lang and target_lang"
            )

        if dictionary:
            source_lang = dictionary.source_lang
            target_lang = dictionary.target_lang

        req_url = f"v3/glossaries/{glossary}/dictionaries?source_lang={source_lang}&target_lang={target_lang}"  # noqa: E501
        status, content, json = self._api_call(
            req_url,
            method="DELETE",
        )
        self._raise_for_status(status, content, json, glossary=True)
