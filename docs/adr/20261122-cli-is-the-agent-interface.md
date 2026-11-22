# The CLI is the agent's interface, and the only supported entry point

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

An agent operating this tool needs to create desktops, run the application under test, capture the
screen, read logs and ask a human for help. It could reach the same capabilities through an MCP
server, a Python library, a D-Bus service or raw `podman` commands. Each of those is another
interface to document, version and keep in sync with the CLI.

The agent's existing tool surface is a shell. Anything callable from a shell is immediately usable,
scriptable and testable, and the same commands work in CI where no panel and no agent exist.

## Decision

`deskbench` (the CLI) is the agent's interface and the only supported way to create a desktop. It
prints machine-readable JSON on `new` and on `ls --json`, and reserves stdout for that data. Adding
an MCP wrapper later is allowed but it must call the same module; it must not reimplement behaviour.

Verbs: `new`, `ls`, `url`, `exec`, `shot`, `logs`, `stop`, `ask`, plus a hidden `tray` verb used by
the CLI itself.

## Alternatives considered

- **MCP server first** — best ergonomics for one harness, invisible to every other consumer,
  including a plain terminal and CI.
- **Python library only** — forces every consumer to write Python.
- **Raw Podman commands in the agent's instructions** — leaks container details into prompts and
  skips the tray lifecycle.

## Consequences

Agents must be told the CLI exists (documented in `README.md`). The quality bar for the CLI is the
product's quality bar: exit codes, JSON shapes and error messages matter as much as behaviour. A
future MCP layer costs roughly fifty lines and no new logic.
