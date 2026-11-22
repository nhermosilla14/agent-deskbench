# Podman by default, Docker when that is what is installed

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

The tool was written against Podman, which is the preferred runtime here, but Docker is what many
machines have and what many teams standardise on. The differences are small but they are not
cosmetic: the `ps --format json` shape, the image-existence verb, the events format, and — the one
that matters — how a non-root container user maps to the host uid.

## Decision

A thin adapter, `deskbench/runtime.py`, detects the runtime once per call:

1. `DESKBENCH_RUNTIME` if set (an explicit escape hatch, and how the test suite can pin one),
2. otherwise `podman` if present,
3. otherwise `docker`.

Everything else in the tool speaks the same command surface, because both implement it. The adapter
owns exactly four differences:

| Concern | Podman | Docker |
|---|---|---|
| `ps --format json` | JSON array | one object per line |
| image exists | `image exists` | `image inspect` |
| uid mapping | `--userns=keep-id:uid=1000,gid=1000` | `--user 1000:1000` |
| events format | `--format json` | `--format '{{json .}}'` |

Ports are normalised from either shape: Podman's structured list, or Docker's `127.0.0.1:32768->6080/tcp`
string.

## Alternatives considered

- **Docker only** — the preferred runtime here is Podman, and rootless Podman is a better default.
- **A third-party abstraction (docker-py, podman-py)** — two more dependencies and two more APIs to
  keep in sync for four differences.
- **Separate code paths per runtime** — every command would need two versions and two test matrices.

## Consequences

Docker cannot express keep-id: rootful Docker maps container uid 1000 to host uid 1000, which is
exactly right on a single-user machine with uid 1000, and wrong on anything else. Rootless Docker
needs its own userns-remap configuration and is not supported out of the box; the limitation is
documented rather than hidden. An image built by one runtime is not visible to the other, so switching
runtimes means one rebuild.

The tray must watch the same runtime that created the containers; it inherits `DESKBENCH_RUNTIME`
when the CLI spawns it, so a session stays coherent.
