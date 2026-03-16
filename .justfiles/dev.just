# Development recipes

[private]
default:
    @just --list --unsorted --justfile {{source_file()}}

# Run samantha with arbitrary args
[no-cd]
run *ARGS:
    uv run samantha {{ARGS}}

# Start Python REPL with project imports
[no-cd]
repl:
    uv run python -c "from samantha import config, voice; import code; code.interact(local=locals())"

# Run with verbose output for debugging
[no-cd]
debug *ARGS:
    uv run python -m samantha.cli {{ARGS}}
