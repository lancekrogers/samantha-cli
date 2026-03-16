"""TTS provider factory."""

from __future__ import annotations

from typing import Any

from samantha.tts.base import TTSProvider


def get_tts_provider(config: dict[str, Any]) -> TTSProvider:
    """Create a TTS provider from config settings."""
    provider = config.get("tts_provider", "edge")
    speed = config.get("speech_speed", 1.0)

    if provider == "fish":
        from samantha.tts.fish import FishAudioProvider
        return FishAudioProvider(
            api_key=config.get("fish_api_key", ""),
            voice_model_id=config.get("fish_voice_model_id", ""),
            speed=speed,
        )

    from samantha.tts.edge import EdgeTTSProvider
    return EdgeTTSProvider(
        voice=config.get("tts_voice", "en-US-AriaNeural"),
        speed=speed,
    )
