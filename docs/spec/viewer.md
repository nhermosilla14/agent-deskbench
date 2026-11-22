# Viewer

Each desktop is reachable from a browser without installing a client, and the URL is stable for the
life of the container.

## Behaviours

### Viewer URL
Every running desktop publishes one HTTP port on the host loopback that serves the noVNC client,
pre-configured to connect and to scale to the window.
- Criteria:
  - `new` and `ls --json` report the URL, and `deskbench url NAME` prints the same string.
  - The URL answers with HTTP 200 and the noVNC page.
  - The port is published on `127.0.0.1` only.
  - The URL contains `autoconnect=1`, so a human does not have to click Connect.
- Tests: tests.test_cli.Desktops.test_viewer_url_serves_novnc, tests.test_cli.Desktops.test_url_verb_matches_ls, tests.test_sessions.Urls.test_viewer_url_autoconnects

## Not supported

- Native VNC/RDP clients: only the web viewer port is published.
- TLS and remote access: the port is loopback-only by design.
