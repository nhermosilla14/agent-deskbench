# Adapt third-party desktop images

- Status: In progress
- Date: 2026-11-26
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Depends on: 20261126-discover-user-flavours

## Goal

A flavour manifest can describe how a third-party image presents its viewer, which user and
environment it needs, and how to take a screenshot. `deskbench new` accepts the image only when the
full desktop contract works, so an agent never receives a desktop that cannot be viewed or captured.

## Acceptance criteria

- The manifest accepts these adapter sections:
  - `[viewer]`: `port` (default `6080`), `path` (default
    `/vnc.html?autoconnect=1&resize=scale`), `scheme` (`http` or `https`, default `http`), and
    `timeout` in seconds (default `30`).
  - `[run]`: `user` (default `1000:1000`), `entrypoint` (optional argv), `command` (optional argv),
    and `env` (a string map). `{width}` and `{height}` are substituted in environment values.
  - `[screenshot]`: `command` (an argv with `{output}` and `{settle}` placeholders) and `settle`
    (boolean). Built-in images use `/usr/local/bin/deskbench-capture {output} {settle}` with
    `settle = false`; custom commands default to `settle = true`.
- `new` publishes the configured viewer port on `127.0.0.1`, waits for the configured scheme and
  path to answer (2xx, 3xx, 401 or 403), and derives the viewer URL from the host port and path.
- Before reporting success, `new` validates the contract inside the running container: the
  screenshot command writes a non-empty file and `sh -lc true` succeeds. If either fails, it stops
  the container and exits 1 with a message naming the flavour and the missing capability.
- `new` records the effective viewer and screenshot configuration as container labels. `ls`, `url`,
  `shot` and `ask` read those labels, so a desktop keeps the configuration it started with even if
  the manifest changes later.
- `shot` runs the configured command and copies the result to the requested host path. With
  `settle = true` it captures until a still frame is seen, bounded in time; with `settle = false`
  it captures once.
- A bare `--image URI` uses the default contract. If that image cannot satisfy it, `new` fails and
  leaves no container behind.
- `exec` runs as the configured user, and host bind mounts round-trip ownership when that user
  matches the host mapping.
- Tests cover a fixture image with a non-default viewer port and path, custom environment variables
  and a custom screenshot command, through `new`, `url`, `shot` and `exec`.

## Spec changes

- Adds: images / Adapt a third-party image
- Adds: images / Desktop image contract
- Changes: cli / Create a desktop
- Changes: cli / Capture the screen
- Changes: cli / Print the viewer URL

## Out of scope

- Making an image without a screenshot tool viable; `new` refuses it instead.
- Non-HTTP viewers, raw VNC clients, TLS client certificates and automatic entrypoint discovery.
- Publishing images (`20261126-publish-the-built-in-images`).
