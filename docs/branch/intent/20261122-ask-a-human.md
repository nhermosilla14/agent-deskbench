# Ask a human

- Status: In progress
- Date: 2026-11-22
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Depends on: 20261122-tray-follows-desktops

## Goal

An agent can request a human, naming the desktop and the reason, and block until the human says they
are done, so the agent resumes knowing the intervention finished.

## Acceptance criteria

- `ask NAME MESSAGE` sends a desktop notification with *Open viewer* and *I'm done* actions.
- While waiting, the tray asks for attention; it returns to normal when the human answers.
- Pressing *I'm done* exits 0; reaching the timeout exits non-zero.
- The desktop's viewer URL is included in the notification body.

## Spec changes

- Adds: handoff / request a human

## Out of scope

- Chat, audio or video.
