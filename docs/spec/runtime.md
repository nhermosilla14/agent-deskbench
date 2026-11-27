# Container runtime

The tool drives whichever container runtime is installed. Podman is the default; Docker works with
the same commands.

## Behaviours

### Choose the runtime
`deskbench` uses Podman when it is available and falls back to Docker, and every verb behaves the
same on either.
- Criteria:
  - With both installed, Podman is used.
  - With only Docker installed, Docker is used.
  - `DESKBENCH_RUNTIME` overrides detection and an unavailable choice fails with a clear message.
  - `ps --format json` from either runtime yields the same list, including the labels and the
    viewer port named by `deskbench.viewer.port` (default 6080).
  - The uid mapping uses the flavour's `[run].user`: Podman gets
    `--userns=keep-id:uid=U,gid=G --user U:G`, Docker gets `--user U:G`.
  - The image-existence check uses the form the runtime supports.
- Tests: tests.test_runtime.Detection.test_prefers_podman_when_both_exist, tests.test_runtime.Detection.test_falls_back_to_docker, tests.test_runtime.Detection.test_explicit_choice_wins, tests.test_runtime.Detection.test_nothing_installed_is_reported, tests.test_runtime.Parsing.test_podman_array, tests.test_runtime.Parsing.test_docker_lines, tests.test_runtime.Parsing.test_a_labelled_viewer_port_is_published_and_found, tests.test_runtime.Parsing.test_docker_labels_skip_malformed_entries, tests.test_runtime.Mapping.test_podman_keeps_the_id, tests.test_runtime.Mapping.test_podman_maps_a_configured_user, tests.test_runtime.Mapping.test_docker_uses_a_plain_user, tests.test_runtime.Mapping.test_image_existence_uses_the_right_verb

## Not supported

- Rootless Docker: it maps container uids to subuids, so bind mounts do not round-trip; rootful
  Docker is required.
- Sharing images between the two runtimes; each keeps its own storage.
