# User flavour discovery

- Status: Done
- Intents: 20261126-discover-user-flavours
- ADRs: 20261126-flavours-are-oci-image-references
- Depends on: 01

## Scope

A flavour can be added by creating
`$XDG_CONFIG_HOME/agent-deskbench/flavours/<name>/flavour.toml` (default `~/.config/...`, overridable
with `DESKBENCH_FLAVOURS_DIR`). The manifest requires `image` and accepts `summary`; unknown keys
are rejected. Discovery validates names, ignores directories without a manifest, rejects names that
shadow a built-in, and reports malformed manifests without taking down the valid ones. `images`
shows the source, and `new --flavour NAME` starts a user flavour with the same pull policy as a
built-in.

## Layers touched

- Foundation: `deskbench/flavours.py` (directory discovery, TOML parsing, name validation,
  collision handling), reuse of the reference validator from `01`.
- Services: `images` origin and warnings on stderr; `new` resolution unchanged.
- Interface: `images` table and JSON `source` field; error messages that name the manifest path.
- Docs: `README.md` flavour section.

## End-to-end test

- `tests/test_images.py::UserFlavours.test_named_flavour_from_the_config_directory` — a temporary
  `DESKBENCH_FLAVOURS_DIR` contains a manifest pointing at the locally built base; `images` lists it
  as `user`, `new --flavour` starts it, and `exec` runs inside it.
- Unit coverage: `DESKBENCH_FLAVOURS_DIR` beats `XDG_CONFIG_HOME`, which beats `~`; invalid names;
  missing `image`; unknown keys; built-in collision; malformed TOML; a directory without a
  manifest is ignored.

## Out of scope

- `[viewer]`, `[run]` and `[screenshot]` (`03`, `04`).
- Publishing user flavours (`05`).
