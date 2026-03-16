"""Base protocol for TTS providers."""

from __future__ import annotations

from typing import Protocol


class TTSProvider(Protocol):
    """Interface that all TTS backends must implement."""

    def generate(self, text: str, output_path: str) -> str:
        """Generate speech audio from text and save to output_path.

        Returns the path to the generated audio file.
        """
        ...

    def available(self) -> bool:
        """Return True if this provider is ready to use."""
        ...

    def list_voices(self) -> list[dict]:
        """Return available voices as a list of dicts.

        Each dict should have at minimum: name, friendly_name, gender, locale.
        """
        ...
