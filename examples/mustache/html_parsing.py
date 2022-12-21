# Copyright 2023 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from html.parser import HTMLParser
import html
from typing import List, Tuple, Dict


class PassthroughHTMLParser(HTMLParser):
    """
    An HTML parser that accumulates parsed HTML in the original HTML.
    The original HTML can be accessed using parsed().

    Note: some HTML features are not correctly handled and reproduced: entity
    references, character references, declarations, processing instructions.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._result = ""

    def parsed(self):
        return self._result

    def _append(self, text):
        self._result += text

    def handle_startendtag(self, tag, attrs):
        self._append(f"<{tag}{self._encode_attrs(attrs)} />")

    def handle_starttag(self, tag, attrs):
        self._append(f"<{tag}{self._encode_attrs(attrs)}>")

    def handle_endtag(self, tag):
        self._append(f"</{tag}>")

    def handle_charref(self, name):
        self._append(f"&#{name};")

    def handle_entityref(self, name):
        self._append(f"&{name};")

    def handle_data(self, data):
        self._append(data)

    def handle_comment(self, data):
        self._append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self._append(f"<!{decl}>")

    def handle_pi(self, data):
        self._append(f"<?{data}>")

    @staticmethod
    def _encode_attrs(attrs: List[Tuple[str, str]]) -> str:
        if attrs:
            return " " + " ".join(
                f'{key}="{html.escape(value)}"' for key, value in attrs
            )
        else:
            return ""


class TagReplacerHTMLParser(PassthroughHTMLParser):
    """
    An HTML parser that accumulates parsed HTML unmodified, except that
    matching start-end tags are replaced by prepared content.

    :param replace_tags: A dictionary of tags to replace, with keys matching
        tag names ("tag") or tag names with IDs ("tag#id"), and values the text
        to replace matching tags with.
    """

    def __init__(self, replace_tags: Dict[str, str]):
        super().__init__()
        self._replace_tags = replace_tags

    def handle_startendtag(self, tag, attrs):
        if self._replace_tag_if_matching(tag):
            return

        id = next((value for key, value in attrs if key == "id"), None)
        if id is not None and self._replace_tag_if_matching(f"{tag}#{id}"):
            return

        # If no replacement is found, fall back to passthrough parser
        super().handle_starttag(tag, attrs)

    def _replace_tag_if_matching(self, tag_and_id):
        if tag_and_id in self._replace_tags:
            stored_tag = self._replace_tags[tag_and_id]
            self._append(stored_tag)
            return True
        return False
