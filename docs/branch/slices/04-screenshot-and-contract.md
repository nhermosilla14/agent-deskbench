# Screenshot adapter and the full contract

- Intents: 20261126-adapt-third-party-desktops
- ADRs: 20261126-desktop-image-contract
- Depends on: 03

## Scope

A manifest can describe how to capture the screen: `[screenshot]` command with `{output}` and
`{settle}` placeholders, and `settle` to capture until the frame stops changing. `shot` uses the
command and settings stored in the container labels. `new` probes both the screenshot command and
the shell before reporting success; if either fails, it stops the container and exits 1 naming the
flavour and the missing capability. A bare `--image` uses the default contract and the same probe.

## Layers touched

- Foundation: screenshot command substitution, settle loop, defaults.
- Services: `shot` reads labels and runs the command; `create` validates the contract and cleans up;
  `new` reports the failure.
- Interface: `shot` errors that distinguish a missing screenshot tool from a bad path; `new`
  failures that leave no container.
- Tests: the fixture image gains a custom screenshot command; a second manifest uses a command that
  always fails.
- Docs: the contract section of `README.md` and `docs/architecture.md`.

## End-to-end test

- `tests/test_images.py::AdapterScreenshot.test_custom_screenshot_command` — the manifest points at
  a wrapper around `deskbench-capture`; `shot` writes a valid PNG.
- `tests/test_images.py::AdapterScreenshot.test_unviable_screenshot_command_is_refused` — the
  manifest uses `/bin/false`; `new` exits 1, names the capability, and `ls` has no desktop.
- Unit coverage: `{output}`/`{settle}` substitution, settle convergence and its bound, label
  round-trip, default contract for `--image`, and a runtime failure after the viewer is ready.

## Out of scope

- Images with no screenshot tool; they are refused.
- Non-HTTP viewers and TLS client certificates.
- Publishing (`05`).
