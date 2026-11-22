# Build the desktop image locally on first use

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

`deskbench new` needs an image containing `Xvnc`, `openbox` and noVNC. It can come from a registry
(pull), or be built from the Dockerfile in this repository. A registry introduces an account, a
push, a tag discipline and a network dependency for a tool used on one developer's machine. A local
build makes the very first `new` slow and surprising if it is implicit.

## Decision

The image is built locally from `image/Dockerfile` and tagged `localhost/agent-deskbench/desktop:1`.
`deskbench new` builds it when the tag is missing and says so on stderr; `task image` forces a
rebuild. `--image` overrides the reference for experiments. Builds happen through the same Podman
binary as everything else.

## Alternatives considered

- **Pull from a registry** — no account or push pipeline exists, and the image is developer-specific.
- **Build silently inside `new`** — a multi-minute first call with no explanation looks like a hang.
- **Never build; require `task image`** — one more step before the first successful run, and the
  agent would have to be told about it.

## Consequences

The first `new` on a fresh machine needs a Debian mirror and a few minutes. Image changes are visible
in git as a Dockerfile diff, and there is no tag skew between what the repo says and what runs.
