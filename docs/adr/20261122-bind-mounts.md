# Bind mounts are explicit and passed through to the runtime

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: cli.md

## Context

The bench image is a bare Debian with X tooling. The application under test lives on the host, and
without a mount the only ways in are rebuilding the image or copying files with `podman cp` after
every change — unusable for an edit-run-look loop.

Mounting the current directory automatically would be convenient and wrong: `new` is often run from
a home directory or a monorepo root, and silently exposing it inside a container that the agent also
drives with shell access is a surprising amount of trust to grant by default.

## Decision

`new --bind SRC[:DST][:ro]`, repeatable, explicit. Defaults: destination `/mnt/<basename of SRC>`,
read-write. A read-only mount is one flag away. Paths are validated before the container starts:
the source must exist and the destination must be absolute.

The flag is passed straight through as a `-v` argument. Podman owns the semantics — including
SELinux labelling and rootless uid mapping — and this tool does not try to improve on them.

## Alternatives considered

- **Auto-mount the working directory** — convenient, but a silent trust decision on every run.
- **Copy the tree into the container** — slow, and changes no longer round-trip.
- **Named volumes** — right for persistent state, wrong for "my checkout".
- **A `--workdir` flag with extra behaviour** — not needed; `exec` already takes a command.

## Consequences

An agent can point the desktop at the project and iterate. Rootless Podman maps host ownership into
the container, so files created inside are owned by the invoking user outside. A mount that the
user forgets to remove lives as long as the container, which is destroyed by `stop`.
