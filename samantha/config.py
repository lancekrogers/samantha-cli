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
    "fish_api_key": "",
    "voice_model_id": "474887f7949b4d1ab3e626cddf82613a",
    "speech_speed": 0.95,
    "language": "en-US",
    "max_history": 10,
    "listen_timeout": 10,
    "phrase_time_limit": 30,
}


def _ensure_config_dir() -> None:
    """Create the config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict[str, Any]:
    """Load configuration from disk, falling back to defaults.

    Environment variables override file values:
        FISH_API_KEY -> fish_api_key
    """
    config = dict(DEFAULTS)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                stored = yaml.safe_load(f) or {}
            config.update(stored)
        except (yaml.YAMLError, OSError):
            pass  # Fall back to defaults silently

    # Environment variable overrides
    env_key = os.environ.get("FISH_API_KEY")
    if env_key:
        config["fish_api_key"] = env_key

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
