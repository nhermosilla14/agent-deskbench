# List and stop desktops

- Status: In progress
- Date: 2026-11-22
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Depends on: 20261122-create-a-desktop

## Goal

Any consumer, human or agent, can discover every running desktop and its URL, and can remove one
without leaving anything behind.

## Acceptance criteria

- `ls` prints a human table; `ls --json` prints the same data as JSON.
- `stop` removes the container; stopping the last one leaves no `deskbench` container and no tray.
- Stopping an unknown desktop exits non-zero and names the desktop.

## Spec changes

- Adds: cli / list desktops
- Adds: cli / stop a desktop

## Out of scope

- Bulk operations.
