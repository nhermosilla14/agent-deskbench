# Images

A desktop starts from one OCI image reference. Built-in flavours are published references under a
configurable registry; user flavours are manifests under the config directory; any fully qualified
reference can be run directly. The CLI pulls images and never builds them.

## Behaviours

### Choose a desktop image
`new` resolves one OCI reference and makes it locally available according to the pull policy;
`deskbench images` reports what exists.
- Criteria:
  - `base`, `firefox` and `chromium` resolve to `<registry>/desktop:1`,
    `<registry>/desktop-firefox:1` and `<registry>/desktop-chromium:1`.
  - `<registry>` defaults to `ghcr.io/nhermosilla14/agent-deskbench`, is read from
    `DESKBENCH_REGISTRY` at call time, tolerates trailing slashes, and a blank value is a
    configuration error.
  - `--flavour NAME` and `--image REF` are mutually exclusive; supplying neither selects `base`.
  - `--image` accepts only a fully qualified reference carrying a tag or a `sha256` digest. A short
    name, a missing tag or whitespace is refused before a container starts.
  - `--pull=missing` uses a local image and pulls only when it is absent, `--pull=always` refreshes,
    and `--pull=never` fails when the image is absent. Pull progress goes to stderr; stdout stays
    machine-readable.
  - No CLI path builds an image.
  - `deskbench images` lists name, source, image reference, local presence and summary as a table
    and as JSON.
- Tests: tests.test_flavours.Registry.test_builtin_names_are_the_three_supported_flavours, tests.test_flavours.Registry.test_builtins_resolve_to_the_default_registry, tests.test_flavours.Registry.test_registry_override_is_read_at_call_time, tests.test_flavours.Registry.test_trailing_slashes_are_stripped, tests.test_flavours.Registry.test_blank_registry_is_a_configuration_error, tests.test_flavours.Validation.test_fully_qualified_references_are_accepted, tests.test_flavours.Validation.test_short_names_and_missing_tags_are_rejected, tests.test_images.Arguments.test_defaults_to_base_with_the_missing_pull_policy, tests.test_images.Arguments.test_flavour_and_image_are_mutually_exclusive, tests.test_images.PullPolicy.test_missing_does_not_pull_when_present, tests.test_images.PullPolicy.test_missing_pulls_when_absent, tests.test_images.PullPolicy.test_always_pulls_even_when_present, tests.test_images.PullPolicy.test_never_raises_when_absent, tests.test_images.PullPolicy.test_create_never_runs_a_build, tests.test_images.ImageReferences.test_new_uses_the_local_builtin_ref, tests.test_images.ImageReferences.test_image_flag_runs_a_direct_reference, tests.test_images.ImageReferences.test_pull_never_fails_when_the_image_is_absent, tests.test_images.ImageReferences.test_images_lists_builtin_references, tests.test_images.ImageReferences.test_images_table_carries_refs_and_summaries

### Discover user flavours
A flavour can be added by creating a directory whose manifest names an image, without editing the
project. `deskbench images` reports it and `new --flavour` starts it.
- Criteria:
  - The directory is `DESKBENCH_FLAVOURS_DIR` when set, then
    `$XDG_CONFIG_HOME/agent-deskbench/flavours`, then `~/.config/agent-deskbench/flavours`, and a
    blank override is a configuration error.
  - Each immediate, non-hidden subdirectory containing `flavour.toml` is a flavour; the directory
    name is 1–31 lowercase letters, digits or hyphens.
  - The manifest requires `image` and accepts an optional `summary`. Unknown top-level keys and
    wrong value types are refused with the manifest path.
  - `new --flavour NAME` resolves a user flavour, applies the same pull policy and contract as a
    built-in, and never builds.
  - `images` lists valid user flavours with source `user`, their image, presence and summary, and
    prints `deskbench: ignoring <path>: <reason>` for malformed candidates without hiding the valid
    ones.
  - A user directory named like a built-in is a problem: `images` keeps the built-in and warns,
    while `new` refuses the shadow and names the manifest.
  - A directory without `flavour.toml` is ignored; `--image` remains the anonymous path.
- Tests: tests.test_flavours.Location.test_explicit_directory_beats_xdg_and_home, tests.test_flavours.Location.test_xdg_beats_the_home_default, tests.test_flavours.Location.test_home_default_when_nothing_is_set, tests.test_flavours.Location.test_blank_override_is_a_configuration_error, tests.test_flavours.Discovery.test_valid_manifest_is_a_user_flavour, tests.test_flavours.Discovery.test_summary_defaults_when_absent, tests.test_flavours.Discovery.test_malformed_toml_is_a_problem_and_other_flavours_survive, tests.test_flavours.Discovery.test_missing_image_is_a_problem, tests.test_flavours.Discovery.test_unknown_key_is_a_problem, tests.test_flavours.Discovery.test_directory_without_a_manifest_is_ignored, tests.test_flavours.Discovery.test_shadowing_a_builtin_is_a_problem_and_the_builtin_survives, tests.test_flavours.Discovery.test_get_rejects_a_shadowing_directory, tests.test_flavours.Discovery.test_images_warns_about_shadowing_and_keeps_the_builtin, tests.test_flavours.Discovery.test_new_rejects_a_shadowing_directory_before_creating_a_container, tests.test_images.UserFlavours.test_named_flavour_from_the_config_directory, tests.test_images.UserFlavours.test_malformed_manifest_warns_without_hiding_valid_flavours, tests.test_images.UserFlavours.test_new_fails_for_a_malformed_manifest

