"""Kokoro TTS provider — local, no API key, high quality."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

MODELS_DIR = Path.home() / ".cache" / "samantha" / "models"
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
SAMPLE_RATE = 24000


def _download_if_missing(url: str, filename: str) -> Path:
    """Download a model file if not already cached."""
    path = MODELS_DIR / filename
    if path.exists():
        return path

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {filename}...")
    urllib.request.urlretrieve(url, str(path))
    print(f"  Saved to {path}")
    return path


class KokoroTTSProvider:
    """TTS using Kokoro-82M via ONNX runtime. Fully local after first download."""

    def __init__(self, voice: str = "af_heart", speed: float = 1.0) -> None:
        self.voice = voice
        self.speed = speed
        self._kokoro = None

    def _init(self):
        if self._kokoro is not None:
            return

        from kokoro_onnx import Kokoro

        model_path = _download_if_missing(MODEL_URL, MODEL_FILE)
        voices_path = _download_if_missing(VOICES_URL, VOICES_FILE)
        self._kokoro = Kokoro(str(model_path), str(voices_path))

    def generate(self, text: str, output_path: str) -> str:
        import soundfile as sf

        self._init()
        samples, sr = self._kokoro.create(text, voice=self.voice, speed=self.speed)
        sf.write(output_path, samples, sr)
        return output_path

    def available(self) -> bool:
        try:
            import kokoro_onnx  # noqa: F401
            import soundfile  # noqa: F401
            return True
        except ImportError:
            return False

    def list_voices(self, locale: str = "", gender: str = "") -> list[dict]:
        self._init()
        voices = self._kokoro.get_voices()

        # Voice naming: {lang}{gender}_{name}
        # a=American, b=British, e=Spanish, f=French, h=Hindi, i=Italian, j=Japanese, p=Portuguese, z=Chinese
        # f=female, m=male
        lang_map = {
            "a": "en-US", "b": "en-GB", "e": "es", "f": "fr",
            "h": "hi", "i": "it", "j": "ja", "p": "pt", "z": "zh",
        }
        gender_map = {"f": "Female", "m": "Male"}

        results = []
        for v in voices:
            if len(v) < 3 or "_" not in v:
                continue
            v_locale = lang_map.get(v[0], "unknown")
            v_gender = gender_map.get(v[1], "unknown")
            v_name = v.split("_", 1)[1] if "_" in v else v

            if locale and not v_locale.startswith(locale):
                continue
            if gender and v_gender.lower() != gender.lower():
                continue

            results.append({
                "name": v,
                "friendly_name": f"Kokoro {v_name.title()} ({v_locale})",
                "gender": v_gender,
                "locale": v_locale,
            })
        return results
