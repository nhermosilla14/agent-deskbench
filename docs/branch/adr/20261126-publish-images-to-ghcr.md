# Publish the built-in images to GHCR on release tags

- Status: Accepted
- Date: 2026-11-26
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: images.md

## Context

The CLI now pulls the built-in flavours instead of building them, so the project needs a registry
and a repeatable publisher for `desktop`, `desktop-firefox` and `desktop-chromium`. Until now
publishing was explicitly out of scope: the image was built on the developer's machine and never
left it.

Three forces matter. The images must be reachable without a new account or stored secret. A tag must
mean the same thing tomorrow as it does today, or `new` silently changes behaviour. And a broken
Dockerfile must fail before a release, not during a user's first pull.

## Decision

- Registry: `ghcr.io/nhermosilla14/agent-deskbench`, the default in ADR
  `20261126-flavours-are-oci-image-references`. Forks and tests override it with
  `DESKBENCH_REGISTRY`.
- `.github/workflows/publish.yml` runs on `v*` tags and on `workflow_dispatch`, never on a push to
  `main`. A manual run takes a required `version` input (for example `1.2.3`).
- It builds `image/Dockerfile`, then the Firefox and Chromium Dockerfiles with `BASE` set to the
  published base reference, and publishes the tags derived from the release version `X.Y.Z` for
  each of the three images:
  - `:X.Y.Z` — the exact release, immutable;
  - `:X.Y` — moves within the minor line;
  - `:X` — the major line the CLI uses;
  - `:latest` — the newest release;
  - `:sha-<short>` — the exact commit.
  A `v1.2.3` release therefore publishes `:1.2.3`, `:1.2`, `:1`, `:latest` and `:sha-...` for
  `desktop`, `desktop-firefox` and `desktop-chromium`.
- The version-to-tag mapping lives in `scripts/image-tags.sh`, shared by the workflow,
  `task publish` and the test suite, so the three cannot drift.
- Authentication uses `GITHUB_TOKEN` with `permissions: packages: write`; no long-lived secret is
  stored in the repository.
- Pull requests build all three images without pushing, so a broken Dockerfile fails CI before it
  can reach a release.
- `task publish REGISTRY=... VERSION=...` performs the same build and push locally. `task image`
  builds the same three references under `localhost/agent-deskbench` for development and tests, and
  `task e2e` points `DESKBENCH_REGISTRY` there.
- Documentation covers the one-time manual step that makes the GHCR packages public, and the
  `podman login ghcr.io` needed when a fork keeps them private.

## Alternatives considered

- **Publish on every push to `main`** — a `:main` tag would move constantly, so two machines that
  pull it get different images; release tags keep the moving lines deliberate.
- **Docker Hub** — a separate account and stored credentials for no benefit over the registry that
  is already attached to the repository.
- **Manual `podman push` only** — no guard against a broken Dockerfile and no record of what a
  release contains.
- **`:latest` and `:sha` only** — simple, but there is no major or minor line to pin; a breaking
  change would reach every user at once. The semver lines give them a choice.
- **Only `:1` and `:latest`** — no exact release to pin; `:X.Y.Z` adds reproducibility for the cost
  of one more tag per image.
- **Only immutable `:X.Y.Z` and `:sha` tags** — users would have to edit a reference to upgrade;
  the moving lines keep `new` working without a code change.
- **Multi-architecture, signing and SBOMs now** — real work with no current user; deferred until a
  second architecture or a distribution requirement exists.
- **Publish user-defined flavours too** — the project cannot vouch for images it did not build.

## Consequences

- A release becomes two steps: tag the repository `vX.Y.Z`, then let CI publish. Until the first
  successful release, a fresh machine cannot pull the built-ins; `task image` still provides them
  locally.
- `:X`, `:X.Y` and `:latest` are moving tags; `:X.Y.Z` and `sha-<short>` are immutable. `:X` moves on
  every release within the major line, so built-ins that use `:1` get minor and patch updates.
  `--pull=missing` will not refresh a local copy; `--pull=always` fetches the current tag.
- GHCR packages are private by default even for a public repository. Making them public is a manual
  one-time setting; until then users need to authenticate.
- Each release and each pull request builds three images. Browser images are large, so CI minutes
  and storage are a real cost. A release now adds five tags per image (fifteen in total), which is
  the price of offering exact, minor, major and latest lines.
- Only the platform CI builds for is published (amd64 today); a second architecture is a later
  decision.
- The drift test compares the workflow's image names and major tag with the CLI's references, and
  the shared `scripts/image-tags.sh` is unit-tested with a sample version, so publishing cannot
  quietly stop matching what the CLI pulls.
