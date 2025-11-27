# Copyright 2025 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

import asyncio
import base64
import json
import logging
import sys
from urllib.parse import urlencode

import aiohttp
import click
import websockets

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s][%(asctime)s.%(msecs)03d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Supported media content types for the DeepL Voice API
supported_media_content_types = [
    "audio/auto",
    "audio/flac",
    "audio/mpeg",
    "audio/ogg",
    "audio/webm",
    "audio/x-matroska",
    "audio/ogg;codecs=flac",
    "audio/ogg;codecs=opus",
    "audio/pcm;encoding=s16le;rate=8000",
    "audio/pcm;encoding=s16le;rate=16000",
    "audio/pcm;encoding=s16le;rate=44100",
    "audio/pcm;encoding=s16le;rate=48000",
    "audio/webm;codecs=opus",
    "audio/x-matroska;codecs=aac",
    "audio/x-matroska;codecs=flac",
    "audio/x-matroska;codecs=mp3",
    "audio/x-matroska;codecs=opus",
]


async def get_streaming_uri(
    session: aiohttp.ClientSession,
    auth_key: str,
    source_media_content_type: str,
    source_language: str | None,
    target_languages: tuple[str, ...],
    formality: str | None,
    glossary_id: str | None,
):
    """
    Get a DeepL Voice API streaming URI for real-time transcription and translation.

    Please refer to https://developers.deepl.com/api-reference/voice/request-stream.

    Args:
        session: aiohttp.ClientSession instance for making HTTP requests
        auth_key: DeepL API key for authentication
        source_media_content_type: content type of the audio file
        source_language: source language of the audio file, or None for auto-detection
        target_languages: tuple of target languages for translation
        formality: formality setting for translation
        glossary_id: glossary ID for translation

    Returns:
        str: WebSocket URI for real-time audio translation
    """
    get_stream_url = "https://api.deepl.com/v3/voice/realtime"

    request_payload = {
        "source_media_content_type": source_media_content_type,
        "source_language": source_language,
        "source_language_mode": "fixed" if source_language else "auto",
        "target_languages": target_languages,
        "formality": formality,
        "glossary_id": glossary_id,
    }

    logger.info(f"Config: {json.dumps(request_payload, indent=2)}")

    logger.info(f"Obtaining stream URI from {get_stream_url}...")

    async with session.post(
        get_stream_url,
        json=request_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"DeepL-Auth-Key {auth_key}",
        },
    ) as response:
        response.raise_for_status()
        response_data = await response.json()

    stream_token = response_data.get("token")
    stream_url = response_data.get("streaming_url")
    stream_session_id = response_data.get("session_id")

    if stream_token is None or stream_url is None:
        raise ValueError(
            f"Did not receive a valid token or streaming URL from the API: {response_data.get('message')}"
        )

    logger.info(f"Streaming Session Id: {stream_session_id}")

    # Return WebSocket URI with token as query parameter
    return f"{stream_url}?{urlencode({'token': stream_token})}"


async def audio_input_provider(filename: str):
    """
    Read an audio file and yield its content in chunks.

    Args:
        filename: path to the audio file or '-' for default audio input (microphone)

    Yields:
        tuple[int, bytes]: sequence number and audio chunk data
    """

    if filename == "-":
        from pyaudio_utils import DefaultAudioInput

        async with DefaultAudioInput() as mic_input:
            logger.info("Terminate with [Ctrl-C]")
            sequence = 0
            async for audio_chunk in mic_input:
                yield sequence, audio_chunk
                sequence += 1
    else:
        logger.info(f"Reading audio data from file: '{filename}'")
        with open(filename, "rb") as file:
            sequence = 0
            while audio_chunk := file.read(
                6400  # that's 200 ms of pcm 16k s16le
            ):
                yield sequence, audio_chunk
                # wait 200 ms between chunks
                # to simulate real-time audio input. we don't know the audio length of the chunks here.
                # it's important to not flood the server with data too quickly, otherwise you hit
                # the rate limits and get disconnected.
                await asyncio.sleep(0.2)
                sequence += 1


async def websocket_listener(websocket, target_languages: tuple[str, ...]):
    """
    Listen for and process WebSocket responses from the DeepL Voice API.

    Receives and logs transcript updates (both source and target), collecting
    concluded transcript chunks to display the full transcript as it's built.
    Exits when the end_of_stream message is received.

    Args:
        websocket: WebSocket connection to listen on
        target_languages: tuple of target languages for translation

    Raises:
        RuntimeError: if an error occurs during WebSocket communication
    """
    try:
        # we collect and join transcript updates to form the full transcript
        full_concluded_source_transcript = ""
        full_concluded_target_transcript = dict.fromkeys(target_languages, "")

        async for message in websocket:
            message_data = json.loads(message)

            # there should only be one field set in the message
            assert (
                len(message_data) == 1
            ), f"Unexpected message format: {message_data}"

            if "source_transcript_update" in message_data:
                transcript_update = message_data["source_transcript_update"]
                # join all chunks of the update
                concluded_update = "".join(
                    chunk["text"] for chunk in transcript_update["concluded"]
                )
                tentative_update = "".join(
                    chunk["text"] for chunk in transcript_update["tentative"]
                )
                # append the concluded part to the full transcript
                full_concluded_source_transcript += concluded_update

                logger.info(
                    f"[WS] Source Transcript Update: {full_concluded_source_transcript} [{tentative_update}]\n"
                )

            elif "target_transcript_update" in message_data:
                transcript_update = message_data["target_transcript_update"]
                language = transcript_update["language"]
                # join all chunks of the update
                concluded_update = "".join(
                    chunk["text"] for chunk in transcript_update["concluded"]
                )
                tentative_update = "".join(
                    chunk["text"] for chunk in transcript_update["tentative"]
                )
                # append the concluded part to the full transcript
                full_concluded_target_transcript[language] += concluded_update

                logger.info(
                    f"[WS] Target Transcript Update ({language}): {full_concluded_target_transcript[language]} [{tentative_update}]\n"
                )

            elif "end_of_source_transcript" in message_data:
                logger.info(
                    f"[WS] Final Source Transcript: {full_concluded_source_transcript}\n"
                )

            elif "end_of_target_transcript" in message_data:
                language = message_data["end_of_target_transcript"]["language"]
                logger.info(
                    f"[WS] Final Target Transcript ({language}): {full_concluded_target_transcript[language]}\n"
                )

            elif "end_of_stream" in message_data:
                logger.info("[WS] End of Stream")

                # no more messages expected, we can exit the listener here
                return

            elif "error" in message_data:
                logger.error(f"[WS] Error received: {message_data['error']}")

            else:
                logger.warning(
                    f"[WS] Unknown WebSocket Message: {message_data}"
                )

    except websockets.exceptions.ConnectionClosed:
        logger.warning("[WebSocket Response]: Connection closed by server")
    except Exception as ex:
        raise RuntimeError("WebSocket Listener Error") from ex


