# Discover user flavours from a config directory

- Status: Accepted
- Date: 2026-11-26
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Depends on: 20261126-run-oci-image-flavours

## Goal

A developer adds a flavour by creating a directory under the user config directory, without editing
code or rebuilding the project. The flavour appears in `deskbench images` and works with
`deskbench new --flavour NAME`.

## Acceptance criteria

- The flavours directory is, in order: `DESKBENCH_FLAVOURS_DIR` when set, then
  `$XDG_CONFIG_HOME/agent-deskbench/flavours`, then `~/.config/agent-deskbench/flavours`.
- Each immediate subdirectory containing a `flavour.toml` is a flavour. The directory name is the
  flavour name and is validated as 1–31 lowercase letters, digits or hyphens.
- A manifest requires `image`, a fully qualified OCI reference with a tag or digest. `summary` is
  optional. Unknown keys are rejected with the file path and the offending key.
- `deskbench new --flavour NAME` resolves a user flavour, applies the same pull policy as a
  built-in, and starts it. No Dockerfile is read or built.
- `deskbench images` lists user flavours with `source` set to `user`, their image reference, local
  presence and summary; the JSON output carries the same fields.
- A user flavour named like a built-in is rejected: `new` fails and names the conflict, while
  `images` reports it on stderr and does not silently replace the built-in.
- A malformed manifest is reported with its path. `images` warns and keeps listing the valid
  flavours; `new --flavour` for that name fails with the parse error.
- A directory without `flavour.toml` is ignored.
- `--image REF` remains the anonymous path: a fully qualified reference runs with no directory and
  no manifest.

## Spec changes

- Adds: images / Discover user flavours
- Changes: images / Choose a desktop image

## Out of scope

- Viewer, run and screenshot overrides (`20261126-adapt-third-party-desktops`).
- Making a user flavour available to other users or committing it to the project.
- Publishing user images.
