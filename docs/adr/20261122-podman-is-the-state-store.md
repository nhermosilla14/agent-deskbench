# Podman is the only state store

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

The tool must know which desktops exist, what they are called, and which URL serves each. The
obvious implementation keeps a JSON file, a PID file, or a small SQLite database. All three drift:
the file survives a crashed container, the PID belongs to a recycled process, and a second CLI
invocation races the first.

## Decision

Persist nothing. The container runtime is the database:

- a desktop is a container labelled `deskbench=1`;
- its name is the container name with the `deskbench-` prefix removed;
- its viewer URL is derived from `podman port <name> 6080`;
- its state is whatever `podman ps` reports;
- cleanup is `--rm` on the container itself.

The tray reads the same source and re-derives everything on each start and each Podman event.

## Alternatives considered

- **State file under `$XDG_STATE_HOME`** — needs reconciliation against reality, plus locking, plus a
  migration story. It is the classic source of "ghost desktop" bugs.
- **A supervising daemon owning the state** — contradicts the requirement that no process exists
  between sessions.
- **Docker or Podman behind an abstraction layer** — two code paths and two bug surfaces for a tool
  used on one machine.

## Consequences

Listing requires a Podman call (milliseconds, acceptable). Anything that creates containers outside
the CLI is invisible only if it omits the label. The tool is unusable without Podman, which is an
accepted prerequisite.
