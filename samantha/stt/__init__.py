"""STT provider factory."""

from __future__ import annotations

from typing import Any

from samantha.stt.base import STTProvider


def get_stt_provider(config: dict[str, Any]) -> STTProvider:
    """Create an STT provider from config settings."""
    provider = config.get("stt_provider", "google")
    language = config.get("language", "en-US")

    if provider == "whisper":
        from samantha.stt.whisper import WhisperSTTProvider
        return WhisperSTTProvider(
            model_size=config.get("whisper_model", "base"),
            language=language,
        )

    from samantha.stt.google import GoogleSTTProvider
    return GoogleSTTProvider(language=language)
