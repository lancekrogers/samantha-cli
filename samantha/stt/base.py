"""Base protocol for STT providers."""

from __future__ import annotations

import audioop
import collections
import math
from typing import Callable, Protocol


def _normalize_audio_level(energy: float, threshold: float) -> float:
    """Map raw RMS energy to a stable 0..1 display range."""
    floor = max(threshold * 0.15, 1.0)
    ceiling = max(threshold * 2.5, floor + 1.0)
    level = (energy - floor) / (ceiling - floor)
    return max(0.0, min(level, 1.0))


def listen_with_activity(
    recognizer,
    source,
    timeout: int = 10,
    phrase_time_limit: int = 30,
    on_status: Callable[[str], None] | None = None,
    on_level: Callable[[float], None] | None = None,
):
    """Listen for a phrase while emitting real-time mic levels and onset events."""
    import speech_recognition as sr

    seconds_per_buffer = float(source.CHUNK) / source.SAMPLE_RATE
    pause_buffer_count = int(math.ceil(recognizer.pause_threshold / seconds_per_buffer))
    phrase_buffer_count = int(math.ceil(recognizer.phrase_threshold / seconds_per_buffer))
    non_speaking_buffer_count = int(
        math.ceil(recognizer.non_speaking_duration / seconds_per_buffer)
    )

    elapsed_time = 0.0
    buffer = b""
    pause_count = 0

    if on_level:
        on_level(0.0)

    while True:
        frames = collections.deque()

        while True:
            elapsed_time += seconds_per_buffer
            if timeout is not None and elapsed_time > timeout:
                raise sr.WaitTimeoutError("listening timed out while waiting for phrase to start")

            buffer = source.stream.read(source.CHUNK)
            if len(buffer) == 0:
                break

            frames.append(buffer)
            if len(frames) > non_speaking_buffer_count:
                frames.popleft()

            energy = audioop.rms(buffer, source.SAMPLE_WIDTH)
            if on_level:
                on_level(_normalize_audio_level(energy, recognizer.energy_threshold))

            if energy > recognizer.energy_threshold:
                if on_status:
                    on_status("hearing")
                break

            if recognizer.dynamic_energy_threshold:
                damping = recognizer.dynamic_energy_adjustment_damping ** seconds_per_buffer
                target_energy = energy * recognizer.dynamic_energy_ratio
                recognizer.energy_threshold = (
                    recognizer.energy_threshold * damping
                    + target_energy * (1 - damping)
                )

        pause_count = 0
        phrase_count = 0
        phrase_start_time = elapsed_time

        while True:
            elapsed_time += seconds_per_buffer
            if (
                phrase_time_limit is not None
                and elapsed_time - phrase_start_time > phrase_time_limit
            ):
                break

            buffer = source.stream.read(source.CHUNK)
            if len(buffer) == 0:
                break

            frames.append(buffer)
            phrase_count += 1

            energy = audioop.rms(buffer, source.SAMPLE_WIDTH)
            if on_level:
                on_level(_normalize_audio_level(energy, recognizer.energy_threshold))

            if energy > recognizer.energy_threshold:
                pause_count = 0
            else:
                pause_count += 1

            if pause_count > pause_buffer_count:
                break

            if recognizer.dynamic_energy_threshold:
                damping = recognizer.dynamic_energy_adjustment_damping ** seconds_per_buffer
                target_energy = energy * recognizer.dynamic_energy_ratio
                recognizer.energy_threshold = (
                    recognizer.energy_threshold * damping
                    + target_energy * (1 - damping)
                )

        phrase_count -= pause_count
        if phrase_count >= phrase_buffer_count or len(buffer) == 0:
            break

        if on_status:
            on_status("listening")

    for _ in range(max(0, pause_count - non_speaking_buffer_count)):
        frames.pop()

    if on_level:
        on_level(0.0)

    return sr.AudioData(b"".join(frames), source.SAMPLE_RATE, source.SAMPLE_WIDTH)


class STTProvider(Protocol):
    """Interface that all STT backends must implement."""

    on_status: Callable[[str], None] | None
    on_level: Callable[[float], None] | None

    def transcribe(self, timeout: int, phrase_time_limit: int) -> str | None:
        """Listen on the microphone and return transcribed text.

        Returns None if no speech was detected or understood.
        Raises RuntimeError if the microphone is not accessible.
        """
        ...

    def available(self) -> bool:
        """Return True if this provider is ready to use."""
        ...
