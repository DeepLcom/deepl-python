# Example: Real-time audio translation using the DeepL Voice API

An example command-line interface showing how to use the [DeepL Voice API][voice-api-docs]
for real-time audio transcription and translation. The CLI supports both audio file input
and live microphone input, streaming audio data to the API via WebSocket and receiving
transcriptions and translations as they become available.

## Usage

Install dependencies for this example:

```shell
cd examples/voice/cli
uv sync
# or
poetry install
```

For microphone support, install the `mic` dependency group. You may need to install
a system package for `pyaudio` first (e.g. `portaudio19-dev` on Debian/Ubuntu, `portaudio` on MacOS):

```shell
uv sync --group mic
# or
poetry install --with mic
```

Define your DeepL Auth key as an environment variable `DEEPL_AUTH_KEY`.

```shell
export DEEPL_AUTH_KEY=your-api-key-here
```

Translate an audio file to one or more target languages:

```shell
uv run python deepl-voice-api-cli.py audio.mp3 de fr
# or
poetry run python deepl-voice-api-cli.py audio.mp3 de fr
```

For live microphone translation, use `-` as the audio file path:

```shell
uv run python deepl-voice-api-cli.py - es
# or
poetry run python deepl-voice-api-cli.py - es
```

For an explanation of the command line arguments, provide the `--help` option:

```shell
uv run python deepl-voice-api-cli.py --help
# or
poetry run python deepl-voice-api-cli.py --help
```

## How it works

This CLI demonstrates the DeepL Voice API streaming workflow:

1. **Request a streaming session**: The CLI sends a POST request to the DeepL Voice API
   to obtain a WebSocket URI with authentication token, specifying the source media type,
   source language (or auto-detection), and target languages.

2. **Connect via WebSocket**: The CLI establishes a WebSocket connection using the
   obtained URI for bidirectional streaming communication.

3. **Stream audio data**: Audio is read in chunks (from file or microphone) and sent
   to the WebSocket as base64-encoded JSON message. For files, chunks are sent with
   simulated delays; for microphone, audio is captured in real-time.

4. **Receive transcriptions and translations**: The API streams back real-time updates
   containing both tentative (in-progress) and concluded (finalized) transcriptions in
   the source language and translations in all requested target languages.

5. **Signal completion**: After all audio is sent, an `end_of_source_media` message
   flushes the pipeline, allowing the server to finalize processing and send complete
   transcripts.

The CLI supports various audio formats including MP3, FLAC, OGG, WebM, and raw PCM.
Microphone input automatically uses PCM format at 16kHz sample rate.

[voice-api-docs]: https://developers.deepl.com/api-reference/voice
