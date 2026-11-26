# Viewer and run adapter

- Intents: 20261126-adapt-third-party-desktops
- ADRs: 20261126-desktop-image-contract
- Depends on: 02

## Scope

A manifest can describe a third-party image's viewer and runtime: `[viewer]` port, path, scheme and
timeout; `[run]` user, entrypoint, command and environment, with `{width}` and `{height}`
substitution. `new` publishes the configured viewer port on `127.0.0.1`, waits for the configured
scheme and path, and derives the URL from them. The effective viewer settings are written as
container labels, and `ls` and `url` read those labels. `exec` uses the configured user. `new`
probes `sh -lc true` and refuses a container that has no shell.

## Layers touched

- Foundation: manifest schema expansion and validation; argv substitution; defaults that reproduce
  the built-in image.
- Services: `create` builds the run arguments (port, user, entrypoint, command, env, labels);
  `wait_ready` uses the configured scheme/path/timeout and status set; `exec_in` uses the user;
  `list_desktops`/`url` read labels.
- Interface: custom viewer URL in `url` and `ls`; clearer errors for an unusable image.
- Tests: a fixture image with a non-default entrypoint, port, path and environment.
- Docs: `docs/architecture.md` (labels as state) and the manifest section of `README.md`.

## End-to-end test

- `tests/test_images.py::Adapter.test_custom_viewer_port_path_and_entrypoint` — the fixture image
  serves HTTP on 3000 at `/`; the manifest overrides the entrypoint; `new` succeeds, `url` points at
  the host port plus `/`, and `exec` runs.
- `tests/test_images.py::Adapter.test_custom_environment_and_size_are_applied` — `exec env` shows
  the manifest values and `{width}`/`{height}` substituted by `--size`.
- `tests/test_images.py::Adapter.test_default_screenshot_still_works` — `shot` on the fixture
  returns a PNG, proving the base stack survives the custom entrypoint.
- Unit coverage: schema defaults and rejections, URL construction, label parsing, argv
  substitution, readiness status handling.

## Out of scope

- A custom screenshot command and `settle` (`04`).
- The screenshot contract probe (`04`).
- Publishing (`05`).
