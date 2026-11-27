# Attach from the host, private shell, tray and settings

- Intents: 20261127-host-attach-and-tray
- ADRs: 20261127-humans-attach-from-their-own-terminal,
  20261127-settings-are-host-preferences-edited-by-the-tray
- Depends on: 01

## Scope

A developer can see the live sessions from the tray, join one in their own terminal, open a private
shell, and choose the default size for terminals started from the tray.

```
deskbench term attach NAME [--session S] [--print]
deskbench shell NAME
tray:  <desktop> ▸ Terminals ▸ <session> | New terminal… | Open private shell
tray:  Settings…
```

Delivered end to end: emulator lookup in a documented order with `DESKBENCH_TERMINAL` and `--print`;
desktop and session validation before spawning; `exec -it` as the labelled run user; a warning when
the host terminal is smaller than the pinned grid; a private shell invisible to the agent and the
tray; per-desktop Terminals submenu with attached counts; failures surfaced as notifications; the
menu rebuilt only when its content changed; and a separate GTK settings window with one validated,
atomically stored preference applied to "New terminal…".

## Layers touched

- Foundation: a settings module (XDG path resolution, `tomllib` read, atomic write, defaults, cell
  validation shared with slice 01) and an emulator-lookup module returning an argv, never spawning.
- Services: attach (validate, then spawn detached with no inherited stdio), the private shell, tray
  session listing through the same functions the CLI uses, and a fire-and-forget notification used for
  tray failures.
- UI: the tray menu additions and a `Gtk.Dialog` owned by the tray process, hidden on close so the
  tray outlives it.

## End-to-end test

Through the CLI, with `DESKBENCH_TERMINAL` pointing at a fake two-line emulator script in
`tests/fixtures/`, and `XDG_CONFIG_HOME` pointed at a temporary directory:

- `term attach --print` prints the argv for a real session and spawns nothing; the argv carries the
  run user and the session name.
- `term attach` with the fake emulator returns 0 and leaves the script's recorded argv behind; an
  unknown desktop or session exits 1 before the emulator runs.
- `shell` runs a login shell that `term list` does not report.
- Settings: absent file gives `120x40`; a saved value round-trips; an invalid value is refused and
  leaves the stored one; a corrupt file falls back to the default; the write is atomic (temp file then
  rename) and the path ignores `DESKBENCH_FLAVOURS_DIR`.
- Tray menu as data: a pure builder returns the sessions for a desktop, the two actions, and the
  settings item; unchanged input produces no rebuild. The GTK window itself is checked by hand,
  because the suite runs headless with `DESKBENCH_NO_TRAY=1`.

## Out of scope

- Any setting other than the default terminal size, per-desktop overrides, and editing settings from
  the CLI.
- A terminal window inside the desktop, a web terminal, and attaching several sessions in one call.
- `term resize`.
