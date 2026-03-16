"""Configuration management for Samantha.

Stores and loads user preferences from ~/.samantha/config.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path.home() / ".samantha"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULTS: dict[str, Any] = {
    # TTS settings
    "tts_provider": "edge",
    "tts_voice": "en-US-AriaNeural",
    "speech_speed": 0.95,

    # STT settings
    "stt_provider": "google",
    "whisper_model": "base",

    # Fish Audio (only when tts_provider == "fish")
    "fish_api_key": "",
    "fish_voice_model_id": "474887f7949b4d1ab3e626cddf82613a",

    # General
    "language": "en-US",
    "max_history": 10,
    "listen_timeout": 10,
    "phrase_time_limit": 30,
}

# Environment variable name -> config key
_ENV_OVERRIDES = {
    "TTS_PROVIDER": "tts_provider",
    "TTS_VOICE": "tts_voice",
    "STT_PROVIDER": "stt_provider",
    "WHISPER_MODEL": "whisper_model",
    "FISH_API_KEY": "fish_api_key",
}


def _ensure_config_dir() -> None:
    """Create the config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _migrate(config: dict[str, Any]) -> None:
    """Migrate old config keys to new names."""
    if "voice_model_id" in config and "fish_voice_model_id" not in config:
        config["fish_voice_model_id"] = config.pop("voice_model_id")


def load() -> dict[str, Any]:
    """Load configuration from disk, falling back to defaults.

    Environment variables override file values.
    """
    config = dict(DEFAULTS)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                stored = yaml.safe_load(f) or {}
            _migrate(stored)
            config.update(stored)
        except (yaml.YAMLError, OSError):
            pass

    for env_name, config_key in _ENV_OVERRIDES.items():
        val = os.environ.get(env_name)
        if val:
            config[config_key] = val

    return config


def save(config: dict[str, Any]) -> None:
    """Persist configuration to disk."""
    _ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def get(key: str) -> Any:
    """Get a single config value."""
    return load().get(key, DEFAULTS.get(key))


def set_key(key: str, value: Any) -> None:
    """Set a single config value and persist."""
    config = load()
    config[key] = value
    save(config)
