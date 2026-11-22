# Tray lifecycle

- Intents: 20261122-tray-follows-desktops
- ADRs: 20261122-cli-spawns-tray-with-flock, 20261122-gtk3-appindicator-tray
- Depends on: 01

## Scope

Tray process spawned by `new`, singleton via flock, menu of desktops, exit at zero containers.

## End-to-end test

`tests/test_lifecycle.py` — spawn, second `new` does not double-spawn, stop last, process gone.
The menu itself is verified at the model level; pixels are manual.
