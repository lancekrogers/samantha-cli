"""Event system for decoupling the conversation engine from the UI.

The engine emits events, the UI subscribes to them. This lets you
swap, reload, or detach the UI without touching the conversation state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# --- Event types ---

@dataclass
class Event:
    """Base event."""


@dataclass
class ReadyForInput(Event):
    """Engine is ready to accept user input."""
    text_mode: bool = False


@dataclass
class UserInput(Event):
    """User said or typed something."""
    text: str = ""


@dataclass
class STTPhase(Event):
    """Speech-to-text phase change (listening, hearing, transcribing)."""
    phase: str = ""
    elapsed: float = 0.0


@dataclass
class ThinkingStarted(Event):
    """Claude is processing."""


@dataclass
class ThinkingComplete(Event):
    """Claude finished thinking."""
    response: str = ""
    full_response: str = ""
    elapsed: float = 0.0


@dataclass
class GeneratingVoice(Event):
    """TTS is generating audio."""


@dataclass
class VoiceGenerated(Event):
    """TTS finished generating audio."""
    path: str = ""
    elapsed: float = 0.0


@dataclass
class SpeakingStarted(Event):
    """Audio playback started."""


@dataclass
class SpeakingComplete(Event):
    """Audio playback finished."""
    response: str = ""
    elapsed: float = 0.0


@dataclass
class ResponseReady(Event):
    """Final response ready to display (text-only or after voice)."""
    response: str = ""
    full_response: str = ""


@dataclass
class ConversationCleared(Event):
    """History was reset."""


@dataclass
class Error(Event):
    """Something went wrong."""
    message: str = ""


@dataclass
class Info(Event):
    """Informational message."""
    message: str = ""


@dataclass
class SessionExit(Event):
    """User is exiting."""


# --- Event Bus ---

EventHandler = Callable[[Event], None]


class EventBus:
    """Simple pub/sub event bus.

    Handlers are called synchronously in registration order.
    Subscribe to a specific event type or to Event for everything.
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = {}

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: type, handler: EventHandler) -> None:
        """Remove a handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def unsubscribe_all(self) -> None:
        """Remove all handlers. Used when hot-reloading the UI."""
        self._handlers.clear()

    def emit(self, event: Event) -> None:
        """Dispatch an event to all matching handlers.

        Handlers registered for the exact event type are called first,
        then handlers registered for the base Event class.
        """
        event_type = type(event)
        for handler in self._handlers.get(event_type, []):
            handler(event)
        # Also fire catch-all handlers registered on Event
        if event_type is not Event:
            for handler in self._handlers.get(Event, []):
                handler(event)
