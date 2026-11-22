# The desktop runs as an unprivileged user mapped to the host uid

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: cli.md

## Context

Everything ran as root inside the container. That works, but it changes the behaviour of the
software under test: browsers require `--no-sandbox`, config lands in `/root`, some toolkits warn or
refuse, and files written into a bind mount come out owned by whoever the container's root maps to.

A non-root user is the obvious fix, but it collides with two other requirements: bind mounts must
round-trip with sane ownership, and `sudo` must remain available for `apt-get`.

## Decision

The image creates `agent` with **uid/gid 1000**, passwordless sudo, and `USER 1000`. The container is
started with `--userns=keep-id:uid=1000,gid=1000`, which maps container uid 1000 to the *invoking
host user*, whatever that uid is, so bind-mounted files keep their ownership in both directions.

Everything in the container — X server, window manager, websockify, the capture helper, the
application — runs as `agent`. Elevated work happens explicitly through `sudo`.

The reference frame and screenshots moved from `/run` (root-owned) to `/tmp`, which the user owns.

## Alternatives considered

- **Stay root, run only `exec` as a different user** — mounts stay owned by container root, so the
  agent cannot write to its own project; the worst of both.
- **`--userns=keep-id` without a matching in-image uid** — breaks when the host uid is not 1000.
- **No `sudo` at all** — safest, but then installing a package means rebuilding an image, which is
  exactly the friction flavours exist to avoid.
- **A rootless-in-container toolkit (rootlesskit, bwrap)** — more moving parts than the problem.

## Consequences

The image is now bound to uid 1000 internally, which `keep-id` translates to whoever runs the tool.
`sudo` inside the container escalates to the namespace root, which is *not* the host root (rootless
Podman), so it cannot change host files it does not already own. Running Chromium still needs
`--no-sandbox` in most containers because the inner sandbox lacks the privileges it expects; the
`chromium-desk` wrapper keeps that working.
