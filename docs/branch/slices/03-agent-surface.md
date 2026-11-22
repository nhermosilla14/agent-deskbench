# Agent control surface

- Intents: 20261122-agent-drives-the-desktop
- Depends on: 01

## Scope

`exec`, `shot`, `logs`, with exit-code propagation and useful errors.

## End-to-end test

`tests/test_cli.py` — exec returns the command's output and exit code; shot writes a non-empty PNG;
logs returns text; unknown desktop fails cleanly.
