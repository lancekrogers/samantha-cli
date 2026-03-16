# Installation recipes

package_name := "samantha-cli"

[private]
default:
    @just --list --unsorted --justfile {{source_file()}}

# Install for development (editable)
[no-cd]
dev:
    uv sync

# Install with all optional providers
[no-cd]
all:
    uv sync --all-extras

# Install whisper extra (local STT)
[no-cd]
whisper:
    uv pip install -e ".[whisper]"

# Install fish extra (Fish Audio TTS)
[no-cd]
fish:
    uv pip install -e ".[fish]"

# Install as global tool via uv
[no-cd]
global:
    uv tool install -e .
    @echo "samantha installed globally"

# Uninstall global tool
[no-cd]
global-uninstall:
    uv tool uninstall {{package_name}}

# Build distribution packages
[no-cd]
build:
    uv build
    @echo "Built packages in dist/"
    @ls -la dist/

# Check system prerequisites
[no-cd]
check:
    #!/usr/bin/env bash
    echo "Checking prerequisites..."
    echo ""
    which claude > /dev/null 2>&1 && echo "claude CLI: OK" || echo "claude CLI: MISSING (install from https://claude.ai/download)"
    which python3 > /dev/null 2>&1 && echo "Python: $(python3 --version)" || echo "Python: MISSING"
    brew list portaudio > /dev/null 2>&1 && echo "portaudio: OK" || echo "portaudio: MISSING (brew install portaudio)"
    uv run python -c "import edge_tts" 2>/dev/null && echo "edge-tts: OK" || echo "edge-tts: MISSING (run: just deps)"
    uv run python -c "import faster_whisper" 2>/dev/null && echo "faster-whisper: OK" || echo "faster-whisper: NOT INSTALLED (optional: just install whisper)"
    uv run python -c "import fishaudio" 2>/dev/null && echo "fish-audio-sdk: OK" || echo "fish-audio-sdk: NOT INSTALLED (optional: just install fish)"
