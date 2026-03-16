"""Whisper STT provider — fully local, no internet needed after model download."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from samantha.stt.base import listen_with_activity
from samantha.stt.google import _default_mic_index


class WhisperSTTProvider:
    """STT using faster-whisper for local speech recognition."""

    def __init__(self, model_size: str = "base", language: str = "en") -> None:
        self.model_size = model_size
        self.language = language.split("-")[0]  # "en-US" -> "en"
        self._model = None
        self.on_status: Callable[[str], None] | None = None
        self.on_level: Callable[[float], None] | None = None

    def _init_model(self):
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel

        if self.on_status:
            self.on_status("loading_model")
        self._model = WhisperModel(self.model_size, compute_type="auto")
        return self._model

    def transcribe(self, timeout: int = 10, phrase_time_limit: int = 30) -> str | None:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 3.0
        recognizer.phrase_threshold = 0.2
        recognizer.non_speaking_duration = 2.0
        recognizer.dynamic_energy_threshold = True
        recognizer.energy_threshold = 300

        if self.on_status:
            self.on_status("listening")

        try:
            with sr.Microphone(device_index=_default_mic_index()) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = listen_with_activity(
                    recognizer,
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                    on_status=self.on_status,
                    on_level=self.on_level,
                )
        except sr.WaitTimeoutError:
            return None
        except OSError as e:
            raise RuntimeError(
                f"Could not access the microphone: {e}. "
                "Check your audio input settings and permissions."
            ) from e

        if self.on_status:
            self.on_status("transcribing")

        wav_data = audio.get_wav_data()
        tmp = Path(tempfile.mktemp(suffix=".wav", prefix="samantha_stt_"))
        try:
            tmp.write_bytes(wav_data)
            model = self._init_model()
            segments, _ = model.transcribe(str(tmp), language=self.language)
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return text if text else None
        finally:
            tmp.unlink(missing_ok=True)

    def available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False
