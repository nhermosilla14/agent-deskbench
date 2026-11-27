# Flavours are OCI image references, not local build recipes

- Replaces: 20261122-image-flavours, 20261122-local-image-build
- Status: Accepted
- Date: 2026-11-26
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: images.md

## Context

The flavour registry is a literal dict of Dockerfiles in `deskbench/flavours.py`. Adding a flavour
means editing the repository, and `new` builds the base and the flavour on first use. That is slow
(the first desktop costs minutes and a Debian mirror), it only works from a checkout where `image/`
exists, and it gives a developer no way to keep a flavour outside the project.

The request is the opposite: put a flavour in a directory in the home directory, and also be able to
run an image that already exists. Those are the same problem once a flavour is seen for what it is:
the choice of which image starts the desktop. A Dockerfile is one way to produce that image, not the
interface the CLI needs.

The project already treats the container runtime as the only state store and the published image as
the unit of distribution. Building in the CLI duplicates what a registry does, worse.

## Decision

A flavour resolves to **one OCI image reference** carrying a tag or a digest.

- Built-in flavours are image references, not recipes:
  - `base` → `<registry>/desktop:1`
  - `firefox` → `<registry>/desktop-firefox:1`
  - `chromium` → `<registry>/desktop-chromium:1`
  - `<registry>` defaults to `ghcr.io/nhermosilla14/agent-deskbench` and is overridable with
    `DESKBENCH_REGISTRY`.
- A user flavour is a directory
  `$XDG_CONFIG_HOME/agent-deskbench/flavours/<name>/flavour.toml` (default
  `~/.config/...`, overridable with `DESKBENCH_FLAVOURS_DIR`). The manifest requires `image` and may
  carry `summary`; the directory name is the flavour name and must be 1–31 lowercase letters,
  digits or hyphens. Built-in names are reserved and a collision is rejected.
- `new --image REF` is the anonymous form of the same model: a fully qualified reference with a tag
  or digest, no directory and no manifest. `--flavour` and `--image` are mutually exclusive;
  supplying neither selects `base`.
- Pulling replaces building. `--pull=missing` (default) uses a local image and pulls only when it is
  absent, `--pull=always` refreshes it, and `--pull=never` fails when it is absent. No CLI path runs
  `podman build`.
- `deskbench images` lists built-ins and user flavours with their source, image reference, local
  presence and summary, as a table and as JSON.
- `image/` and `image/flavours/*` remain the build inputs for the publishing pipeline. `task image`
  builds the three references locally under `localhost/agent-deskbench`; `task e2e` points
  `DESKBENCH_REGISTRY` there.
- The viewer, user, environment and screenshot settings that a flavour may also carry are decided
  by ADR `20261126-desktop-image-contract`; this ADR fixes where the image comes from.

## Alternatives considered

- **Keep the dict and add a scan of `image/flavours/`** — still needs a repository edit for a new
  flavour, still fails from an installed copy, and does not support premade images.
- **Discover Dockerfiles under the config directory** — solves the home-directory request but forces
  a local build and cannot use a published image at all; slower for everyone.
- **One fat image with every tool** — a larger pull for every user, and browser version skew still
  bites.
- **Keep building on first use and add a registry as an option** — two code paths, and user flavours
  would still need the checkout.
- **Short image names and an implicit `latest`** — ambiguous across registries and non-reproducible;
  fully qualified references with a tag or digest avoid both.
- **A VM image instead of OCI** — out of scope in `docs/vision.md`.

## Consequences

- The first `new` on a fresh machine needs network access and pulls hundreds of megabytes for a
  browser. The 15-second success criterion in the vision holds once the image is local; the first
  pull is a one-off cost.
- `:1` is a moving tag, and `:latest` moves with it on every release. `--pull=missing` will not
  refresh either; `--pull=always` does, and the publishing pipeline also adds `:X.Y.Z` and
  `sha-<short>` tags for pinning.
- There is no build cache in the CLI. Maintainers build with `task image` and publish with
  `task publish`; users pull.
- Running an image from a registry executes code the user chose to trust. The contract check in ADR
  `20261126-desktop-image-contract` rejects images that cannot be viewed or captured, but it is not
  a security boundary.
- The two replaced ADRs become `Superseded` and move to `docs/adr/superseded/` when the branch is
  finalized.
