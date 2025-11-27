# Copyright 2025 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

import asyncio
import contextlib
import logging
import threading

try:
    import pyaudio
except Exception as ex:
    raise ImportError(
        "PyAudio is required for audio input functionality.\nPlease install the environment with '--group mic'"
    ) from ex

logger = logging.getLogger(__name__)


class DefaultAudioInput(contextlib.AbstractAsyncContextManager):
    """
    Async context manager for capturing audio from the default system input device.

    This class provides an async iterator interface for streaming audio data from
    the default microphone in real-time. Audio is captured in a background thread
    and made available through an async queue.

    Audio format:
        - Sample rate: 16kHz
        - Format: 16-bit signed PCM (paInt16)
        - Channels: 1 (mono)
        - Chunk size: 1600 frames (100ms of audio)
    """

    def __init__(self):
        """Initialize the audio input handler with empty state."""
        self.stream = None
        self.queue = asyncio.Queue(
            maxsize=300  # equivalent to 30 seconds of audio
        )
        self.pa = None
        self.close_event = threading.Event()
        self.reader_thread = None

    async def __aenter__(self):
        """
        Start the audio capture background thread when entering the context.
        """
        self.reader_thread = threading.Thread(
            target=self._reader_worker,
            args=(asyncio.get_running_loop(),),
            daemon=True,
        )
        self.close_event.clear()
        self.reader_thread.start()
        # Wait for the stream to initialize
        await asyncio.sleep(1)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Signals the background thread to stop and waits for it to complete.
        """
        self.close_event.set()
        await asyncio.to_thread(self.reader_thread.join)
        logger.info("Audio input stream closed")

    async def __aiter__(self):
        """
        Async iterator that yields audio chunks as they become available.

        Yields:
            bytes: raw audio data chunks in 16-bit PCM format
        """
        while audio_chunk := await self.queue.get():
            yield audio_chunk
            self.queue.task_done()

    def _reader_worker(self, eventloop: asyncio.AbstractEventLoop):
        """
        Background thread worker that reads audio data from the microphone.

        This method runs in a separate thread to avoid blocking the async event loop.
        It continuously reads audio chunks from the default input device and places
        them in the queue for consumption by the async iterator.

        Args:
            eventloop: asyncio event loop to use for thread-safe queue operations
        """
        pa = pyaudio.PyAudio()
        frames_per_chunk = 1600  # 100ms of audio at 16kHz
        default_device = pa.get_default_input_device_info()

        # Verify the device supports the required audio format
        if not pa.is_format_supported(
            16000,  # Sample rate
            input_device=default_device["index"],
            input_channels=default_device["maxInputChannels"],
            input_format=pyaudio.paInt16,
        ):
            raise RuntimeError(
                f"Requested audio format not supported by device '{default_device['name']}'"
            )

        # Open the audio stream with the required configuration
        self.stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=frames_per_chunk,
            start=True,
            input_device_index=default_device["index"],
        )

        logger.info(
            f"Reading audio data from default input device: '{default_device['name']}'"
        )

        # Read audio chunks until close is signaled
        while self.stream.is_active() and not self.close_event.is_set():
            chunk = self.stream.read(
                frames_per_chunk, exception_on_overflow=True
            )
            if not eventloop.is_running():
                break

            # Thread-safe queue operation using the event loop
            eventloop.call_soon_threadsafe(self.queue.put_nowait, chunk)

        # Clean up PyAudio resources
        self.stream.stop_stream()
        self.stream.close()
        pa.terminate()
