# Example: Translation of JSON values

An example showing how to translate strings within JSON objects.

The script translates strings, but leaves numbers, booleans, null values and
object keys untranslated. It also recurses into arrays and objects.

For example:

```
{
  "greeting": "Good morning!",
  "messages": [
    "This is a message.",
    {
      "text": "Here is an embedded text.",
      "sent": false
    },
    null
  ],
  "active": true,
  "balance": 100.0
}
```

could be translated into German as:

```
{
  "greeting": "Guten Morgen!",
  "messages": [
    "Dies ist eine Nachricht.",
    {
      "text": "Hier ist ein Text eingebettet.",
      "sent": false
    },
    null
  ],
  "active": true,
  "balance": 100.0
}
```

## Usage

Install the [`deepl` Python library](../../README.md).

Define your DeepL auth key as an environment variable `DEEPL_AUTH_KEY`.

```
export DEEPL_AUTH_KEY=f63c02c5-f056-...
```

Run the JSON translator by running Python on this directory:

```
python examples/json --to de '{"greeting": "Hello!"}'
```

For an explanation of the command line arguments, provide the `--help` option:

```
python examples/json --help
```
