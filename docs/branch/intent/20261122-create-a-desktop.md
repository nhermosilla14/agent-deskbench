# Create a desktop

- Status: In progress
- Date: 2026-11-22
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Goal

An agent can turn a containerised graphical desktop, with a viewer URL it can hand to a human, on in
one command, and the result is discoverable by every other part of the system without shared state.

## Acceptance criteria

- `deskbench new` starts a labelled container and prints JSON with `name`, `url`, `id`.
- The URL responds with the noVNC viewer page while the container runs.
- Names are unique; `--name`, `--size` and `--image` are honoured.
- A failed start exits non-zero with the runtime's error on stderr.

## Spec changes

- Adds: cli / create a desktop
- Adds: viewer / viewer url

## Out of scope

- Tray presence (later intent).
- Running the application under test.
