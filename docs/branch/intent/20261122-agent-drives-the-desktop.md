# The agent drives the desktop

- Status: In progress
- Date: 2026-11-22
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Depends on: 20261122-create-a-desktop

## Goal

An agent can run commands inside a desktop, capture what the screen looks like, and read the
container log, without knowing anything about Podman.

## Acceptance criteria

- `exec NAME -- CMD` runs in the desktop and propagates stdout, stderr and the exit code.
- `shot NAME -o PATH` writes a PNG of the current screen; `shot` without `-o` writes a temp file.
- `logs NAME` prints the last lines of the container log.
- Every verb fails with a clear message when the desktop does not exist.

## Spec changes

- Adds: cli / run a command
- Adds: cli / capture the screen
- Adds: cli / read the log

## Out of scope

- Semantic (AT-SPI) automation.
