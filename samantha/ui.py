"""Rich-powered terminal UI for Samantha.

Provides a clean, minimal display with status indicators
and a scrolling conversation transcript.

The UI can subscribe to an EventBus to receive events from
the ConversationEngine, keeping display fully decoupled from logic.
"""

from __future__ import annotations

import math
import threading
import time
from enum import Enum

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from samantha.events import (
    EventBus,
    Event,
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


class Status(Enum):
    """Visual states for the UI."""

    IDLE = "idle"
    LISTENING = "listening"
    HEARING = "hearing"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    GENERATING = "generating"
    SPEAKING = "speaking"
    ERROR = "error"


# Status display configuration
_STATUS_STYLES: dict[Status, tuple[str, str, str]] = {
    #                    (dot_color,  label,          style)
    Status.IDLE:         ("dim",       "Ready",              "dim"),
    Status.LISTENING:    ("green",     "Listening...",        "bold green"),
    Status.HEARING:      ("green",     "Hearing you...",     "bold green"),
    Status.TRANSCRIBING: ("cyan",      "Transcribing...",    "bold cyan"),
    Status.THINKING:     ("yellow",    "Claude thinking...", "bold yellow"),
    Status.GENERATING:   ("blue",      "Generating voice...", "bold blue"),
    Status.SPEAKING:     ("magenta",   "Speaking...",         "bold magenta"),
    Status.ERROR:        ("red",       "Error",               "bold red"),
}

# Idle mic frames -- very subtle breathing dot, barely moving.
# Shows "I'm listening" without looking like you're talking.
_MIC_FRAMES_IDLE = [
    "  · · · ▁ · · ·  ",
    "  · · ▁ ▁ ▁ · ·  ",
    "  · · ▁ ▂ ▁ · ·  ",
    "  · · ▁ ▁ ▁ · ·  ",
]

# Active mic frames -- lively waveform for when speech is detected.
_MIC_FRAMES_ACTIVE = [
    "  ▁ ▂ ▃ ▅ ▃ ▂ ▁  ",
    "  ▁ ▃ ▅ ▅ ▅ ▃ ▁  ",
    "  ▂ ▃ ▅ ▇ ▅ ▃ ▂  ",
    "  ▃ ▅ ▇ ▇ ▇ ▅ ▃  ",
    "  ▅ ▅ ▇ ▇ ▇ ▅ ▅  ",
    "  ▃ ▅ ▇ ▇ ▇ ▅ ▃  ",
    "  ▂ ▃ ▅ ▇ ▅ ▃ ▂  ",
    "  ▁ ▃ ▅ ▅ ▅ ▃ ▁  ",
]

_MIC_BARS = ("·", "▁", "▂", "▃", "▄", "▅", "▆", "▇")
_MIC_PROFILE = (0.35, 0.6, 0.85, 1.0, 0.85, 0.6, 0.35)


class MicAnimation:
    """Animated microphone indicator that runs in a background thread."""

    def __init__(self, console: Console) -> None:
        self._console = console
        self._live: Live | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._label = "Listening..."
        self._color = "green"
        self._active = False  # idle vs active (speech detected)
        self._level = 0.0
        self._display_level = 0.0

    def start(self, label: str = "Listening...", color: str = "green") -> None:
        """Start the mic animation in idle mode."""
        self.stop()  # Clean up any previous animation
        self._label = label
        self._color = color
        self._active = False
        self._level = 0.0
        self._display_level = 0.0
        self._stop_event.clear()
        self._live = Live(
            self._render_frame(0),
            console=self._console,
            refresh_per_second=12,
            transient=True,
        )
        self._live.start()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def set_active(self, active: bool = True) -> None:
        """Switch between idle (waiting) and active (hearing speech) animation."""
        self._active = active

    def set_level(self, level: float) -> None:
        """Update the live microphone level."""
        self._level = max(0.0, min(level, 1.0))

    def update_label(self, label: str, color: str | None = None) -> None:
        """Update the label text without restarting the animation."""
        self._label = label
        if color:
            self._color = color

    def stop(self) -> None:
        """Stop the animation and clean up."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._live:
            try:
                self._live.stop()
            except Exception:
                pass
            self._live = None
        self._thread = None

    def _animate(self) -> None:
        """Animation loop -- runs in background thread."""
        frame_idx = 0
        while not self._stop_event.is_set():
            target = self._level
            if target >= self._display_level:
                self._display_level += (target - self._display_level) * 0.65
            else:
                self._display_level += (target - self._display_level) * 0.3

            if self._live:
                try:
                    self._live.update(self._render_frame(frame_idx))
                except Exception:
                    break
            frame_idx += 1
            interval = 0.08 if self._active or self._display_level > 0.05 else 0.25
            self._stop_event.wait(interval)

    def _render_frame(self, idx: int) -> Text:
        """Render a single animation frame."""
        if self._active or self._display_level > 0.05:
            waveform = self._render_live_wave()
        else:
            frames = _MIC_FRAMES_IDLE
            waveform = frames[idx % len(frames)]

        frame = Text()
        frame.append("  🎙 ", style=f"bold {self._color}")
        frame.append(waveform, style=self._color)
        frame.append(f" {self._label}", style=f"bold {self._color}")
        return frame

    def _render_live_wave(self) -> str:
        """Render a waveform whose height tracks the measured mic level."""
        bars = []
        for weight in _MIC_PROFILE:
            scaled = self._display_level * weight
            idx = min(len(_MIC_BARS) - 1, max(0, math.ceil(scaled * (len(_MIC_BARS) - 1))))
            bars.append(_MIC_BARS[idx])
        return f"  {' '.join(bars)}  "


class UI:
    """Terminal interface for Samantha.

    Uses Rich for colored output and status indicators.
    Keeps things simple -- prints sequentially rather than
    using Live display, which plays better with audio I/O.
    """

    def __init__(self) -> None:
        self.console = Console()
        self.mic = MicAnimation(self.console)

    def show_welcome(self) -> None:
        """Display the startup banner."""
        title = Text()
        title.append("Samantha", style="bold magenta")

        subtitle = Text("Give Claude a voice. Inspired by Her.", style="dim italic")

        welcome = Text()
        welcome.append("\n")
        welcome.append("  Say something, and I'll respond.\n", style="dim")
        welcome.append("  Press ", style="dim")
        welcome.append("Ctrl+C", style="bold dim")
        welcome.append(" to exit.\n", style="dim")

        panel = Panel(
            welcome,
            title=title,
            subtitle=subtitle,
            border_style="magenta",
            padding=(0, 2),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    def show_status(self, status: Status) -> None:
        """Print a status indicator line."""
        dot_color, label, style = _STATUS_STYLES[status]
        indicator = Text()
        indicator.append("  ● ", style=dot_color)
        indicator.append(label, style=style)
        self.console.print(indicator)

    def show_user(self, text: str) -> None:
        """Display what the user said."""
        line = Text()
        line.append("  You: ", style="bold cyan")
        line.append(text)
        self.console.print(line)

    def show_samantha(self, text: str) -> None:
        """Display Samantha's response all at once."""
        line = Text()
        line.append("  Samantha: ", style="bold magenta")
        line.append(text)
        self.console.print(line)
        self.console.print()

    def show_samantha_streaming(self, text: str, duration: float = 3.0) -> None:
        """Reveal Samantha's response word by word, timed to audio duration."""
        import time

        words = text.split()
        if not words:
            return

        ms_per_word = max(0.06, duration / len(words))
        revealed = "  Samantha: "

        for i, word in enumerate(words):
            revealed += word + " "
            # Clear line and reprint
            self.console.print(f"\r{revealed}", end="", highlight=False, style="magenta" if i == 0 else None)
            time.sleep(ms_per_word)

        self.console.print()  # Final newline
        self.console.print()  # Breathing room

    def show_error(self, message: str) -> None:
        """Display an error message."""
        line = Text()
        line.append("  Error: ", style="bold red")
        line.append(message, style="red")
        self.console.print(line)
        self.console.print()

    def show_step(self, label: str, elapsed: float) -> None:
        """Display a completed step with timing."""
        self.console.print(f"  [dim]  {label} ({elapsed:.1f}s)[/dim]")

    def show_info(self, message: str) -> None:
        """Display an informational message."""
        self.console.print(f"  [dim]{message}[/dim]")

    def show_goodbye(self) -> None:
        """Display the exit message."""
        self.console.print()
        self.console.print("  [dim magenta]See you later.[/dim magenta]")
        self.console.print()

    def clear_status(self) -> None:
        """Move cursor up to overwrite the last status line."""
        # Move up one line and clear it
        self.console.print("\033[A\033[2K", end="")

    # --- Event bus integration ---

    def subscribe_to(self, bus: EventBus) -> None:
        """Wire this UI up to an EventBus so it reacts to engine events.

        Call bus.unsubscribe_all() then ui.subscribe_to(bus) to hot-reload.
        """
        self._bus = bus

        bus.subscribe(STTPhase, self._on_stt_phase)
        bus.subscribe(MicLevel, self._on_mic_level)
        bus.subscribe(UserInput, self._on_user_input)
        bus.subscribe(ThinkingStarted, self._on_thinking_started)
        bus.subscribe(ThinkingComplete, self._on_thinking_complete)
        bus.subscribe(GeneratingVoice, self._on_generating_voice)
        bus.subscribe(VoiceGenerated, self._on_voice_generated)
        bus.subscribe(SpeakingStarted, self._on_speaking_started)
        bus.subscribe(SpeakingComplete, self._on_speaking_complete)
        bus.subscribe(ResponseReady, self._on_response_ready)
        bus.subscribe(ConversationCleared, self._on_cleared)
        bus.subscribe(Error, self._on_error)
        bus.subscribe(Info, self._on_info)

    def _on_stt_phase(self, event: STTPhase) -> None:
        """Handle STT phase transitions (listening, hearing, transcribing)."""
        phase = event.phase
        elapsed = event.elapsed

        # If there's timing from a previous phase, show it
        if elapsed > 0:
            if phase in ("listening", "hearing"):
                return
            self.mic.stop()
            self.show_step(phase, elapsed)
            return

        # Drive the mic animation for current phase
        if phase == "listening":
            self.mic.start("Listening...", "green")
        elif phase == "hearing":
            self.mic.start("Hearing you...", "green")
            self.mic.set_active(True)
        elif phase in ("loading_model", "transcribing"):
            self.mic.stop()
            self.show_status(Status.TRANSCRIBING)
        else:
            self.mic.start("Listening...", "green")

    def _on_mic_level(self, event: MicLevel) -> None:
        self.mic.set_level(event.level)

    def _on_user_input(self, event: UserInput) -> None:
        self.mic.stop()
        self.show_user(event.text)

    def _on_thinking_started(self, event: ThinkingStarted) -> None:
        self.show_status(Status.THINKING)

    def _on_thinking_complete(self, event: ThinkingComplete) -> None:
        self.clear_status()
        self.show_step("claude thinking", event.elapsed)

        # Show full Opus response if it was summarized
        if event.full_response != event.response and len(event.full_response) > len(event.response):
            self.console.print(Panel(
                Text(event.full_response, style="dim"),
                title="[dim]Claude (Opus)[/]",
                border_style="dim",
                padding=(0, 1),
            ))

    def _on_generating_voice(self, event: GeneratingVoice) -> None:
        self.show_status(Status.GENERATING)

    def _on_voice_generated(self, event: VoiceGenerated) -> None:
        self.clear_status()
        self.show_step("voice generation", event.elapsed)

    def _on_speaking_started(self, event: SpeakingStarted) -> None:
        self.show_status(Status.SPEAKING)

    def _on_speaking_complete(self, event: SpeakingComplete) -> None:
        self.show_step("playback", event.elapsed)

    def _on_response_ready(self, event: ResponseReady) -> None:
        self.clear_status()
        self.show_samantha(event.response)

    def _on_cleared(self, event: ConversationCleared) -> None:
        self.show_info("Conversation cleared.")

    def _on_error(self, event: Error) -> None:
        self.mic.stop()
        self.show_error(event.message)

    def _on_info(self, event: Info) -> None:
        self.show_info(event.message)
