"""CLI entry point for Samantha.

Provides the main `samantha` command and subcommands.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console

from samantha import __version__
from samantha import config as cfg
from samantha.brain import Brain
from samantha.ui import UI, Status
from samantha.voice import VoiceEngine, TTSError


@click.group(invoke_without_command=True)
@click.option("--text", "-t", is_flag=True, help="Text-only mode (no microphone).")
@click.option("--no-voice", "-n", is_flag=True, help="Disable TTS output.")
@click.version_option(version=__version__, prog_name="samantha")
@click.pass_context
def main(ctx: click.Context, text: bool, no_voice: bool) -> None:
    """Samantha -- Give Claude a voice. Inspired by Her."""
    if ctx.invoked_subcommand is not None:
        return

    _run_assistant(text_mode=text, no_voice=no_voice)


@main.command()
@click.argument("session_id", required=False)
def resume(session_id: str | None) -> None:
    """Resume a past conversation. Uses Claude's session history.

    Without arguments: continues the most recent Claude session.
    With a session ID: resumes that specific Claude session.
    """
    console = Console()
    settings = cfg.load()
    brain = Brain(max_history=settings["max_history"])

    if session_id:
        brain._resume_id = session_id
        console.print(f"  Resuming session {session_id}...", style="green")
    else:
        brain._continue_mode = True
        console.print("  Continuing last session...", style="green")

    console.print()
    _run_assistant(text_mode=False, no_voice=False, brain=brain)


@main.command("test")
def test_audio() -> None:
    """Test your microphone and speaker to verify they work."""
    console = Console()
    settings = cfg.load()
    voice = VoiceEngine(settings)

    console.print("\n  [bold magenta]Samantha Audio Test[/bold magenta]")
    console.print(f"  [dim]TTS: {settings['tts_provider']} | STT: {settings['stt_provider']}[/dim]\n")

    # --- Test 1: Speaker / TTS ---
    console.print("  [bold]1. Testing speaker (TTS)...[/bold]")
    if not voice.tts_available:
        provider = settings["tts_provider"]
        if provider == "fish":
            console.print("  [red]FAIL:[/red] Fish Audio not available (missing API key or package).")
            console.print("  [dim]Fix: samantha config fish_api_key YOUR_KEY[/dim]\n")
        else:
            console.print(f"  [red]FAIL:[/red] TTS provider '{provider}' not available.\n")
    else:
        try:
            voice.speak("Hello! I'm Samantha. Your speaker is working.")
            console.print("  [green]PASS:[/green] Speaker working.\n")
        except Exception as e:
            console.print(f"  [red]FAIL:[/red] {e}\n")

    # --- Test 2: Microphone / STT ---
    console.print("  [bold]2. Testing microphone (STT)...[/bold]")
    if not voice.stt_available:
        provider = settings["stt_provider"]
        if provider == "whisper":
            console.print("  [red]FAIL:[/red] faster-whisper not installed.")
            console.print("  [dim]Fix: uv pip install samantha-cli[whisper][/dim]\n")
        else:
            console.print("  [red]FAIL:[/red] SpeechRecognition or PyAudio not installed.\n")
    else:
        console.print("  [dim]Speak something now (you have 5 seconds)...[/dim]")
        try:
            text = voice.stt.transcribe(timeout=5, phrase_time_limit=5)
            if text:
                console.print(f'  [green]PASS:[/green] Heard: "{text}"\n')
            else:
                console.print("  [yellow]WARN:[/yellow] Heard audio but couldn't understand it.\n")
        except RuntimeError as e:
            console.print(f"  [red]FAIL:[/red] {e}\n")

    console.print("  [bold magenta]Test complete.[/bold magenta]\n")


@main.command("voices")
@click.option("--provider", "-p", default=None, help="TTS provider to list voices for.")
@click.option("--gender", "-g", default="", help="Filter by gender (male/female).")
@click.option("--locale", "-l", default="", help="Filter by locale (e.g. en-US).")
def voices(provider: str | None, gender: str, locale: str) -> None:
    """List available TTS voices for the current provider."""
    console = Console()
    settings = cfg.load()

    if provider:
        settings["tts_provider"] = provider
    voice = VoiceEngine(settings)

    active_provider = settings["tts_provider"]
    console.print(f"\n  [bold magenta]Voices for: {active_provider}[/bold magenta]\n")

    voice_list = voice.tts.list_voices(locale=locale, gender=gender)
    if not voice_list:
        console.print("  [dim]No voices found (provider may not support listing).[/dim]\n")
        return

    for v in voice_list:
        console.print(
            f"  [cyan]{v['name']}[/cyan]  "
            f"{v.get('friendly_name', '')}  "
            f"[dim]{v.get('gender', '')} / {v.get('locale', '')}[/dim]"
        )
    console.print(f"\n  [dim]{len(voice_list)} voices found.[/dim]\n")


@main.command("providers")
def providers() -> None:
    """Show available TTS and STT providers."""
    console = Console()
    settings = cfg.load()

    console.print("\n  [bold magenta]Providers[/bold magenta]\n")

    # TTS
    console.print("  [bold]TTS (text-to-speech):[/bold]")
    tts_active = settings["tts_provider"]
    tts_options = [
        ("kokoro", "kokoro-onnx", "Local, high quality, no API key", _check_import("kokoro_onnx")),
        ("edge", "edge-tts", "Free cloud, no API key", _check_import("edge_tts")),
        ("fish", "fish-audio-sdk", "Paid cloud, custom voice clones", _check_import("fishaudio")),
    ]
    for name, pkg, desc, installed in tts_options:
        marker = "[green]active[/green]" if name == tts_active else ("[dim]ready[/dim]" if installed else "[yellow]not installed[/yellow]")
        install_hint = "" if installed else f"  [dim](uv pip install samantha-cli[{name}])[/dim]"
        console.print(f"    [{marker}] [cyan]{name}[/cyan] — {desc}{install_hint}")

    console.print()

    # STT
    console.print("  [bold]STT (speech-to-text):[/bold]")
    stt_active = settings["stt_provider"]
    stt_options = [
        ("google", "SpeechRecognition", "Free, requires internet", True),
        ("whisper", "faster-whisper", "Local, no internet needed", _check_import("faster_whisper")),
    ]
    for name, pkg, desc, installed in stt_options:
        marker = "[green]active[/green]" if name == stt_active else ("[dim]ready[/dim]" if installed else "[yellow]not installed[/yellow]")
        install_hint = "" if installed else f"  [dim](uv pip install samantha-cli[{name}])[/dim]"
        console.print(f"    [{marker}] [cyan]{name}[/cyan] — {desc}{install_hint}")

    console.print()


@main.command("config")
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key: str | None, value: str | None) -> None:
    """View or set configuration values.

    \b
    Examples:
        samantha config                  # Show all config
        samantha config tts_provider     # Show one value
        samantha config tts_voice en-US-JennyNeural  # Set a value
    """
    console = Console()

    if key is None:
        current = cfg.load()
        console.print("\n  [bold magenta]Samantha Configuration[/bold magenta]")
        console.print(f"  [dim]Config file: {cfg.CONFIG_FILE}[/dim]\n")
        for k, v in current.items():
            display_value = _mask_secret(k, v)
            console.print(f"  [cyan]{k}[/cyan] = {display_value}")
        console.print()
        return

    if value is None:
        current = cfg.load()
        if key in current:
            display_value = _mask_secret(key, current[key])
            console.print(f"  [cyan]{key}[/cyan] = {display_value}")
        else:
            console.print(f"  [red]Unknown key:[/red] {key}")
            console.print(f"  [dim]Available: {', '.join(cfg.DEFAULTS.keys())}[/dim]")
        return

    if key not in cfg.DEFAULTS:
        console.print(f"  [red]Unknown key:[/red] {key}")
        console.print(f"  [dim]Available: {', '.join(cfg.DEFAULTS.keys())}[/dim]")
        return

    default = cfg.DEFAULTS[key]
    if isinstance(default, int):
        value = int(value)
    elif isinstance(default, float):
        value = float(value)

    cfg.set_key(key, value)
    console.print(f"  [green]Set[/green] [cyan]{key}[/cyan] = {_mask_secret(key, value)}")


def _mask_secret(key: str, value) -> str:
    """Mask sensitive config values for display."""
    if "key" in key.lower() and isinstance(value, str) and len(value) > 8:
        return value[:4] + "..." + value[-4:]
    return str(value)


def _check_import(module: str) -> bool:
    """Check if a Python module is importable."""
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def _run_assistant(text_mode: bool = False, no_voice: bool = False, brain: Brain | None = None) -> None:
    """Main conversation loop."""
    ui = UI()
    settings = cfg.load()

    # --- Validate prerequisites ---
    if brain is None:
        brain = Brain(max_history=settings["max_history"])
    if not brain.available:
        ui.show_error(
            "The 'claude' CLI is not installed or not on your PATH.\n"
            "         Install it: https://docs.anthropic.com/en/docs/claude-cli"
        )
        sys.exit(1)

    # --- Initialize voice engine ---
    if no_voice:
        settings["tts_provider"] = "_disabled"
    voice = VoiceEngine(settings)

    # Warn about missing config
    if not text_mode and not voice.stt_available:
        ui.show_error(
            "STT provider not available. Falling back to text mode.\n"
            "         Check: samantha providers"
        )
        text_mode = True

    if not no_voice and not voice.tts_available:
        ui.show_info(
            "TTS provider not available. Running without voice output.\n"
            "         Check: samantha providers"
        )

    # Wire up activity callback so we can see what Claude is doing
    brain._activity_callback = lambda msg: ui.show_info(f"  {msg}")

    # Show active providers
    ui.show_info(f"TTS: {settings['tts_provider']} | STT: {settings['stt_provider']}")

    # --- Start ---
    ui.show_welcome()

    try:
        _conversation_loop(ui, brain, voice, text_mode)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        voice.cleanup()
        ui.show_goodbye()


def _conversation_loop(
    ui: UI,
    brain: Brain,
    voice: VoiceEngine,
    text_mode: bool,
) -> None:
    """Run the listen-think-speak loop until interrupted."""
    import time

    # Wire up STT status callback so UI updates during listen/transcribe
    _stt_status_map = {
        "listening": Status.LISTENING,
        "loading_model": Status.TRANSCRIBING,
        "transcribing": Status.TRANSCRIBING,
    }
    _phase_times: dict[str, float] = {}

    def _on_stt_status(phase: str) -> None:
        now = time.monotonic()
        # Log timing of previous phase
        if _phase_times.get("last_phase"):
            prev = _phase_times["last_phase"]
            elapsed = now - _phase_times.get("last_time", now)
            ui.clear_status()
            ui.show_step(prev, elapsed)
        _phase_times["last_phase"] = phase
        _phase_times["last_time"] = now
        status = _stt_status_map.get(phase, Status.LISTENING)
        ui.show_status(status)

    voice.stt.on_status = _on_stt_status

    while True:
        # --- 1. Get user input ---
        if text_mode:
            try:
                user_input = ui.console.input("  [bold cyan]You:[/bold cyan] ").strip()
            except EOFError:
                break
            if not user_input:
                continue
        else:
            _phase_times.clear()
            t0 = time.monotonic()
            try:
                user_input = voice.listen()
            except KeyboardInterrupt:
                break
            except RuntimeError as e:
                ui.clear_status()
                ui.show_error(str(e))
                ui.show_info("Switching to text mode.")
                text_mode = True
                continue

            # Show final phase timing
            if _phase_times.get("last_phase"):
                elapsed = time.monotonic() - _phase_times.get("last_time", t0)
                ui.clear_status()
                ui.show_step(_phase_times["last_phase"], elapsed)
            else:
                ui.clear_status()

            if user_input is None:
                continue  # Silence or unrecognized -- keep listening

            ui.show_user(user_input)

        # --- Natural language commands ---
        cmd = user_input.strip().lower()

        # Exit
        if cmd in ("exit", "quit", "bye", "goodbye", "stop", "/exit", "/q"):
            break
        exit_phrases = [
            "gotta go", "got to go", "i'm out", "i'm done", "wrap up",
            "talk later", "see you later", "see ya", "good night",
            "signing off", "peace out", "catch you later", "bye samantha",
            "bye bye", "that's all", "we're done", "samantha exit",
            "samantha quit", "samantha bye",
        ]
        if any(cmd == phrase for phrase in exit_phrases):
            break

        # Clear conversation
        if any(phrase in cmd for phrase in [
            "forget everything", "start over", "clear the conversation",
            "fresh start", "new conversation", "reset",
        ]) or cmd in ("/clear", "/c"):
            brain.history.clear()
            brain._first_sent = False
            brain._save_history()
            ui.show_info("Conversation cleared.")
            continue

        # --- 2. Think ---
        ui.show_status(Status.THINKING)
        t0 = time.monotonic()
        try:
            response = brain.think(user_input)
        except (RuntimeError, TimeoutError) as e:
            ui.clear_status()
            ui.show_error(str(e))
            continue

        think_time = time.monotonic() - t0
        ui.clear_status()
        ui.show_step("claude thinking", think_time)

        # --- 3. Respond ---
        # Show full Opus response if it was summarized
        full = getattr(brain, '_full_response', response)
        if full != response and len(full) > len(response):
            from rich.text import Text
            from rich.panel import Panel
            ui.console.print(Panel(
                Text(full, style="dim"),
                title="[dim]Claude (Opus)[/]",
                border_style="dim",
                padding=(0, 1),
            ))

        if voice.tts_available and not text_mode:
            # --- Generate audio ---
            ui.show_status(Status.GENERATING)
            t0 = time.monotonic()
            try:
                audio_path = voice.generate_audio(response)
            except TTSError as e:
                ui.clear_status()
                ui.show_samantha(response)
                ui.show_info(f"Voice output failed: {e}")
                continue

            gen_time = time.monotonic() - t0
            ui.clear_status()
            ui.show_step("voice generation", gen_time)

            # --- Play audio ---
            if audio_path:
                ui.show_status(Status.SPEAKING)
                import threading

                player = threading.Thread(target=voice.play_audio, args=(audio_path,), daemon=True)
                t0 = time.monotonic()
                player.start()

                ui.clear_status()
                ui.show_samantha(response)

                player.join()
                play_time = time.monotonic() - t0
                ui.show_step("playback", play_time)
            else:
                ui.show_samantha(response)
        else:
            ui.show_samantha(response)


if __name__ == "__main__":
    main()
