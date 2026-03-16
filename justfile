#!/usr/bin/env just --justfile
# Samantha CLI - Give Claude a voice

set dotenv-load := true

# Modules
[doc('Voice & audio setup')]
mod voice '.justfiles/voice.just'

[doc('Development tasks')]
mod dev '.justfiles/dev.just'

[doc('Installation options')]
mod install '.justfiles/install.just'

[private]
default:
    #!/usr/bin/env bash
    echo "Samantha CLI - Give Claude a voice"
    echo ""
    just --list --unsorted

# Talk to Samantha (full voice mode)
talk:
    uv run samantha

# Talk in text mode (type instead of speak, still hear her voice)
text:
    uv run samantha --text

# Talk in silent mode (type + read, no audio)
silent:
    uv run samantha --text --no-voice

# Resume last conversation
resume *SESSION:
    uv run samantha resume {{SESSION}}

# Show current config
config:
    uv run samantha config

# Set a config value
set KEY VALUE:
    uv run samantha config {{KEY}} {{VALUE}}

# Install/sync dependencies
deps:
    uv sync

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache htmlcov/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
