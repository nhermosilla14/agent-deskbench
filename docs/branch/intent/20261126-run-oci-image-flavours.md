# Run published OCI images as flavours

- Status: In progress
- Date: 2026-11-26
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Goal

`deskbench new` starts a desktop from an OCI image reference. The built-in flavours (`base`,
`firefox`, `chromium`) are published image references, not local Dockerfile recipes, and the CLI
pulls a missing image instead of building it. A caller can also run any fully qualified image
directly with `--image`.

## Acceptance criteria

- `deskbench new` with no image flag resolves `base` to `<registry>/desktop:1`, where `<registry>`
  defaults to `ghcr.io/nhermosilla14/agent-deskbench` and is overridable with
  `DESKBENCH_REGISTRY`.
- `--flavour firefox` and `--flavour chromium` resolve to `<registry>/desktop-firefox:1` and
  `<registry>/desktop-chromium:1`.
- `--image REF` starts a desktop from any fully qualified OCI reference carrying a tag or digest,
  using the default desktop contract; no manifest is involved.
- `--flavour` and `--image` are mutually exclusive; supplying neither means `base`.
- `--pull=missing` (the default) uses a local image and pulls only when it is absent;
  `--pull=always` pulls before running; `--pull=never` fails when the image is absent. Pull progress
  goes to stderr, not stdout.
- A missing or malformed reference fails with exit 1 before any container starts, and the message
  says what is wrong.
- `deskbench images` lists the built-in flavours with their name, image reference, local presence
  and summary, both as a table and as JSON.
- No CLI path runs a container build. `task image` builds the three built-in references locally
  under `localhost/agent-deskbench` for development and tests, and `task e2e` uses that registry.
- `ls`, `url`, `exec`, `shot`, `logs`, `stop` and `ask` keep working for desktops started from a
  pulled or local image.

## Spec changes

- Adds: images / Choose a desktop image
- Changes: cli / Create a desktop
- Removes: cli / Choose an image flavour

## Out of scope

- User-defined flavour directories and manifests (`20261126-discover-user-flavours`).
- Per-flavour viewer and screenshot adaptation (`20261126-adapt-third-party-desktops`).
- Publishing the images (`20261126-publish-the-built-in-images`).
