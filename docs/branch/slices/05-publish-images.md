# Publish the built-in images to GHCR

- Intents: 20261126-publish-the-built-in-images
- ADRs: 20261126-publish-images-to-ghcr
- Depends on: 01

## Scope

A release tag `vX.Y.Z` publishes `desktop`, `desktop-firefox` and `desktop-chromium` with the tags
`:X.Y.Z`, `:X.Y`, `:X`, `:latest` and `:sha-<short>`. A manual run takes the version. Pull requests
build all three without pushing. `scripts/image-tags.sh` is the single implementation of the
version-to-tag mapping, used by the workflow, `task publish` and the tests. `task image` builds the
same three references under `localhost/agent-deskbench`, and `task e2e` uses them.

## Layers touched

- Foundation: `scripts/image-tags.sh`; the publish workflow.
- Services: `Taskfile.yml` targets `image`, `publish` and `e2e`.
- Interface: none in the CLI; the published refs are the ones `01` already resolves.
- Docs: `README.md`, `docs/architecture.md`, and the one-time GHCR visibility step.

## End-to-end test

- `tests/test_publishing.py::Tags.test_semver_mapping` — `scripts/image-tags.sh 1.2.3` yields
  `1.2.3`, `1.2`, `1`, `latest`, and a `sha-` tag; `v1.2.3` yields the same.
- `tests/test_publishing.py::Workflow.test_image_names_and_major_tag_match_the_cli` — the workflow
  builds the same three repositories and the same major tag that `flavours` resolves.
- `tests/test_publishing.py::Workflow.test_pull_requests_build_without_pushing` — the workflow has a
  pull-request build path and no push permission outside the publish job.
- CI proves the image builds on a pull request; the first tagged release proves the push.

## Out of scope

- Multi-architecture manifests, signing, SBOMs, digest pinning automation and Docker Hub.
- Publishing user-defined flavours.
