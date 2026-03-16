"""Edge TTS provider — free, no API key required."""

from __future__ import annotations

import asyncio


class EdgeTTSProvider:
    """TTS using Microsoft Edge's online speech service via edge-tts."""

    def __init__(self, voice: str = "en-US-AriaNeural", speed: float = 1.0) -> None:
        self.voice = voice
        self.speed = speed

    def _rate_str(self) -> str:
        pct = int((self.speed - 1.0) * 100)
        return f"{pct:+d}%"

    def generate(self, text: str, output_path: str) -> str:
        import edge_tts

        async def _generate():
            communicate = edge_tts.Communicate(text, self.voice, rate=self._rate_str())
            await communicate.save(output_path)

        asyncio.run(_generate())
        return output_path

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def list_voices(self, locale: str = "", gender: str = "") -> list[dict]:
        import edge_tts

        async def _list():
            return await edge_tts.list_voices()

        voices = asyncio.run(_list())
        results = []
        for v in voices:
            if locale and not v["Locale"].startswith(locale):
                continue
            if gender and v["Gender"].lower() != gender.lower():
                continue
            results.append({
                "name": v["ShortName"],
                "friendly_name": v["FriendlyName"],
                "gender": v["Gender"],
                "locale": v["Locale"],
            })
        return results
