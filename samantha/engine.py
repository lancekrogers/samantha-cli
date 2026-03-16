"""Conversation engine -- the core loop decoupled from any UI.

Owns the Brain and VoiceEngine, runs the listen-think-speak loop,
and emits events for anything a UI layer might care about.
The engine knows nothing about Rich, terminals, or display.
"""

from __future__ import annotations

import time
import threading
from typing import Any

from samantha.brain import Brain
from samantha.voice import VoiceEngine, TTSError
from samantha.events import (
    EventBus,
    ReadyForInput,
    UserInput,
    STTPhase,
    MicLevel,
    ThinkingStarted,
    ThinkingComplete,
    GeneratingVoice,
    VoiceGenerated,
    SpeakingStarted,
    SpeakingComplete,
    ResponseReady,
    ConversationCleared,
    Error,
    Info,
    SessionExit,
)


# Natural-language exit commands
_EXIT_WORDS = {"exit", "quit", "bye", "goodbye", "stop", "/exit", "/q"}
_EXIT_PHRASES = [
    "gotta go", "got to go", "i'm out", "i'm done", "wrap up",
    "talk later", "see you later", "see ya", "good night",
    "signing off", "peace out", "catch you later", "bye samantha",
    "bye bye", "that's all", "we're done", "samantha exit",
    "samantha quit", "samantha bye",
]

_CLEAR_PHRASES = [
    "forget everything", "start over", "clear the conversation",
    "fresh start", "new conversation", "reset",
]
_CLEAR_WORDS = {"/clear", "/c"}


class ConversationEngine:
    """Runs the conversation loop, emitting events instead of calling a UI.

    Usage:
        bus = EventBus()
        engine = ConversationEngine(brain, voice, bus, text_mode=False)
        # subscribe UI handlers to bus ...
        engine.run()   # blocks until exit
    """

    def __init__(
        self,
        brain: Brain,
        voice: VoiceEngine,
        bus: EventBus,
        text_mode: bool = False,
        input_fn=None,
    ) -> None:
        self.brain = brain
        self.voice = voice
        self.bus = bus
        self.text_mode = text_mode
        self._input_fn = input_fn  # callable that returns str (for text mode)
        self._running = False

    def run(self) -> None:
        """Block on the listen-think-speak loop until exit."""
        self._running = True
        phase_times: dict[str, float] = {}

        # Wire STT status callback
        def _on_stt_status(phase: str) -> None:
            now = time.monotonic()
            if phase_times.get("last_phase"):
                prev = phase_times["last_phase"]
                elapsed = now - phase_times.get("last_time", now)
                self.bus.emit(STTPhase(phase=prev, elapsed=elapsed))
            phase_times["last_phase"] = phase
            phase_times["last_time"] = now
            # Emit current phase with zero elapsed (it just started)
            self.bus.emit(STTPhase(phase=phase, elapsed=0.0))

        def _on_stt_level(level: float) -> None:
            self.bus.emit(MicLevel(level=level))

        self.voice.stt.on_status = _on_stt_status
        self.voice.stt.on_level = _on_stt_level

        while self._running:
            # --- 1. Get user input ---
            user_input = self._get_input(phase_times)
            if user_input is None:
                continue  # silence or empty

            self.bus.emit(UserInput(text=user_input))

            # --- Check for commands ---
            cmd = user_input.strip().lower()

            if cmd in _EXIT_WORDS or any(cmd == p for p in _EXIT_PHRASES):
                self.bus.emit(SessionExit())
                break

            if cmd in _CLEAR_WORDS or any(p in cmd for p in _CLEAR_PHRASES):
                self.brain.history.clear()
                self.brain._first_sent = False
                self.brain._save_history()
                self.bus.emit(ConversationCleared())
                continue

            # --- 2. Think ---
            self.bus.emit(ThinkingStarted())
            t0 = time.monotonic()
            try:
                response = self.brain.think(user_input)
            except (RuntimeError, TimeoutError) as e:
                self.bus.emit(Error(message=str(e)))
                continue

            think_time = time.monotonic() - t0
            full_response = getattr(self.brain, "_full_response", response)
            self.bus.emit(ThinkingComplete(
                response=response,
                full_response=full_response,
                elapsed=think_time,
            ))

            # --- 3. Respond ---
            if self.voice.tts_available and not self.text_mode:
                self._respond_with_voice(response, full_response)
            else:
                self.bus.emit(ResponseReady(
                    response=response,
                    full_response=full_response,
                ))

    def stop(self) -> None:
        """Signal the engine to stop after the current iteration."""
        self._running = False

    # --- Private helpers ---

    def _get_input(self, phase_times: dict[str, float]) -> str | None:
        """Get input from text or voice, emitting appropriate events."""
        if self.text_mode:
            self.bus.emit(ReadyForInput(text_mode=True))
            try:
                text = self._input_fn() if self._input_fn else input("You: ")
                return text.strip() or None
            except EOFError:
                self.bus.emit(SessionExit())
                self._running = False
                return None
        else:
            phase_times.clear()
            self.bus.emit(ReadyForInput(text_mode=False))
            try:
                user_input = self.voice.listen()
            except KeyboardInterrupt:
                self.bus.emit(SessionExit())
                self._running = False
                return None
            except RuntimeError as e:
                self.bus.emit(Error(message=str(e)))
                self.bus.emit(Info(message="Switching to text mode."))
                self.text_mode = True
                return None

            # Emit final phase timing
            if phase_times.get("last_phase"):
                elapsed = time.monotonic() - phase_times.get("last_time", 0)
                self.bus.emit(STTPhase(
                    phase=phase_times["last_phase"],
                    elapsed=elapsed,
                ))

            return user_input

    def _respond_with_voice(self, response: str, full_response: str) -> None:
        """Generate TTS and play audio, emitting events along the way."""
        # Generate
        self.bus.emit(GeneratingVoice())
        t0 = time.monotonic()
        try:
            audio_path = self.voice.generate_audio(response)
        except TTSError as e:
            self.bus.emit(ResponseReady(response=response, full_response=full_response))
            self.bus.emit(Info(message=f"Voice output failed: {e}"))
            return

        gen_time = time.monotonic() - t0
        self.bus.emit(VoiceGenerated(path=audio_path or "", elapsed=gen_time))

        # Play
        if audio_path:
            self.bus.emit(SpeakingStarted())
            t0 = time.monotonic()
            player = threading.Thread(
                target=self.voice.play_audio, args=(audio_path,), daemon=True,
            )
            player.start()

            # Emit response for display while audio plays
            self.bus.emit(ResponseReady(response=response, full_response=full_response))

            player.join()
            play_time = time.monotonic() - t0
            self.bus.emit(SpeakingComplete(response=response, elapsed=play_time))
        else:
            self.bus.emit(ResponseReady(response=response, full_response=full_response))
