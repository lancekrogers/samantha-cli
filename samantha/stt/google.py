"""Google STT provider — free, uses SpeechRecognition library."""

from __future__ import annotations


def _default_mic_index() -> int | None:
    """Get the system default input device index via PyAudio."""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        try:
            info = p.get_default_input_device_info()
            return info["index"]
        finally:
            p.terminate()
    except Exception:
        return None


class GoogleSTTProvider:
    """STT using Google's free speech recognition service."""

    def __init__(self, language: str = "en-US") -> None:
        self.language = language
        self._recognizer = None

    def _init_recognizer(self):
        if self._recognizer is not None:
            return self._recognizer

        import speech_recognition as sr

        self._recognizer = sr.Recognizer()
        self._recognizer.pause_threshold = 3.0
        self._recognizer.phrase_threshold = 0.2
        self._recognizer.non_speaking_duration = 2.0
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.energy_threshold = 300
        return self._recognizer

    def transcribe(self, timeout: int = 10, phrase_time_limit: int = 30) -> str | None:
        import speech_recognition as sr

        recognizer = self._init_recognizer()

        try:
            with sr.Microphone(device_index=_default_mic_index()) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )
        except sr.WaitTimeoutError:
            return None
        except OSError as e:
            raise RuntimeError(
                f"Could not access the microphone: {e}. "
                "Check your audio input settings and permissions."
            ) from e

        try:
            text = recognizer.recognize_google(audio, language=self.language)
            return text.strip() if text else None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            raise RuntimeError(
                f"Speech recognition service error: {e}. "
                "Check your internet connection."
            ) from e

    def available(self) -> bool:
        try:
            import speech_recognition as sr  # noqa: F401
            return True
        except ImportError:
            return False
