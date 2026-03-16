"""Fish Audio TTS provider — paid, supports custom voice clones."""

from __future__ import annotations


class FishAudioProvider:
    """TTS using Fish Audio's API."""

    def __init__(self, api_key: str = "", voice_model_id: str = "", speed: float = 1.0) -> None:
        self.api_key = api_key
        self.voice_model_id = voice_model_id
        self.speed = speed
        self._client = None
        self._config = None

    def _init_client(self) -> None:
        if self._client is not None:
            return

        from fishaudio import FishAudio
        from fishaudio.types import TTSConfig, Prosody

        self._client = FishAudio(api_key=self.api_key)
        self._config = TTSConfig(
            reference_id=self.voice_model_id,
            prosody=Prosody(speed=self.speed),
            format="mp3",
        )

    def generate(self, text: str, output_path: str) -> str:
        self._init_client()

        audio = self._client.tts.convert(text=text, config=self._config)

        if isinstance(audio, bytes):
            data = audio
        else:
            data = b"".join(
                chunk if isinstance(chunk, bytes) else bytes([chunk])
                for chunk in audio
            )

        with open(output_path, "wb") as f:
            f.write(data)
        return output_path

    def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import fishaudio  # noqa: F401
            return True
        except ImportError:
            return False

    def list_voices(self, locale: str = "", gender: str = "") -> list[dict]:
        return []
