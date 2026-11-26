# Publish the built-in images to GHCR

- Status: Accepted
- Date: 2026-11-26
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Depends on: 20261126-run-oci-image-flavours

## Goal

The built-in flavours are available from GHCR, so a fresh machine can pull them instead of building
them. A release publishes the base, Firefox and Chromium images the CLI already points at.

## Acceptance criteria

- `.github/workflows/publish.yml` runs on `v*` tags and on `workflow_dispatch`.
- It builds `image/Dockerfile`, then the Firefox and Chromium Dockerfiles with `BASE` set to the
  published base reference.
- A `vX.Y.Z` release publishes `<registry>/desktop:X.Y.Z`, `:X.Y`, `:X`, `:latest` and
  `:sha-<short>`, and the same set for `desktop-firefox` and `desktop-chromium`. The CLI's built-in
  references use `:X` (`:1` today).
- A manual run takes a required `version` input (`X.Y.Z`) and publishes the same tags.
- `scripts/image-tags.sh` derives the tag list from the version; the workflow, `task publish` and
  the test suite all use it.
- It authenticates with `GITHUB_TOKEN` and the `packages: write` permission; no long-lived secrets
  are stored.
- Pull requests build all three images without pushing, so a broken Dockerfile fails CI.
- `task publish REGISTRY=... VERSION=...` performs the same build and push locally. `task image`
  builds the same three references under `localhost/agent-deskbench` for tests, and `task e2e` uses
  those local references.
- A test asserts that the workflow's image names and major tag match the CLI's built-in references,
  and that `scripts/image-tags.sh 1.2.3` yields `1.2.3`, `1.2`, `1`, `latest` and a `sha-` tag.
- `README.md` and `docs/architecture.md` describe publishing, the registry override and the
  one-time step that makes the GHCR packages public.

## Spec changes

- Adds: images / Publish images
- Changes: images / Choose a desktop image

## Out of scope

- Multi-architecture manifests, image signing, SBOMs, digest pinning automation and Docker Hub.
- Publishing user-defined flavours.
