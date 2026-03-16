"""Voice engine -- delegates to configurable TTS and STT providers."""

from __future__ import annotations

import subprocess
import platform
import tempfile
from pathlib import Path
from typing import Any

from samantha.tts import get_tts_provider
from samantha.stt import get_stt_provider


class VoiceEngine:
    """Manages speech-to-text and text-to-speech via pluggable providers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.tts = get_tts_provider(config)
        self.stt = get_stt_provider(config)
        self._temp_dir = Path(tempfile.mkdtemp(prefix="samantha_"))

    @property
    def tts_available(self) -> bool:
        return self.tts.available()

    @property
    def stt_available(self) -> bool:
        return self.stt.available()

    def listen(self) -> str | None:
        """Listen on the microphone and return transcribed text."""
        return self.stt.transcribe(
            timeout=self.config.get("listen_timeout", 10),
            phrase_time_limit=self.config.get("phrase_time_limit", 30),
        )

    def generate_audio(self, text: str) -> str | None:
        """Generate TTS audio and save to temp file. Returns file path."""
        if not self.tts_available:
            return None

        ext = ".wav" if self.config.get("tts_provider") == "kokoro" else ".mp3"
        output_path = str(self._temp_dir / f"response{ext}")
        try:
            return self.tts.generate(text, output_path)
        except Exception as e:
            raise TTSError(f"Text-to-speech failed: {e}") from e

    def play_audio(self, path: str) -> None:
        """Play an audio file."""
        self._play_audio_file(path)

    def speak(self, text: str) -> None:
        """Generate and play TTS. For simple usage."""
        path = self.generate_audio(text)
        if path:
            self._play_audio_file(path)

    def _play_audio_file(self, path: str) -> None:
        """Play an audio file using the best available system player."""
        if platform.system() == "Darwin":
            subprocess.run(["afplay", path], check=True, capture_output=True)
        else:
            for player in [
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                ["mpv", "--no-video", "--really-quiet", path],
                ["aplay", path],
            ]:
                try:
                    subprocess.run(player, check=True, capture_output=True)
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            raise RuntimeError("No audio player found. Install ffmpeg or mpv.")

    def cleanup(self) -> None:
        """Release audio resources."""
        for f in self._temp_dir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            self._temp_dir.rmdir()
        except OSError:
            pass


class TTSError(Exception):
    """Raised when text-to-speech conversion or playback fails."""
