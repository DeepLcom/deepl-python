# DeepL Python Library

[![PyPI version](https://img.shields.io/pypi/v/deepl.svg)](https://pypi.org/project/deepl/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/deepl.svg)](https://pypi.org/project/deepl/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blueviolet.svg)](https://github.com/DeepLcom/deepl-python/blob/main/LICENSE)

The [DeepL API][api-docs] is a language translation API that allows other
computer programs to send texts and documents to DeepL's servers and receive
high-quality translations. This opens a whole universe of opportunities for
developers: any translation product you can imagine can now be built on top of
DeepL's best-in-class translation technology.

The DeepL Python library offers a convenient way for applications written in
Python to interact with the DeepL API. We intend to support all API functions
with the library, though support for new features may be added to the library
after they’re added to the API.

## Getting an authentication key

To use the DeepL Python Library, you'll need an API authentication key. To get a
key, [please create an account here][create-account]. With a DeepL API Free
account you can translate up to 500,000 characters/month for free.

## Installation

The library can be installed from [PyPI][pypi-project] using pip:

```shell
pip install --upgrade deepl
```

If you need to modify this source code, install the dependencies using poetry:

```shell
poetry install
```

On Ubuntu 22.04 an error might occur: `ModuleNotFoundError: No module named 
'cachecontrol'`. Use the workaround `sudo apt install python3-cachecontrol` as
explained in this [bug report][bug-report-ubuntu-2204].

### Requirements

The library is tested with Python versions 3.6 to 3.10.

The `requests` module is used to perform HTTP requests; the minimum is version
2.0.

## Usage

Import the package and construct a `Translator`. The first argument is a string
containing your API authentication key as found in your
[DeepL Pro Account][pro-account].

Be careful not to expose your key, for example when sharing source code.

```python
import deepl

auth_key = "f63c02c5-f056-..."  # Replace with your key
translator = deepl.Translator(auth_key)

result = translator.translate_text("Hello, world!", target_lang="FR")
print(result.text)  # "Bonjour, le monde !"
```

This example is for demonstration purposes only. In production code, the
authentication key should not be hard-coded, but instead fetched from a
configuration file or environment variable.

`Translator` accepts additional options, see [Configuration](#configuration)
for more information.

### Translating text

To translate text, call `translate_text()`. The first argument is a string
containing the text you want to translate, or a list of strings if you want to
translate multiple texts.

`source_lang` and `target_lang` specify the source and target language codes
respectively. The `source_lang` is optional, if it is unspecified the source
language will be auto-detected.

Language codes are **case-insensitive** strings according to ISO 639-1, for
example `'DE'`, `'FR'`, `'JA''`. Some target languages also include the regional
variant according to ISO 3166-1, for example `'EN-US'`, or `'PT-BR'`. The full
list of supported languages is in the
[API documentation][api-docs-lang-list].

There are additional optional arguments to control translation, see
[Text translation options](#text-translation-options) below.

`translate_text()` returns a `TextResult`, or a list of `TextResult`s
corresponding to your input text(s). `TextResult` has two properties: `text` is
the translated text, and `detected_source_lang` is the detected source language
code.

```python
# Translate text into a target language, in this case, French:
result = translator.translate_text("Hello, world!", target_lang="FR")
print(result.text)  # "Bonjour, le monde !"

# Translate multiple texts into British English
result = translator.translate_text(
    ["お元気ですか？", "¿Cómo estás?"], target_lang="EN-GB"
)
print(result[0].text)  # "How are you?"
print(result[0].detected_source_lang)  # "JA" the language code for Japanese
print(result[1].text)  # "How are you?"
print(result[1].detected_source_lang)  # "ES" the language code for Spanish

# Translate into German with less and more Formality:
print(
    translator.translate_text(
        "How are you?", target_lang="DE", formality="less"
    )
)  # 'Wie geht es dir?'
print(
    translator.translate_text(
        "How are you?", target_lang="DE", formality="more"
    )
)  # 'Wie geht es Ihnen?'
```

#### Text translation options

In addition to the input text(s) argument, the available `translate_text()`
arguments are:

- `source_lang`: Specifies the source language code, but may be omitted to
  auto-detect the source language.
- `target_lang`: Required. Specifies the target language code.
- `split_sentences`: specify how input text should be split into sentences,
  default: `'on'`.
    - `'on''` (`SplitSentences.ON`): input text will be split into sentences
      using both newlines and punctuation.
    - `'off'` (`SplitSentences.OFF`): input text will not be split into
      sentences. Use this for applications where each input text contains only
      one sentence.
    - `'nonewlines'` (`SplitSentences.NO_NEWLINES`): input text will be split
      into sentences using punctuation but not newlines.
- `preserve_formatting`: controls automatic-formatting-correction. Set to `True`
  to prevent automatic-correction of formatting, default: `False`.
- `formality`: controls whether translations should lean toward informal or
  formal language. This option is only available for some target languages, see
  [Listing available languages](#listing-available-languages).
    - `'less'` (`Formality.LESS`): use informal language.
    - `'more'` (`Formality.MORE`): use formal, more polite language.
- `glossary`: specifies a glossary to use with translation, either as a string
  containing the glossary ID, or a `GlossaryInfo` as returned by
  `get_glossary()`.
- `tag_handling`: type of tags to parse before translation, options are `'html'`
  and `'xml'`.

The following options are only used if `tag_handling` is `'xml'`:

- `outline_detection`: specify `False` to disable automatic tag detection,
  default is `True`.
- `splitting_tags`: list of XML tags that should be used to split text into
  sentences. Tags may be specified as an array of strings (`['tag1', 'tag2']`),
  or a comma-separated list of strings (`'tag1,tag2'`). The default is an empty
  list.
- `non_splitting_tags`: list of XML tags that should not be used to split text
  into sentences. Format and default are the same as for `splitting_tags`.
- `ignore_tags`: list of XML tags that containing content that should not be
  translated. Format and default are the same as for `splitting_tags`.

For a detailed explanation of the XML handling options, see the
[API documentation][api-docs-xml-handling].

### Translating documents

To translate documents, you may call either `translate_document()` using file IO
objects, or `translate_document_from_filepath()` using file paths. For both
functions, the first and second arguments correspond to the input and output
files respectively.

Just as for the `translate_text()` function, the `source_lang` and
`target_lang` arguments specify the source and target language codes.

There are additional optional arguments to control translation, see
[Document translation options](#document-translation-options) below.

```python
# Translate a formal document from English to German
input_path = "/path/to/Instruction Manual.docx"
output_path = "/path/to/Bedienungsanleitung.docx"
try:
    # Using translate_document_from_filepath() with file paths 
    translator.translate_document_from_filepath(
        input_path,
        output_path,
        target_lang="DE",
        formality="more"
    )

    # Alternatively you can use translate_document() with file IO objects
    with open(input_path, "rb") as in_file, open(output_path, "wb") as out_file:
        translator.translate_document(
            in_file,
            out_file,
            target_lang="DE",
            formality="more"
        )

except deepl.DocumentTranslationException as error:
    # If an error occurs during document translation after the document was
    # already uploaded, a DocumentTranslationException is raised. The
    # document_handle property contains the document handle that may be used to
    # later retrieve the document from the server, or contact DeepL support.
    doc_id = error.document_handle.id
    doc_key = error.document_handle.key
    print(f"Error after uploading ${error}, id: ${doc_id} key: ${doc_key}")
except deepl.DeepLException as error:
    # Errors during upload raise a DeepLException
    print(error)
```

`translate_document()` and `translate_document_from_filepath()` are convenience
functions that wrap multiple API calls: uploading, polling status until the
translation is complete, and downloading. If your application needs to execute
these steps individually, you can instead use the following functions directly:

- `translate_document_upload()`,
- `translate_document_get_status()` (or
  `translate_document_wait_until_done()`), and
- `translate_document_download()`

#### Document translation options

In addition to the input file, output file, `source_lang` and `target_lang`
arguments, the available `translate_document()` and
`translate_document_from_filepath()` arguments are:

- `formality`: same as in [Text translation options](#text-translation-options).
- `glossary`: same as in [Text translation options](#text-translation-options).

### Glossaries

Glossaries allow you to customize your translations using user-defined terms.
Multiple glossaries can be stored with your account, each with a user-specified
name and a uniquely-assigned ID.

#### Creating a glossary

You can create a glossary with your desired terms and name using
`create_glossary()`. Each glossary applies to a single source-target language
pair. Note: Glossaries are only supported for some language pairs, see
[Listing available glossary languages](#listing-available-glossary-languages)
for more information. The entries should be specified as a dictionary.

If successful, the glossary is created and stored with your DeepL account, and
a `GlossaryInfo` object is returned including the ID, name, languages and entry
count.

```python
# Create an English to German glossary with two terms:
entries = {"artist": "Maler", "prize": "Gewinn"}
my_glossary = translator.create_glossary(
    "My glossary",
    source_lang="EN",
    target_lang="DE",
    entries=entries,
)
print(
    f"Created '{my_glossary.name}' ({my_glossary.glossary_id}) "
    f"{my_glossary.source_lang}->{my_glossary.target_lang} "
    f"containing {my_glossary.entry_count} entries"
)
# Example: Created 'My glossary' (559192ed-8e23-...) EN->DE containing 2 entries
```

You can also upload a glossary downloaded from the DeepL website using
`create_glossary_from_csv()`. Instead of supplying the entries as a dictionary,
specify the CSV data as `csv_data` either as a file-like object or string or
bytes containing file content:

```python
# Open the CSV file assuming UTF-8 encoding. If your file contains a BOM,
# consider using encoding='utf-8-sig' instead.
with open('/path/to/glossary_file.csv', 'r',  encoding='utf-8') as csv_file:
    csv_data = csv_file.read()  # Read the file contents as a string
    my_csv_glossary = translator.create_glossary_from_csv(
        "CSV glossary",
        source_lang="EN",
        target_lang="DE",
        csv_data=csv_data,
    )
```

The [API documentation][api-docs-csv-format] explains the expected CSV format in
detail.

#### Getting, listing and deleting stored glossaries

Functions to get, list, and delete stored glossaries are also provided:

- `get_glossary()` takes a glossary ID and returns a `GlossaryInfo` object for a
  stored glossary, or raises an exception if no such glossary is found.
- `list_glossaries()` returns a list of `GlossaryInfo` objects corresponding to
  all of your stored glossaries.
- `delete_glossary()` takes a glossary ID or `GlossaryInfo` object and deletes
  the stored glossary from the server, or raises an exception if no such
  glossary is found.

```python
# Retrieve a stored glossary using the ID
glossary_id = "559192ed-8e23-..."
my_glossary = translator.get_glossary(glossary_id)

# Find and delete glossaries named 'Old glossary'
glossaries = translator.list_glossaries()
for glossary in glossaries:
    if glossary.name == "Old glossary":
        translator.delete_glossary(glossary)
```

#### Listing entries in a stored glossary

The `GlossaryInfo` object does not contain the glossary entries, but instead
only the number of entries in the `entry_count` property.

To list the entries contained within a stored glossary, use
`get_glossary_entries()` providing either the `GlossaryInfo` object or glossary
ID:

```python
entries = translator.get_glossary_entries(my_glossary)
print(entries)  # "{'artist': 'Maler', 'prize': 'Gewinn'}"
```

#### Using a stored glossary

You can use a stored glossary for text translation by setting the `glossary`
argument to either the glossary ID or `GlossaryInfo` object. You must also
specify the `source_lang` argument (it is required when using a glossary):

```python
text = "The artist was awarded a prize."
with_glossary = translator.translate_text(
    text, source_lang="EN", target_lang="DE", glossary=my_glossary,
)
print(with_glossary)  # "Der Maler wurde mit einem Gewinn ausgezeichnet."

# For comparison, the result without a glossary:
without_glossary = translator.translate_text(text, target_lang="DE")
print(without_glossary)  # "Der Künstler wurde mit einem Preis ausgezeichnet."
```

Using a stored glossary for document translation is the same: set the `glossary`
argument and specify the `source_lang` argument:

```python
translator.translate_document(
    in_file, out_file, source_lang="EN", target_lang="DE", glossary=my_glossary,
)
```

The `translate_document()`, `translate_document_from_filepath()` and
`translate_document_upload()` functions all support the `glossary` argument.

### Checking account usage

To check account usage, use the `get_usage()` function.

The returned `Usage` object contains three usage subtypes: `character`,
`document` and `team_document`. Depending on your account type, some usage
subtypes may be invalid; this can be checked using the `valid` property. For API
accounts:

- `usage.character.valid` is `True`,
- `usage.document.valid` and `usage.team_document.valid` are `False`.

Each usage subtype (if valid) has `count` and `limit` properties giving the
amount used and maximum amount respectively, and the `limit_reached` property
that checks if the usage has reached the limit. The top level `Usage` object has
the `any_limit_reached` property to check all usage subtypes.

```python
usage = translator.get_usage()
if usage.any_limit_reached:
    print('Translation limit reached.')
if usage.character.valid:
    print(
        f"Character usage: {usage.character.count} of {usage.character.limit}")
if usage.document.valid:
    print(f"Document usage: {usage.document.count} of {usage.document.limit}")
```

### Listing available languages

You can request the list of languages supported by DeepL for text and documents
using the `get_source_languages()` and `get_target_languages()` functions. They
both return a list of `Language` objects.

The `name` property gives the name of the language in English, and the `code`
property gives the language code. The `supports_formality` property only appears
for target languages, and indicates whether the target language supports the
optional `formality` parameter.

```python
print("Source languages:")
for language in translator.get_source_languages():
    print(f"{language.name} ({language.code})")  # Example: "German (DE)"

print("Target languages:")
for language in translator.get_target_languages():
    if language.supports_formality:
        print(f"{language.name} ({language.code}) supports formality")
        # Example: "Italian (IT) supports formality"
    else:
        print(f"{language.name} ({language.code})")
        # Example: "Lithuanian (LT)"
```

#### Listing available glossary languages

Glossaries are supported for a subset of language pairs. To retrieve those
languages use the `get_glossary_languages()` function, which returns an array
of `GlossaryLanguagePair` objects. Each has `source_lang` and `target_lang`
properties indicating that that pair of language codes is supported.

```python
glossary_languages = translator.get_glossary_languages()
for language_pair in glossary_languages:
    print(f"{language_pair.source_lang} to {language_pair.target_lang}")
    # Example: "EN to DE", "DE to EN", etc.
```

You can also find the list of supported glossary language pairs in the
[API documentation][api-docs-glossary-lang-list].

Note that glossaries work for all target regional-variants: a glossary for the
target language English (`"EN"`) supports translations to both American English
(`"EN-US"`) and British English (`"EN-GB"`).

### Exceptions

All module functions may raise `deepl.DeepLException` or one of its subclasses.
If invalid arguments are provided, they may raise the standard exceptions
`ValueError` and `TypeError`.

### Configuration

#### Logging

Logging can be enabled to see the HTTP requests sent and responses received by
the library. Enable and control logging using Python's `logging` module, for
example:

```python
import logging

logging.basicConfig()
logging.getLogger('deepl').setLevel(logging.DEBUG)
```

#### Server URL configuration

You can override the URL of the DeepL API by specifying the `server_url`
argument when constructing a `deepl.Translator`. This may be useful for testing
purposes. You **do not** need to specify the URL to distinguish API Free and API
Pro accounts, the library selects the correct URL automatically.

```python
server_url = "http://user:pass@localhost:3000"
translator = deepl.Translator(..., server_url=server_url)
```

#### Proxy configuration

You can configure a proxy by specifying the `proxy` argument when constructing a
`deepl.Translator`:

```python
proxy = "http://user:pass@10.10.1.10:3128"
translator = deepl.Translator(..., proxy=proxy)
```

The proxy argument is passed to the underlying `requests` session, see the
[documentation for requests][requests-proxy-docs]; a dictionary of schemes to
proxy URLs is also accepted.

## Command Line Interface

The library can be run on the command line supporting all API functions. Use the
`--help` option for usage information:

```shell
python3 -m deepl --help
```

The CLI requires your DeepL authentication key specified either as the
`DEEPL_AUTH_KEY` environment variable, or using the `--auth-key` option, for
example:

```shell
python3 -m deepl --auth-key=YOUR_AUTH_KEY usage
```

Note that the `--auth-key` argument must appear *before* the command argument.
The recognized commands are:

| Command   | Description                                            |
| :-------- | :----------------------------------------------------- |
| text      | translate text(s)                                      |
| document  | translate document(s)                                  |
| usage     | print usage information for the current billing period |
| languages | print available languages                              |
| glossary  | create, list, and remove glossaries                    |

For example, to translate text:

```shell
python3 -m deepl --auth-key=YOUR_AUTH_KEY text --to=DE "Text to be translated."
```

Wrap text arguments in quotes to prevent the shell from splitting sentences into
words.

## Issues

If you experience problems using the library, or would like to request a new
feature, please open an [issue][issues].

## Development

We welcome Pull Requests, please read the
[contributing guidelines](CONTRIBUTING.md).

### Tests

Execute the tests using `pytest`. The tests communicate with the DeepL API using
the auth key defined by the `DEEPL_AUTH_KEY` environment variable.

Be aware that the tests make DeepL API requests that contribute toward your API
usage.

The test suite may instead be configured to communicate with the mock-server
provided by [deepl-mock][deepl-mock]. Although most test cases work for either,
some test cases work only with the DeepL API or the mock-server and will be
otherwise skipped. The test cases that require the mock-server trigger server
errors and test the client error-handling. To execute the tests using
deepl-mock, run it in another terminal while executing the tests. Execute the
tests using `pytest` with the `DEEPL_MOCK_SERVER_PORT` and `DEEPL_SERVER_URL`
environment variables defined referring to the mock-server.

[api-docs]: https://www.deepl.com/docs-api?utm_source=github&utm_medium=github-python-readme

[api-docs-csv-format]: https://www.deepl.com/docs-api/managing-glossaries/supported-glossary-formats/?utm_source=github&utm_medium=github-python-readme

[api-docs-xml-handling]: https://www.deepl.com/docs-api/handling-xml/?utm_source=github&utm_medium=github-python-readme

[api-docs-lang-list]: https://www.deepl.com/docs-api/translating-text/?utm_source=github&utm_medium=github-python-readme

[api-docs-glossary-lang-list]: https://www.deepl.com/docs-api/managing-glossaries/?utm_source=github&utm_medium=github-python-readme

[bug-report-ubuntu-2204]: https://bugs.launchpad.net/ubuntu/+source/poetry/+bug/1958227

[create-account]: https://www.deepl.com/pro?utm_source=github&utm_medium=github-python-readme#developer

[deepl-mock]: https://www.github.com/DeepLcom/deepl-mock

[issues]: https://www.github.com/DeepLcom/deepl-python/issues

[pypi-project]: https://pypi.org/project/deepl/

[pro-account]: https://www.deepl.com/pro-account/?utm_source=github&utm_medium=github-python-readme

[requests-proxy-docs]: https://docs.python-requests.org/en/latest/user/advanced/#proxies
