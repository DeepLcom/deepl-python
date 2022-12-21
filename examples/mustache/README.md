# Example: Translation of Mustache templates

An example showing how to translate [Mustache templates][mustache-docs] using
XML tag-handling. Mustache templates embed tags in literal text and HTML tags;
the tags refer to keys in hashes, so they should not be translated.

For example:

```
Hello {{name}}. You have just won <b>{{value}} dollars</b>!
```

could be translated into German as:

```
Hallo {{name}}. Sie haben gerade <b>{{value}} Dollar</b> gewonnen!
```

## Usage

Install the [`deepl` Python library](../../README.md).

Define your DeepL auth key as an environment variable `DEEPL_AUTH_KEY`.

```
export DEEPL_AUTH_KEY=f63c02c5-f056-...
```

Run the Mustache translator by running Python on this directory:

```
python examples/mustache --to de "Hello {{name}}"
```

For an explanation of the command line arguments, provide the `--help` option:

```
python examples/mustache --help
```

## How it works

This Mustache translator uses XML tag-handling to preserve the Mustache tags 
while using the DeepL API to translate. It also handles HTML tags embedded in
the Mustache template.

1. The input Mustache template is parsed to separate the literal text from the
   Mustache tags.
   ```
   Hello {{name}}. You have just won <b>{{value}} dollars</b>!
         ^^^^^^^^                       ^^^^^^^^^
   ```
2. The template is modified to replace all Mustache tags with placeholder XML
   tags. Unique IDs are attached to each placeholder tag to identify them in the
   translated XML.
   ```
   Hello <m id=0 />. You have just won <b><m id=1 /> dollars</b>!
         ^^^^^^^^^^                       ^^^^^^^^^^
   ```
3. The XML template is translated using DeepL API.
   ```
   Hallo <m id=0 />. Sie haben gerade <b><m id=1 /> Dollar</b> gewonnen!
   ```
4. The translated XML is parsed to identify placeholder tags and replace them 
   with the original Mustache tags.
   ```
   Hallo {{name}}. Sie haben gerade <b>{{value}} Dollar</b> gewonnen!
         ^^^^^^^^                      ^^^^^^^^^
   ```
   

[mustache-docs]: https://mustache.github.io/mustache.5.html