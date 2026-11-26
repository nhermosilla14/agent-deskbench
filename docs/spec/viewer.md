# Viewer

Each desktop is reachable from a browser without installing a client, and the URL is stable for the
life of the container.

## Behaviours

### Viewer URL
Every running desktop publishes one HTTP(S) viewer port on the host loopback; the URL comes from
the published port and the scheme and path recorded on the container.
- Criteria:
  - `new`, `ls --json` and `deskbench url NAME` agree on the URL.
  - The URL uses the configured scheme and path. The default path is the noVNC client with
    `autoconnect=1` and `resize=scale`.
  - `new` waits for the configured scheme and path to answer 2xx, 3xx, 401 or 403 within the
    configured timeout (default 30 seconds).
  - The port is published on `127.0.0.1` only.
  - Containers without viewer labels, including those created before this behaviour, use the
    built-in noVNC URL.
  - A path is addressed from the root with or without a leading slash.
- Tests: tests.test_cli.Desktops.test_viewer_url_serves_novnc, tests.test_cli.Desktops.test_url_verb_matches_ls, tests.test_sessions.Urls.test_viewer_url_autoconnects, tests.test_sessions.Urls.test_custom_scheme_and_path, tests.test_sessions.Urls.test_missing_leading_slash_is_added, tests.test_images.Listing.test_labels_decide_the_url, tests.test_images.Listing.test_a_container_without_labels_keeps_the_default_url, tests.test_images.Adapter.test_custom_viewer_port_path_and_entrypoint

## Not supported

- Native VNC/RDP clients: only the web viewer port is published.
- Remote access: the port is loopback-only by design. A manifest may select `https` when the image
  serves it.
