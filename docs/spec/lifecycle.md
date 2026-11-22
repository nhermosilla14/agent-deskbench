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
- Tests: tests.test_lifecycle.TrayLifetime.test_2_tray_exits_when_the_last_desktop_is_stopped, tests.test_lifecycle.TrayDiesWithItsContainer.test_tray_exits_when_the_container_is_killed

### Single tray instance
At most one tray runs per user session, even when several desktops are created concurrently.
- Criteria:
  - A second `deskbench tray` exits 0 immediately instead of drawing a second icon.
  - The first one keeps its menu.
  - The lock that proves liveness is released when the process ends.
- Tests: tests.test_lifecycle.TrayLifetime.test_1_a_second_tray_refuses_to_start

## Not supported

- Autostart at login: desktops do not survive a reboot, so there is nothing to show. The optional
  `task autostart` entry exists for the case of a container restored by the runtime.
- Watching for containers created outside the CLI: the CLI is the contract.
