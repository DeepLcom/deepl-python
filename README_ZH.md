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

`translate_document()`和`translate_document_from_filepath()`是两个方便使用的
函数，包含了多个API调用：上传、轮询状态直到翻译完成以及最后的下载。如果你的应用程序需要单独执行
这些步骤，你可以直接使用以下函数。

- `translate_document_upload()`,
- `translate_document_get_status()` (或者`translate_document_wait_until_done()`)
- `translate_document_download()`

#### 文件翻译选项

In addition to the input file, output file, `source_lang` and `target_lang`
arguments, the available `translate_document()` and
`translate_document_from_filepath()` arguments are:
除了输入文件、输出文件、"source_lang "和 "target_lang "参数外,可用的`translate_document()`和 "translate_document_from_filepath() "的参数是。

- `formality`: 与[文本翻译选项](#text-translation-options)中相同。
- `glossary`: 与[文本翻译选项](#text-translation-options)中相同。
### 词汇表

词汇表允许你使用用户定义的术语来定制你的翻译。
您的账户可以存储多个词汇表，每个词汇表都有一个用户指定的名称和唯一分配的ID.

#### 创建一个词汇表

你可以用你想要的术语和名称创建一个词汇表，使用
`create_glossary()`创建一个词汇表。每个词汇表适用于单一的源语言-目标语言
对。注意：词汇表只支持某些语言对，见
[列出可用的词汇表语言](#listing-available-glossary-languages)
获取更多信息。


如果成功，词汇表将被创建并存储在你的DeepL 账户中，并且
返回一个`GlossaryInfo`对象，包括ID、名称、语言和条目数。

```python
# 用两个术语创建一个英语到德语的词汇表。
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
# 这是一个例子。创建了'我的词汇表'（559192ed-8e23-...）EN->DE，包含2个条目
```

#### 获取、列出和删除存储的词汇表

还提供了获取、列出和删除存储的词汇表的功能。

- `get_glossary()` 接受一个词汇表ID，并返回一个`GlossaryInfo'对象，用于存储一个词汇表。
如果没有找到这样的词汇表，则会引发一个异常。
- `list_glossaries()` 返回一个`GlossaryInfo`对象的列表，该列表对应于你所有存储的词汇表。
- `delete_glossary()` 接受一个词汇表ID或`GlossaryInfo`对象并从服务器上删除存储的词汇表，如果没有找到这样的词汇表，则会引发一个异常。


```python
# 使用ID检索一个存储的词汇表
glossary_id = "559192ed-8e23-..."
my_glossary = translator.get_glossary(glossary_id)

# 查找并删除名为 "旧词汇表 "的词汇表
glossaries = translator.list_glossaries()
for glossary in glossaries:
    if glossary.name == "Old glossary":
        translator.delete_glossary(glossary)
```

#### 在存储的词汇表中列出条目 

`GlossaryInfo`对象不包含词汇表条目，而是只包含`entry_count`属性中的条目数量。

要列出一个存储的词汇表所包含的条目，请使用
`get_glossary_entries()`提供`GlossaryInfo`对象或 glossary
ID。

```python
entries = translator.get_glossary_entries(my_glossary)
print(entries)  # "{'artist': 'Maler', 'prize': 'Gewinn'}"
```

#### 使用存储的词汇表

你可以通过设置`glossary`参数来使用存储的词汇表进行文本翻译。
参数设置为词汇表ID或`GlossaryInfo`对象。你还必须
指定`source_lang`参数（当使用词汇表时，它是必须的）。

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

`translate_document()`, `translate_document_from_filepath()` 和
`translate_document_upload()`函数都支持`glossary`参数。
### 支票账户的使用

要检查账户使用情况，请使用`get_usage()`函数。

返回的 "使用 "对象包含三个使用子类型。`character`,
`document` and `team_document`.根据你的账户类型，一些用法
可能是无效的；对于API
帐户，可以通过`valid`属性来检查。

- `usage.character.valid` is `True`,
- `usage.document.valid` and `usage.team_document.valid` are `False`.

每个使用类型（如果有效）都有`count`和`limit`属性，分别给出使用量和最大使用量。
以及`limit_reached'属性，检查使用量是否达到限制。顶层的`Usage`对象有
`any_limit_reached'属性来检查所有使用量的子类型。


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

### 列出可用的语言

你可以使用`get_source_languages()`和`get_target_languages()`函数请求DeepL 支持的文本和文档语言列表。
使用`get_source_languages()`和`get_target_languages()`函数。它们
它们都返回一个 "语言 "对象的列表。

The `name` property gives the name of the language in English, and the `code`
property gives the language code. The `supports_formality` property only appears
for target languages, and indicates whether the target language supports the
optional `formality` parameter.
`name`属性给出了语言的英文名称，`code`属性给出了语言代码。
`supports_formality`属性只出现在目标语言中，并指示目标语言是否支持可选的`formality`参数。

```python
print("Source languages:")
for language in translator.get_source_languages():
    print(f"{language.name} ({language.code})")  # Example: "German (DE)"

print("Target languages:")
for language in translator.get_target_languages():
    if language.supports_formality:
        print(f"{language.name} ({language.code}) supports formality")
        # 例子："意大利语（IT）支持正式性"
    else:
        print(f"{language.name} ({language.code})")
        # 例子："立陶宛语（LT）"
```

#### 列出可用的词汇表语言

词汇表支持一个语言对的子集。要检索这些
使用`get_glossary_languages()`函数，该函数返回一个`GlossaryLanguagePair`对象的数组。
每个对象都有`source_lang'和`target_lang'属性，表示支持这对语言。

```python
glossary_languages = translator.get_glossary_languages()
for language_pair in glossary_languages:
    print(f"{language_pair.source_lang} to {language_pair.target_lang}")
    # Example: "EN to DE", "DE to EN", etc.
```

你也可以在以下文件中找到支持的词汇表语言对的列表
[API文档][api-docs-lossary-lang-list]。

请注意，词汇表适用于所有的目标区域变体：一个目标语言英语的词汇表
目标语言英语("EN")的词汇表支持翻译成美国英语("EN-US")和英国英语("EN-GB")。
### 例外情况

All module functions may raise `deepl.DeepLException` or one of its subclasses.
If invalid arguments are provided, they may raise the standard exceptions
`ValueError` and `TypeError`.
所有的模块函数都可能引发`deepl.DeepLException`或其子类之一。
如果提供了无效的参数，它们可能引发标准的异常:
`ValueError'`和`TypeError'`。
### 配置

#### 日志

Logging can be enabled to see the HTTP requests sent and responses received by
the library. Enable and control logging using Python's `logging` module, for
example:

可以启用日志记录功能，以查看HTTP请求的发送和库的接收情况。使用Python的`logging`模块来启用和控制日志记录，例如：

```python
import logging

logging.basicConfig()
logging.getLogger('deepl').setLevel(logging.DEBUG)
```

#### 服务器URL配置


你可以通过在构建 `"deepl.Translator"`时指定 `"server_url"`参数来覆盖DeepL API的URL。
参数来重写 API的URL，这在构建` "deepl.Translator "`时非常有用。这可能对测试
的目的。你**不需要**指定URL来区分API免费和API专业账户，库会自动选择正确的URL。

```python
server_url = "http://user:pass@localhost:3000"
translator = deepl.Translator(..., server_url=server_url)
```

#### 代理配置

你可以通过在构建 "deepl.Translator "时指定 "proxy "参数。

```python
proxy = "http://user:pass@10.10.1.10:3128"
translator = deepl.Translator(..., proxy=proxy)
```

The proxy argument is passed to the underlying `requests` session, see the
[documentation for requests][requests-proxy-docs]; a dictionary of schemes to
proxy URLs is also accepted.

代理参数被传递给底层的`requests`会话，见
[requests的文档][requests-proxy-docs]；

## 命令行界面

该库可以在支持所有API功能的命令行上运行。使用
`--help`选项获取使用信息。

```shell
python3 -m deepl --help
```
CLI需要你的DeepL 认证密钥，指定为
`DEEPL_AUTH_KEY`环境变量，或使用`--auth-key`选项，例如:

```shell
python3 -m deepl --auth-key=YOUR_AUTH_KEY usage
```

Note that the `--auth-key` argument must appear *before* the command argument.
请注意，`--auth-key` 参数必须出现在 **命令参数之前**。
识别的命令有：

| 命令      | 描述                                            |
| :-------- | :----------------------------------------------------- |
| text      | 译文                                      |
| document  | 翻译文件                                  |
| usage     | 打印当前计费期的使用信息 |
| languages | 打印可用的语言                              |
| glossary  | 创建、列出和删除词汇表                    |

例如，要翻译文本。

```shell
python3 -m deepl --auth-key=YOUR_AUTH_KEY text --to=DE "Text to be translated."
```

将文本参数用引号括起来，以防止 shell 将句子拆分成字。

## 问题

如果您在使用库时遇到问题，或者想申请新的
功能，请打开一个[issue][issues].

## 发展

我们欢迎Pull Request，请阅读
[贡献指南](CONTRIBUTING.md)。

### 测试

使用 `pytest` 执行测试。 测试使用 DeepL API 进行通信
由 `DEEPL_AUTH_KEY` 环境变量定义的身份验证密钥。

请注意，测试会发出有助于您的 API 的 DeepL API 请求
用法。

测试套件可以被配置为与[deepl-mock][deepl-mock]提供的模拟服务器通信。虽然大多数测试用例对两者都适用，但有些测试用例只适用于DeepL API或模拟服务器，否则将被跳过。需要模拟服务器的测试用例会触发服务器错误并测试客户端错误处理。要使用deepl-mock执行测试，在执行测试的同时在另一个终端运行它。使用`pytest`执行测试，定义`DEEPL_MOCK_SERVER_PORT`和`DEEPL_SERVER_URL`环境变量，参考模拟服务器。

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
