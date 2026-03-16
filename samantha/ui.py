"""Rich-powered terminal UI for Samantha.

Provides a clean, minimal display with status indicators
and a scrolling conversation transcript.
"""

from __future__ import annotations

from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


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


class UI:
    """Terminal interface for Samantha.

    Uses Rich for colored output and status indicators.
    Keeps things simple -- prints sequentially rather than
    using Live display, which plays better with audio I/O.
    """

    def __init__(self) -> None:
        self.console = Console()

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