### Adapt a third-party image
A manifest can describe where a third-party image presents its viewer, which user and environment
it needs, and how to capture the screen. Defaults reproduce the built-in image.
- Criteria:
  - `[viewer]` accepts `port` (1–65535, default 6080), `path` (default
    `/vnc.html?autoconnect=1&resize=scale`), `scheme` (`http` or `https`, default `http`) and
    `timeout` seconds (default 30).
  - `[run]` accepts `user` (`uid` or `uid:gid`, default `1000:1000`), optional `entrypoint` and
    `command` argv lists, and an `env` table. `{width}` and `{height}` in environment values are
    replaced from `--size`.
  - `[screenshot]` accepts a `command` argv containing `{output}` (and optionally `{settle}`) and a
    `settle` boolean. A custom command defaults `settle` to true; `settle` without a command is an
    error.
  - `new` publishes the configured viewer port on `127.0.0.1`, waits for the configured scheme and
    path (2xx, 3xx, 401 or 403) within the configured timeout, and builds the URL from the host port
    and path.
  - The entrypoint and command follow the image in the runtime arguments; the entrypoint executable
    is passed as `--entrypoint`.
  - The effective viewer port, path, scheme, user and screenshot command are recorded as container
    labels. `ls`, `url`, `exec` and `shot` read them, so editing a manifest cannot mutate a running
    desktop; containers without labels keep the built-in layout.
  - `exec` runs as the configured user.
  - `shot` uses the labelled command, or probes `deskbench-capture`, `scrot` and `import` in that
    order when there is no command. With `settle = false` it captures once; with `settle = true` it
    captures until two consecutive frames match, bounded, and warns if the screen never settles.
  - Unknown keys at the top level or inside a table, and invalid values, are refused.
- Tests: tests.test_flavours.Defaults.test_viewer_defaults_reproduce_the_base_layout, tests.test_flavours.Defaults.test_run_defaults_reproduce_the_base_layout, tests.test_flavours.Defaults.test_screenshot_defaults_leave_resolution_to_the_runtime, tests.test_flavours.Defaults.test_builtins_use_the_builtin_capture_helper, tests.test_flavours.Defaults.test_adhoc_uses_the_default_contract, tests.test_flavours.Schema.test_full_viewer_and_run_tables_are_parsed, tests.test_flavours.Schema.test_partial_tables_keep_the_defaults, tests.test_flavours.Schema.test_unknown_keys_inside_a_table_are_refused, tests.test_flavours.Schema.test_wrong_types_are_refused, tests.test_flavours.Schema.test_viewer_values_are_validated, tests.test_flavours.Schema.test_bad_run_users_are_refused, tests.test_flavours.Schema.test_entrypoint_and_command_items_are_validated, tests.test_flavours.Schema.test_env_is_validated, tests.test_flavours.Schema.test_a_screenshot_command_defaults_to_settle, tests.test_flavours.Schema.test_an_explicit_screenshot_settle_is_kept, tests.test_flavours.Schema.test_a_screenshot_command_must_have_an_output_placeholder, tests.test_flavours.Schema.test_a_screenshot_settle_requires_a_command, tests.test_images.CommandLine.test_the_viewer_port_and_contract_become_flags_and_labels, tests.test_images.CommandLine.test_entrypoint_and_command_follow_the_image, tests.test_images.CommandLine.test_a_user_screenshot_command_becomes_a_compact_label, tests.test_images.CommandLine.test_a_builtin_screenshot_command_is_labelled_with_settle_false, tests.test_images.CommandLine.test_a_flavour_without_a_screenshot_command_omits_the_label, tests.test_images.CommandLine.test_environment_substitutes_the_size, tests.test_images.Adapter.test_custom_viewer_port_path_and_entrypoint, tests.test_images.Adapter.test_custom_environment_and_size_are_applied, tests.test_images.Listing.test_labels_decide_the_url, tests.test_images.Listing.test_a_container_without_labels_keeps_the_default_url, tests.test_images.Listing.test_exec_uses_the_labelled_user, tests.test_images.Listing.test_exec_without_a_label_uses_the_container_default, tests.test_images.ScreenshotCommand.test_the_fallback_chain_returns_the_first_tool_found, tests.test_images.Settle.test_two_identical_frames_end_the_loop, tests.test_images.Settle.test_a_screen_that_never_settles_is_bounded_and_warns, tests.test_runtime.Parsing.test_a_labelled_viewer_port_is_published_and_found, tests.test_runtime.Mapping.test_podman_maps_a_configured_user, tests.test_sessions.Urls.test_custom_scheme_and_path, tests.test_sessions.Urls.test_missing_leading_slash_is_added

