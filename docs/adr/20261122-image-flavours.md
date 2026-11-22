# Image flavours: thin Dockerfiles over one base, declared in code

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: cli.md

## Context

The base image is deliberately bare: Debian, X, openbox, the viewer and the X demos. That keeps it
small and predictable, but it means a session that needs a browser pays a network round trip and a
minute of `apt-get` every time — which an agent pays again on the next run, because containers are
`--rm`.

Two shapes were possible: one fat image with everything, or several thin ones. A fat image makes the
common case slower to build and larger to store, and every session inherits tools it never uses.

## Decision

Ship **flavours**: a directory per variant under `image/flavours/<name>/` with a Dockerfile that
builds `FROM ${BASE}` (defaulting to the base tag), plus one entry in `deskbench/flavours.py`.

- Tags are `localhost/agent-deskbench/desktop-<flavour>:1`; base stays `desktop:1`.
- The registry is a literal dict in code, not a directory scan, so it works from an installed copy
  where `image/` is not present. A test asserts every entry's Dockerfile exists and references the
  base tag.
- Building happens on demand in `new --flavour`, base first, and is cached by tag.
- `deskbench images` lists flavours with a summary and whether they are built, so an agent can choose
  without reading the repository.

Shipped: `base`, `firefox` (Firefox ESR), `chromium` (Chromium plus a `chromium-desk` wrapper that
adds `--no-sandbox`, which Chromium requires as root).

## Alternatives considered

- **One image with every browser** — simpler selection, but a much larger pull and build for
  everyone, and version skew between browsers still bites.
- **Discover flavours by scanning `image/flavours/`** — no duplication, but breaks once installed
  outside the checkout and hides the summary text from the agent.
- **Let agents `apt-get install` per session** — the status quo; fine for one run, wasteful across
  many, and it makes the first screenshot of every session depend on the network.
- **Publish images to a registry** — out of scope; the tool is local-only by design.

## Consequences

Each flavour costs one build the first time it is used (a browser is a few hundred MB). A flavour
cannot be changed after the container starts, so an agent must choose before installing anything it
cares about. Adding a flavour is two files and one dict entry, and the test suite fails if they drift.
