# Walking skeleton: image, new, url

- Intents: 20261122-create-a-desktop, 20261122-list-and-stop-desktops
- ADRs: 20261122-desktop-image, 20261122-podman-is-the-state-store, 20261122-local-image-build

## Scope

Build the image, start a container, print its URL, list it, stop it. A human opens the URL by hand.
Proves the whole vertical path before any UI exists.

## End-to-end test

`tests/test_cli.py` — new → ls --json contains it → url responds → stop → gone.