### Desktop image contract
An image is viable only if the desktop can be viewed, captured and driven; `new` proves it before
reporting success.
- Criteria:
  - A viable image provides an HTTP(S) viewer on the configured port and path, a screenshot command
    that writes a non-empty file, `sh` for `exec`, and a process user that can be mapped to the
    invoking host user.
  - After the viewer answers, `new` runs `sh -lc true` as the configured user and a real screenshot,
    retrying a starting image a few times.
  - If either probe fails, `new` removes the container, exits 1 and names the flavour and the
    missing capability. A failed viewer timeout is cleaned up the same way.
  - A bare `--image` uses the default contract and the same probes; an image without a known
    screenshot tool is refused.
  - The built-in images use `/usr/local/bin/deskbench-capture {output} {settle}` with
    `settle = false`.
  - tmux is not part of the contract: `new` neither probes, records nor refuses it. The base image
    ships it, so every built-in flavour has a terminal; `capabilities` reports it live, and
    `term start` names the install route when it is missing.
  - `new` records the flavour name as `deskbench.flavour`, so a message about a missing capability
    can name the flavour and its image; a bare `--image` has no flavour name and is named by its
    image alone.
- Tests: tests.test_images.ContractProbe.test_a_missing_shell_is_an_error_naming_the_flavour, tests.test_images.ContractProbe.test_the_shell_probe_runs_as_the_configured_user, tests.test_images.ContractProbe.test_a_failing_screenshot_command_is_an_error_naming_the_capability, tests.test_images.ContractProbe.test_a_flavour_with_no_known_tool_is_refused_and_cleaned_up, tests.test_images.ContractProbe.test_a_failed_new_leaves_no_container, tests.test_images.ContractProbe.test_a_shell_less_viewer_timeout_also_cleans_up, tests.test_images.AdapterScreenshot.test_custom_screenshot_command, tests.test_images.AdapterScreenshot.test_unviable_screenshot_command_is_refused, tests.test_images.AdapterScreenshot.test_default_capture_helper_is_the_fallback, tests.test_term.StartFailures.test_the_flavour_is_recorded_as_a_creation_label, tests.test_term.StartFailures.test_ad_hoc_image_is_named_by_its_image_only, tests.test_term.StartFailures.test_a_desktop_without_the_flavour_label_names_its_image, tests.test_term.StartFailures.test_missing_tmux_names_the_flavour_and_route_not_a_raw_runtime_error

### Publish images
A release publishes the built-in images so a fresh machine can pull them.
- Criteria:
  - `.github/workflows/publish.yml` runs on `v*` tags, manual dispatch with a required version, and
    pull requests touching the image or publish scripts.
  - A release `vX.Y.Z` publishes `desktop`, `desktop-firefox` and `desktop-chromium` with `:X.Y.Z`,
    `:X.Y`, `:X`, `:latest` and `:sha-<short>`. The CLI resolves the `:X` line.
  - The version-to-tag mapping lives only in `scripts/image-tags.sh`, shared by the workflow,
    `task publish` and the tests.
  - The publishing job authenticates with `GITHUB_TOKEN` and `packages: write`; pull requests build
    all three without logging in or pushing.
  - `task publish REGISTRY=... VERSION=...` builds and pushes the same references locally with
    Podman; `task image` builds them locally under `localhost/agent-deskbench` for tests.
- Tests: tests.test_publishing.Tags.test_semver_mapping, tests.test_publishing.Tags.test_v_prefix_is_stripped, tests.test_publishing.Tags.test_sha_adds_a_tag, tests.test_publishing.Tags.test_invalid_versions_are_rejected, tests.test_publishing.PublishScript.test_builds_tags_and_pushes_every_image, tests.test_publishing.Workflow.test_release_and_manual_triggers, tests.test_publishing.Workflow.test_image_names_and_major_tag_match_the_cli, tests.test_publishing.Workflow.test_tags_have_a_single_source, tests.test_publishing.Workflow.test_pull_requests_build_without_pushing, tests.test_publishing.Taskfile.test_publish_task_uses_the_shared_script

## Not supported

- Images with no screenshot tool: `new` refuses them instead of starting a desktop that cannot be
  captured.
- Non-HTTP viewers, raw VNC clients, TLS client certificates and automatic entrypoint discovery
  beyond the manifest.
- Multi-architecture images, signing, SBOMs, Docker Hub and publishing user-defined flavours.
- Automatic viewer-port or screenshot-tool discovery beyond the documented label and fallback rules.
