# Handoff to a human

- Intents: 20261122-ask-a-human
- Depends on: 02

## Scope

`ask`: notification with actions, attention marker for the tray, blocking with timeout.

## End-to-end test

`tests/test_handoff.py` — the notification request is built correctly and the timeout path exits
non-zero; the interactive path is exercised manually because it needs a human.
