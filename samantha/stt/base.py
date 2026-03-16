"""Base protocol for STT providers."""

from __future__ import annotations

from typing import Protocol


class STTProvider(Protocol):
    """Interface that all STT backends must implement."""

    def transcribe(self, timeout: int, phrase_time_limit: int) -> str | None:
        """Listen on the microphone and return transcribed text.

        Returns None if no speech was detected or understood.
        Raises RuntimeError if the microphone is not accessible.
        """
        ...

    def available(self) -> bool:
        """Return True if this provider is ready to use."""
        ...
