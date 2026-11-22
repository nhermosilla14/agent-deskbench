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
  - `ps --format json` from either runtime yields the same list, including the viewer port.
  - The uid mapping and the image-existence check use the form the runtime supports.
- Tests: tests.test_runtime.Detection.test_prefers_podman_when_both_exist, tests.test_runtime.Detection.test_falls_back_to_docker, tests.test_runtime.Detection.test_explicit_choice_wins, tests.test_runtime.Detection.test_nothing_installed_is_reported, tests.test_runtime.Parsing.test_podman_array, tests.test_runtime.Parsing.test_docker_lines, tests.test_runtime.Mapping.test_podman_keeps_the_id, tests.test_runtime.Mapping.test_docker_uses_a_plain_user

## Not supported

- Rootless Docker: it maps container uids to subuids, so bind mounts do not round-trip; rootful
  Docker is required.
- Sharing images between the two runtimes; each keeps its own storage.
