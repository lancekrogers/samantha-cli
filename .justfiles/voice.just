# Voice & audio setup recipes

[private]
default:
    @just --list --unsorted --justfile {{source_file()}}

# Test mic and speaker with current providers
[no-cd]
test:
    uv run samantha test

# List available TTS voices (filtered to en-US female by default)
[no-cd]
voices:
    uv run samantha voices --locale en-US --gender female

# List all available TTS voices
[no-cd]
voices-all:
    uv run samantha voices

# List voices filtered by locale and gender
[no-cd]
voices-filter LOCALE GENDER:
    uv run samantha voices --locale {{LOCALE}} --gender {{GENDER}}

# Show available TTS/STT providers and status
[no-cd]
providers:
    uv run samantha providers

# Set TTS voice
[no-cd]
set-voice VOICE:
    uv run samantha config tts_voice {{VOICE}}

# Set speech speed (0.5 = slow, 1.0 = normal, 1.5 = fast)
[no-cd]
set-speed SPEED:
    uv run samantha config speech_speed {{SPEED}}

# Switch to Kokoro (local, high quality, default)
[no-cd]
use-kokoro:
    uv run samantha config tts_provider kokoro
    uv run samantha config tts_voice af_heart
    @echo "TTS switched to Kokoro (local, no API key)"

# Switch to edge-tts (free cloud)
[no-cd]
use-edge:
    uv pip install -e ".[edge]"
    uv run samantha config tts_provider edge
    uv run samantha config tts_voice en-US-AriaNeural
    @echo "TTS switched to edge-tts (free cloud)"

# Switch to Fish Audio (requires API key)
[no-cd]
use-fish KEY:
    uv pip install -e ".[fish]"
    uv run samantha config tts_provider fish
    uv run samantha config fish_api_key {{KEY}}
    @echo "TTS switched to Fish Audio"

# Switch STT to local whisper
[no-cd]
use-whisper MODEL="base":
    uv pip install -e ".[whisper]"
    uv run samantha config stt_provider whisper
    uv run samantha config whisper_model {{MODEL}}
    @echo "STT switched to whisper (model: {{MODEL}})"

# Switch STT back to Google (free, cloud)
[no-cd]
use-google-stt:
    uv run samantha config stt_provider google
    @echo "STT switched to Google (free, requires internet)"

# Go fully local (kokoro + whisper)
[no-cd]
go-local MODEL="base":
    uv pip install -e ".[whisper]"
    uv run samantha config tts_provider kokoro
    uv run samantha config tts_voice af_heart
    uv run samantha config stt_provider whisper
    uv run samantha config whisper_model {{MODEL}}
    @echo "Fully local mode: kokoro + whisper (model: {{MODEL}})"
