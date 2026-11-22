# The CLI spawns the tray; a lifetime-held flock answers "is it running?"

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

The tray icon must exist exactly while at least one desktop exists: no resident watcher before the
first desktop, no icon and no process after the last one. Something must therefore start the tray at
the moment a desktop is created, and stop it when the last one dies.

A container appearing is not a subscribable event: `podman events` is a stream that notifies only a
reader that is already listening. So either a pre-existing supervisor watches, or the creator
announces.

## Decision

The creator announces. `deskbench new` starts the container, checks whether a tray is alive, and
spawns `deskbench tray` detached (`start_new_session`) when it is not. Liveness is a lock held by the
tray for its entire lifetime on `$XDG_RUNTIME_DIR/deskbench/tray.lock`; the CLI probes it with a
non-blocking `flock`. The lock is the singleton guard and the answer to "is it running?" at once.

The tray stops itself: it watches `podman events` filtered to the label, recounts, and returns from
its main loop at zero. The CLI additionally pokes the tray after `stop` so the common path does not
wait for an event.

No D-Bus activation, no systemd unit, no PID files.

## Alternatives considered

- **D-Bus activation of a `Type=dbus` unit** — removes the spawn code and adds a supervisor, at the
  cost of a unit file, a bus dependency and an activation latency, for the same result.
- **A resident watcher started at login** — violates the requirement that nothing is resident.
- **PID file** — stale after a crash, recycled PIDs produce false positives.

## Consequences

Creation outside the CLI (a raw `podman run`) produces a container with no icon until the next CLI
call; the CLI is documented as the only supported entry point. Two concurrent `new` calls are safe:
the loser blocks on the lock, then reads Podman anyway and renders the truth.