async def main(
    source_media_content_type: str,
    audio_file_path: str,
    source_language: str | None,
    target_languages: tuple[str, ...],
    formality: str | None,
    glossary_id: str | None,
    auth_key: str,
):
    """
    Main entry function for DeepL Voice API streaming demo.

    Args:
        source_media_content_type: content type of the audio file
        audio_file_path: path to the audio file or '-' for default audio input (microphone)
        source_language: source language of the audio file, or None for auto-detection
        target_languages: tuple of target languages for translation
        formality: formality setting for translation
        glossary_id: glossary ID for translation
        auth_key: DeepL API key for authentication
    """

    logger.info("Starting DeepL Voice API streaming demo...")
    # mic input implies pcm 16k
    source_media_content_type = (
        "audio/pcm;encoding=s16le;rate=16000"
        if audio_file_path == "-"
        else source_media_content_type
    )
    async with aiohttp.ClientSession() as session:
        # STEP 1: Obtain the WebSocket URI for the streaming service
        stream_uri = await get_streaming_uri(
            session,
            auth_key,
            source_media_content_type,
            source_language,
            target_languages,
            formality,
            glossary_id,
        )

        # STEP 2: Connect to the WebSocket using the obtained URI
        logger.info("Connecting to WebSocket...")
        async with websockets.connect(stream_uri) as websocket:
            logger.info("Connected to WebSocket!")

            # STEP 3: Start listening for responses in a background task
            listen_task = asyncio.create_task(
                websocket_listener(websocket, target_languages)
            )

            # STEP 4: load and send audio data in chunks to the WebSocket
            logger.info("Start sending audio data")
            async for sequence, audio_chunk in audio_input_provider(
                audio_file_path
            ):
                audio_message = json.dumps(
                    {
                        "source_media_chunk": {
                            "data": base64.b64encode(audio_chunk).decode(
                                "utf-8"
                            )
                        }
                    }
                )

                await websocket.send(audio_message)
                logger.debug(
                    f"Sent audio chunk {sequence} ({len(audio_chunk)} bytes)"
                )

            # STEP 5: Indicate end of audio data input to the stream
            #         This flushes the transcription/translation pipeline and
            #         allows the server to finalize the processing of the audio.
            #         The server will then send the final transcript updates and the indication
            #         that the target transcripts are complete.
            await websocket.send(json.dumps({"end_of_source_media": {}}))
            logger.info("Finished sending audio data")

            # wait for the listening task to complete
            await listen_task

    logger.info("WebSocket connection closed")


@click.command()
@click.argument(
    "audio-file-path",
    type=click.Path(exists=True, allow_dash=True, dir_okay=False),
)
@click.argument("target-language", type=str, nargs=-1)
@click.option(
    "-c",
    "--media-content-type",
    type=click.Choice(supported_media_content_types),
    default="audio/auto",
    help="Content type of the audio file or auto for auto-detection (default: audio/auto)",
)
@click.option(
    "-s",
    "--source-language",
    type=str,
    help="Set source language of the audio file",
    default=None,
)
@click.option(
    "-f",
    "--formality",
    type=click.Choice(("formal", "informal")),
    help="Formality setting for translation",
    default=None,
)
@click.option(
    "-g",
    "--glossary",
    "glossary_id",
    type=str,
    help="ID of glossary to use for translation",
    default=None,
)
@click.option(
    "-k",
    "--auth-key",
    envvar="DEEPL_AUTH_KEY",
    help="DeepL Auth Key",
    required=True,
)
def sync_main(
    media_content_type: str,
    audio_file_path: str,
    target_language: tuple[str, ...],
    source_language: str | None,
    formality: str | None,
    glossary_id: str | None,
    auth_key: str,
):
    """
    DeepL Voice API streaming example CLI.

    Please refer to https://developers.deepl.com/api-reference/voice for the
    DeepL Voice API documentation.

    \b
    AUDIO_FILE_PATH: Path to the audio file to be transcribed and translated.
                     Use '-' for default audio input (microphone).
    """
    asyncio.run(
        main(
            media_content_type,
            audio_file_path,
            source_language,
            target_language,
            formality,
            glossary_id,
            auth_key,
        )
    )


if __name__ == "__main__":
    sys.exit(sync_main())
