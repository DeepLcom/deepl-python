# DeepL Python 数据库

[![PyPI version](https://img.shields.io/pypi/v/deepl.svg)](https://pypi.org/project/deepl/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/deepl.svg)](https://pypi.org/project/deepl/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blueviolet.svg)](https://github.com/DeepLcom/deepl-python/blob/main/LICENSE)

 [DeepL API][api-docs]是一个语言翻译API，允许其他计算机程序向DeepL的服务器发送文本和文件并接收高质量的翻译。这为开发者创造了大量的开发机会
任何你能想象的翻译产品现在都可以建立在DeepL的同类最佳翻译技术之上。

DeepL Python库为用Python编写的应用程序提供了一种更加方便的方式，使其能够与DeepL API交互。
我们用各种库来支持所有的 API 功能
对新功能的支持会首先上线API，然后再添加到相对应的库中

## 获取认证密钥

为了使用DeepL的Python库，你需要获取一个API密钥. 为了获取密钥, [请在这创建账户][create-account]. 使用DeepL API免费账户，你可以免费翻译多达50万个字符/月。

## 安装

DeepL 的 Python库 可以通过 [PyPI][pypi-project] 使用 pip 进行安装:

```shell
pip install --upgrade deepl
```


如果你需要修改源代码，请用 poetry 安装所有依赖项。

```shell
poetry install
```

### 依赖项

该库在Python 3.6到3.10版本下进行了测试。

`requests` 模块用于执行 HTTP 需求; 最低版本限制为2.0.
## 使用方法

导入软件包并构建一个 `Translator`. 第一个参数是一个字符串包含有你在
[DeepL Pro Account][pro-account]中所得到的API认证密钥。

当你在分享源码时，请一定注意不要将你的密钥一并导出，可能会发生泄露。

```python
import deepl

auth_key = "f63c02c5-f056-..."  # 用你的密钥进行替换
translator = deepl.Translator(auth_key)

result = translator.translate_text("Hello, world!", target_lang="FR")
print(result.text)  # "将hello，world翻译为法语：Bonjour, le monde !"
```

这个例子仅用于示范目的。在编写代码中，认证密钥不应该为硬编码，而应该从一个
配置文件或环境变量中获取。

`Translator` 接受另外的配置, 详见 [配置](#configuration)

### 翻译文本

要翻译文本，请调用 `translate_text()`。第一个参数是一个包含你想翻译的文本的字符串
，如果你想翻译多个文本，也可以将参数更改为一个字符串列表，

`source_lang` 和 `target_lang` 分别指定源语言和目标语言. 
`source_lang`（源语言）是可选的, 如果它没有被指定，源语言将被自动检测。

根据ISO 639-1，语言代码是**不区分大小写的**字符串，例如"DE"，"FR"，"JA"。
根据ISO 3166-1，一些目标语言还包括区域性的变体，例如`'EN-US'`或`'PT-BR'`。支持的语言的完整列表在
[API文档][api-docs-lang-list] 。

还有一些额外的可选参数来控制翻译软件，详见
[文本翻译选项](#text-translation-options)。

`translate_text()`返回一个`TextResult`的列表，或一个`TextResult`的列表。
对应于你的输入文本。`TextResult'`有两个属性。`text`是
翻译后的文本，`detected_source_lang`是检测到的源语言代码。

```python
# 将文本翻译成目标语言，本例中为法语:
result = translator.translate_text("Hello, world!", target_lang="FR")
print(result.text)  # "Bonjour, le monde !"

# 将多个文本翻译成英式英语
result = translator.translate_text(
    ["お元気ですか？", "¿Cómo estás?"], target_lang="EN-GB"
)
print(result[0].text)  # "How are you?"
print(result[0].detected_source_lang)  # "JA" 为日语的缩写
print(result[1].text)  # "How are you?"
print(result[1].detected_source_lang)  # "ES" 为西班牙语的缩写

# 下面的例子中，语言将会被翻译成少而精的德语。
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

#### 文本翻译选项

除了输入文本参数外，可用的 `translate_text()` 参数有：

- `source_lang`: 指定源语言代码，但可以省略，因为DeepL可以自动检测源语言。
- `target_lang`: 指定目标语言代码（必须）。
- `split_sentences`: 指定输入的文本应如何分割成句。
  默认: `'on'`.
    - `'on''` (`SplitSentences.ON`): 输入的文本将使用换行符和标点符号被分割成几个句子。
    - `'off'` (`SplitSentences.OFF`): 输入的文本将不会被分割成句子。请在只包含一个句子的文本中使用该选项。
    - `'nonewlines'` (`SplitSentences.NO_NEWLINES`): （没有换行符）输入的文本将用标点符号被分割成句子，但不会使用换行符来分割为句子
- `preserve_formatting`: 控制自动格式校正。设置为 "True "是为了防止自动更正格式.默认为`False`。
- `formality`: 控制翻译是否应该偏向于非正式或
  正式语言。这个选项只适用于某些目标语言，详见
  [列出可用语言](#listing-available-languages)。
    - `'less'` (`Formality.LESS`): 使用非正式的语言。
    - `'more'` (`Formality.MORE`): 使用正式的、更有礼貌的语言。
- `glossary`: 指定一个用于翻译的词汇表，可以是一个包含词汇表ID的字符串
  或由`get_glossary()`返回的`GlossaryInfo`词汇表。
- `tag_handling`: 翻译前要解析的标签类型，选项是`'html'`和`'xml'`。

以下选项只在`tag_handling'`为`'xml'`时使用。

- `outline_detection`: 指定 "False "来禁用自动标签检测。
  默认为 `"True"`。
- `splitting_tags`: 
  XML标签列表，这些标签应被用来将文本分割成句子。标签可以被指定为一个字符串数组（`['tag1', 'tag2']`）。或以逗号分隔的字符串列表（`'tag1,tag2'`）。默认是一个空列表。
- `non_splitting_tags`: XML标签列表，这些标签不应该被用来将文本分割成句子。格式和默认值与`splitting_tags`相同。
- `ignore_tags`: 包含不应该被翻译的内容的XML标签的列表。格式和默认值与`splitting_tags`相同。

关于XML处理选项的详细解释，见
[API 文档][api-docs-xml-handling]。

### 翻译文件

要翻译文件，你可以调用`translate_document()`使用文件对象，或者使用文件路径调用 `translate_document_from_filepath()`。对于这两个
函数，第一个和第二个参数分别对应于输入和输出的文件。

就像`translate_text()`函数一样，通过`source_lang`和`target_lang`参数指定源语言和目标语言代码。

还有一些额外的可选参数来控制翻译，参见
[文档翻译选项](#document-translation-options)。

```python
# 将一份正式文件从英文翻译成德文
input_path = "/path/to/Instruction Manual.docx"
output_path = "/path/to/Bedienungsanleitung.docx"
try:
    # 使用带有文件路径的 translate_document_from_filepath()。
    translator.translate_document_from_filepath(
        input_path,
        output_path,
        target_lang="DE",
        formality="more"
    )

    # 另外，你可以使用translate_document()与文件IO对象一起使用
    with open(input_path, "rb") as in_file, open(output_path, "wb") as out_file:
        translator.translate_document(
            in_file,
            out_file,
            target_lang="DE",
            formality="more"
        )

except deepl.DocumentTranslationException as error:
    # 如果在文档翻译过程中发生错误，而该文档已经被
    # 已经上传，就会产生一个DocumentTranslationException异常
    # document_handle 属性包含了文档的句柄，可以用来
    # 以后从服务器上检索文档，或联系 DeepL 。
    doc_id = error.document_handle.id
    doc_key = error.document_handle.key
    print(f"Error after uploading ${error}, id: ${doc_id} key: ${doc_key}")
except deepl.DeepLException as error:
    # 上传过程中的错误会引发一个DeepLException
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
(`"EN-US"`) and British English (`"EN-GB""`).

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

[api-docs-xml-handling]: https://www.deepl.com/docs-api/handling-xml/?utm_source=github&utm_medium=github-python-readme

[api-docs-lang-list]: https://www.deepl.com/docs-api/translating-text/?utm_source=github&utm_medium=github-python-readme

[api-docs-glossary-lang-list]: https://www.deepl.com/docs-api/managing-glossaries/?utm_source=github&utm_medium=github-python-readme

[create-account]: https://www.deepl.com/pro?utm_source=github&utm_medium=github-python-readme#developer

[deepl-mock]: https://www.github.com/DeepLcom/deepl-mock

[issues]: https://www.github.com/DeepLcom/deepl-python/issues

[pypi-project]: https://pypi.org/project/deepl/

[pro-account]: https://www.deepl.com/pro-account/?utm_source=github&utm_medium=github-python-readme

[requests-proxy-docs]: https://docs.python-requests.org/en/latest/user/advanced/#proxies
