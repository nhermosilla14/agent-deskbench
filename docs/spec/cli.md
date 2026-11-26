# Command line

The `deskbench` command is the only supported entry point. Every verb either produces behaviour the
agent can rely on or fails with a message that names what was wrong.

## Behaviours

### Create a desktop
`deskbench new` starts a labelled container and reports it as JSON on stdout, so a caller never has
to parse prose.
- Criteria:
  - stdout is a single JSON object with `name`, `url`, `id` and `state`.
  - The command returns only once the viewer answers, so a GUI client launched immediately can
    connect instead of racing the entrypoint.
  - `--name` is honoured; without it the first free `deskN` is used.
  - `--size WxH` reaches every new container; invalid sizes are refused before anything starts.
  - `--flavour NAME` and `--image REF` are mutually exclusive; supplying neither selects `base`.
  - `--pull=missing|always|never` controls whether a missing image is pulled (default `missing`);
    pull progress goes to stderr. No path builds an image.
  - A missing or malformed reference fails with exit 1 before a container starts.
  - Before reporting success, `new` probes `sh -lc true` and a real screenshot as the configured
    user; a failure removes the container and names the flavour and the missing capability.
  - `--bind SRC[:DST][:ro]` makes a host path visible inside, repeatable; the destination defaults
    to `/mnt/<basename>` and mounts are read-write unless `:ro` is given.
  - A missing bind source or a relative destination is refused before any container starts.
  - A duplicate name fails with exit 1 and a message naming the desktop.
- Tests: tests.test_cli.Desktops.test_new_reports_a_usable_desktop, tests.test_cli.Failures.test_invalid_name_is_rejected, tests.test_sessions.Names.test_accepts_ordinary_names, tests.test_sessions.Names.test_next_free_name_fills_the_first_gap, tests.test_sessions.Sizes.test_accepts_plausible_geometry, tests.test_sessions.Binds.test_defaults_to_mnt_and_read_write, tests.test_sessions.Binds.test_explicit_destination_and_read_only, tests.test_sessions.Binds.test_rejects_missing_source, tests.test_sessions.Binds.test_rejects_relative_destination, tests.test_cli.BindMounts.test_host_file_is_visible_inside, tests.test_cli.BindMounts.test_writes_round_trip_to_the_host, tests.test_cli.BindMounts.test_read_only_mount_refuses_writes, tests.test_images.Arguments.test_defaults_to_base_with_the_missing_pull_policy, tests.test_images.Arguments.test_flavour_and_image_are_mutually_exclusive, tests.test_images.ImageReferences.test_new_uses_the_local_builtin_ref, tests.test_images.ImageReferences.test_pull_never_fails_when_the_image_is_absent, tests.test_images.ContractProbe.test_a_failed_new_leaves_no_container

### List desktops
`deskbench ls` shows every running desktop and its viewer URL, in a table for humans and as JSON for
machines.
- Criteria:
  - `ls --json` is an array of the same objects `new` prints.
  - The list is derived from the runtime, so a container started by a previous process still appears.
  - With no desktops the table says `no desktops` and the JSON is `[]`.
  - Each URL comes from the published port and the viewer labels; containers without labels keep
    the built-in noVNC URL.
- Tests: tests.test_cli.Desktops.test_ls_json_includes_the_desktop, tests.test_images.Listing.test_labels_decide_the_url, tests.test_images.Listing.test_a_container_without_labels_keeps_the_default_url

### Stop a desktop
`deskbench stop` removes one desktop without leaving anything behind.
- Criteria:
  - The container is gone and `ls` no longer lists it.
  - Stopping an unknown desktop exits 1 and names it.
  - The stop is prompt enough to be interactive; the tray is notified immediately.
- Tests: tests.test_cli.Failures.test_unknown_desktop_fails_cleanly, tests.test_lifecycle.TrayLifetime.test_2_tray_exits_when_the_last_desktop_is_stopped

### Run a command
`deskbench exec NAME -- CMD` runs a command inside the desktop with a shell, streaming output and
propagating the exit code.
- Criteria:
  - stdout and stderr of the command reach the caller.
  - The command's exit code becomes the CLI's exit code.
  - Commands run as the user recorded on the container; a built-in desktop uses the unprivileged
    `agent` (uid 1000), not root.
  - A third-party flavour may set a different `[run].user`; `exec` uses the labelled value.
  - `sudo` inside needs no password, for the cases where root is genuinely required.
  - An unknown desktop fails before running anything.
- Tests: tests.test_cli.AgentSurface.test_exec_propagates_output_and_exit_code, tests.test_cli.AgentSurface.test_exec_propagates_failure, tests.test_cli.AgentSurface.test_commands_run_as_an_unprivileged_user, tests.test_cli.AgentSurface.test_sudo_is_passwordless, tests.test_images.Listing.test_exec_uses_the_labelled_user, tests.test_images.Listing.test_exec_without_a_label_uses_the_container_default, tests.test_images.Adapter.test_custom_environment_and_size_are_applied

### Capture the screen
`deskbench shot` writes a PNG of the screen as a human would see it, using the screenshot contract
recorded on the container.
- Criteria:
  - `-o PATH` writes exactly there; without it a temp file is used and printed.
  - The file is a valid PNG.
  - The command and settle flag come from the container labels; a flavour without a command uses
    `deskbench-capture`, `scrot` or `import`, in that order.
  - `{output}` and `{settle}` are substituted in the command.
  - `settle = false` captures once; `settle = true` captures until two consecutive frames match,
    bounded, and warns on stderr when the screen never settles. `--settle MS` sets the delay.
  - A desktop whose image has no known screenshot tool exits 1 naming the missing capability.
  - A capture issued immediately after launching a window shows that window.
  - A desktop with no windows returns an image instead of waiting indefinitely.
  - A blank screen produces a blank image rather than an error.
- Tests: tests.test_cli.Capture.test_immediate_shot_after_launch_shows_the_window, tests.test_cli.Capture.test_shot_still_returns_when_nothing_is_drawn, tests.test_cli.AgentSurface.test_shot_writes_a_png, tests.test_images.AdapterScreenshot.test_custom_screenshot_command, tests.test_images.AdapterScreenshot.test_default_capture_helper_is_the_fallback, tests.test_images.ScreenshotCommand.test_placeholders_are_substituted_and_other_text_survives, tests.test_images.Settle.test_two_identical_frames_end_the_loop, tests.test_images.Settle.test_a_screen_that_never_settles_is_bounded_and_warns, tests.test_images.ContractProbe.test_a_flavour_with_no_known_tool_is_refused_and_cleaned_up

### Read the log
`deskbench logs` prints the tail of the container log.
- Criteria:
  - `-n N` limits the number of lines.
  - The command succeeds for a running desktop.
- Tests: tests.test_cli.AgentSurface.test_logs_returns_something

## Not supported

- Bulk operations and filters; one desktop per invocation keeps the exit code meaningful.
- Creating desktops without Podman; the runtime is a prerequisite, not an implementation detail.
