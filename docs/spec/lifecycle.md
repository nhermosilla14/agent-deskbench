# Lifecycle

The system's most important property: a tray icon exists exactly while a desktop exists, and no
process of ours survives the last desktop.

## Behaviours

### Tray lifetime
The tray process is spawned by the CLI when the first desktop is created and ends when the last one
is gone; the icon follows the process.
- Criteria:
  - `new` leaves a `deskbench tray` process running.
  - Stopping the last desktop ends that process, so the icon disappears with it.
  - A container that dies on its own also ends the tray, without any CLI call.
  - With no desktops, no `deskbench` process exists.
- Tests: tests.test_lifecycle.TrayLifetime.test_2_tray_exits_when_the_last_desktop_is_stopped, tests.test_lifecycle.TrayDiesWithItsContainer.test_1_tray_exits_when_the_container_is_killed, tests.test_lifecycle.TrayDiesWithItsContainer.test_2_container_stops_when_the_x_server_dies

### Single tray instance
At most one tray runs per user session, even when several desktops are created concurrently, and it
works when started from the installed command rather than a checkout.
- Criteria:
  - A second `deskbench tray` exits 0 immediately instead of drawing a second icon.
  - The first one keeps its menu and keeps running while any desktop exists.
  - The lock that proves liveness is released when the process ends.
  - Starting the tray through the installed console script works even when that script lives in an
    isolated environment without PyGObject.
- Tests: tests.test_lifecycle.TrayLifetime.test_1_a_second_tray_refuses_to_start, tests.test_distribution.InstalledEntryPoint.test_installed_command_can_run_the_tray

### Tray menu
The menu describes every desktop and lets the human act on it without the CLI.
- Criteria:
  - Each desktop's submenu lists a Terminals section with every live session and its attached-client
    count, marking a session whose shell has exited as ended, followed by `New terminal…` and
    `Open private shell`.
  - `New terminal…` starts the default session at the configured size when it is absent and then
    attaches; `Open private shell` opens the private shell; both go through the same functions the
    CLI uses, so there is no second implementation.
  - A failure from any action reaches the human as a desktop notification, because the tray has no
    stderr to watch.
  - The menu is rebuilt only when what it displays has changed, so an idle tick leaves it alone.
  - Runtime reads happen off the GUI thread and never overlap, so a slow runtime cannot freeze the
    menu or pile up ticks.
- Tests: tests.test_tray_menu.Model.test_a_desktop_with_no_sessions_offers_none, tests.test_tray_menu.Model.test_two_sessions_are_listed_with_their_attached_counts, tests.test_tray_menu.Model.test_only_listed_sessions_appear_so_a_private_shell_is_never_a_terminal, tests.test_tray_menu.Model.test_sessions_belong_to_their_own_desktop, tests.test_tray_menu.Model.test_the_configured_size_is_carried_into_the_model, tests.test_tray_menu.Model.test_an_ended_session_is_labelled_ended_not_attached, tests.test_tray_menu.Signature.test_identical_content_gives_an_identical_signature, tests.test_tray_menu.Signature.test_a_new_session_changes_it, tests.test_tray_menu.Signature.test_an_attach_count_change_changes_it, tests.test_tray_menu.Signature.test_a_desktop_state_change_changes_it, tests.test_tray_menu.Signature.test_a_session_going_from_alive_to_ended_changes_it, tests.test_tray_menu.Signature.test_a_settings_change_changes_it, tests.test_tray_menu.Signature.test_the_signature_is_hashable
- Unverified: the rendered GTK menu and its callbacks; the content and its rebuild rule are tested as
  data, and the menu was exercised by hand.

## Not supported

- Autostart at login: desktops do not survive a reboot, so there is nothing to show. The optional
  `task autostart` entry exists for the case of a container restored by the runtime.
- Watching for containers created outside the CLI: the CLI is the contract.
