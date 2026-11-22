# Command line

The `deskbench` command is the only supported entry point. Every verb either produces behaviour the
agent can rely on or fails with a message that names what was wrong.

## Behaviours

### Create a desktop
`deskbench new` starts a labelled container and reports it as JSON on stdout, so a caller never has
to parse prose.
- Criteria:
  - stdout is a single JSON object with `name`, `url`, `id` and `state`.
  - `--name` is honoured; without it the first free `deskN` is used.
  - `--size WxH` reaches every new container; invalid sizes are refused before anything starts.
  - `--image` overrides the image reference for that one desktop.
  - `--bind SRC[:DST][:ro]` makes a host path visible inside, repeatable; the destination defaults
    to `/mnt/<basename>` and mounts are read-write unless `:ro` is given.
  - A missing bind source or a relative destination is refused before any container starts.
  - A duplicate name fails with exit 1 and a message naming the desktop.
- Tests: tests.test_cli.Desktops.test_new_reports_a_usable_desktop, tests.test_cli.Failures.test_invalid_name_is_rejected, tests.test_sessions.Names.test_accepts_ordinary_names, tests.test_sessions.Names.test_next_free_name_fills_the_first_gap, tests.test_sessions.Sizes.test_accepts_plausible_geometry, tests.test_cli.BindMounts.test_host_file_is_visible_inside, tests.test_cli.BindMounts.test_writes_round_trip_to_the_host, tests.test_cli.BindMounts.test_read_only_mount_refuses_writes, tests.test_sessions.Binds.test_defaults_to_mnt_and_read_write, tests.test_sessions.Binds.test_explicit_destination_and_read_only, tests.test_sessions.Binds.test_rejects_missing_source, tests.test_sessions.Binds.test_rejects_relative_destination

### List desktops
`deskbench ls` shows every running desktop and its viewer URL, in a table for humans and as JSON for
machines.
- Criteria:
  - `ls --json` is an array of the same objects `new` prints.
  - The list is derived from the runtime, so a container started by a previous process still appears.
  - With no desktops the table says `no desktops` and the JSON is `[]`.
- Tests: tests.test_cli.Desktops.test_ls_json_includes_the_desktop

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
  - An unknown desktop fails before running anything.
- Tests: tests.test_cli.AgentSurface.test_exec_propagates_output_and_exit_code, tests.test_cli.AgentSurface.test_exec_propagates_failure

### Capture the screen
`deskbench shot` writes a PNG of the screen as a human would see it, waiting long enough for the
picture to be worth taking.
- Criteria:
  - `-o PATH` writes exactly there; without it a temp file is used and printed.
  - The file is a valid PNG.
  - A capture issued immediately after launching a window shows that window.
  - `--settle MS` controls how long the screen must stay unchanged.
  - A desktop with no windows returns an image instead of waiting indefinitely.
  - A blank screen produces a blank image rather than an error.
- Tests: tests.test_cli.Capture.test_immediate_shot_after_launch_shows_the_window, tests.test_cli.Capture.test_shot_still_returns_when_nothing_is_drawn, tests.test_cli.AgentSurface.test_shot_writes_a_png

### Read the log
`deskbench logs` prints the tail of the container log.
- Criteria:
  - `-n N` limits the number of lines.
  - The command succeeds for a running desktop.
- Tests: tests.test_cli.AgentSurface.test_logs_returns_something

## Not supported

- Bulk operations and filters; one desktop per invocation keeps the exit code meaningful.
- Creating desktops without Podman; the runtime is a prerequisite, not an implementation detail.
