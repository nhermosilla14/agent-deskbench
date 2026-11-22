# The tray follows the desktops

- Status: In progress
- Date: 2026-11-22
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Depends on: 20261122-create-a-desktop, 20261122-list-and-stop-desktops

## Goal

A tray icon exists exactly while at least one desktop exists, with no process of ours running before
the first desktop and none after the last.

## Acceptance criteria

- The first `new` spawns the tray; a second `new` does not spawn a second one.
- The menu lists every desktop with a submenu that opens its viewer.
- Stopping the last desktop, or its container dying, ends the tray process.
- No `deskbench` process exists when there are no desktops.

## Spec changes

- Adds: lifecycle / tray lifetime
- Adds: lifecycle / single tray instance

## Out of scope

- Autostart after a reboot.
