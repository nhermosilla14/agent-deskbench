# Image references and pull policies

- Status: Done
- Intents: 20261126-run-oci-image-flavours
- ADRs: 20261126-flavours-are-oci-image-references
- Depends on: none

## Scope

`deskbench new` resolves a flavour to one OCI image reference and ensures that image is present by
pulling it, never by building. The built-in flavours become references under a configurable
registry. `--image REF` runs a fully qualified reference directly, `--pull` controls the refresh
policy, and `deskbench images` reports refs and local presence. `task image` builds the three
references locally under `localhost/agent-deskbench` for development and tests.

## Layers touched

- Foundation: `deskbench/flavours.py` (built-in refs, registry override, reference validation),
  `deskbench/engine.py` (pull instead of build), removal of the build path.
- Services: `new` passes the resolved image; `images` lists refs and presence; `create` no longer
  defaults to a module-level image.
- Interface: `--image`, `--pull`, mutually exclusive with `--flavour`, pull progress on stderr,
  JSON fields for `images`.
- Docs: `docs/architecture.md` and `README.md` stop describing local builds.

## End-to-end test

- `tests/test_images.py::ImageReferences.test_new_uses_the_local_builtin_ref` — with
  `DESKBENCH_REGISTRY=localhost/agent-deskbench`, `new` starts the locally built base and reports a
  usable desktop.
- `tests/test_images.py::ImageReferences.test_image_flag_runs_a_direct_reference` — `new --image`
  starts the same image without a flavour.
- `tests/test_images.py::ImageReferences.test_pull_never_fails_when_the_image_is_absent` — no
  container is created.
- `tests/test_images.py::ImageReferences.test_images_lists_builtin_references` — the table and JSON
  carry the three refs.
- Unit coverage: reference validation, registry override, tag/digest handling, `--flavour` and
  `--image` mutual exclusion, and a fake runtime that must never receive a `build` call.

## Out of scope

- User flavour directories (`02`).
- Viewer, run and screenshot overrides (`03`, `04`).
- Publishing (`05`).
- Multi-architecture images.
