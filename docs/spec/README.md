# Spec index

Areas appear here as behaviour is delivered. Each entry states a behaviour, its acceptance criteria
and the tests that prove it.

| Area | File | Covers |
|---|---|---|
| Command line | [`cli.md`](cli.md) | new, images, ls, url, exec, shot, logs, stop, capabilities, shell |
| Terminal sessions | [`terminal.md`](terminal.md) | term start/screen/send/list/stop/attach, ended panes, the private shell |
| Images | [`images.md`](images.md) | OCI references, built-in and user flavours, manifests, the desktop contract, publishing |
| Viewer | [`viewer.md`](viewer.md) | the one loopback port and the configured viewer URL |
| Lifecycle | [`lifecycle.md`](lifecycle.md) | tray lifetime, single instance, the tray menu |
| Settings | [`settings.md`](settings.md) | the host preferences file and the settings window |
| Handoff | [`handoff.md`](handoff.md) | asking a human and blocking until they answer |
| Runtime | [`runtime.md`](runtime.md) | Podman or Docker, and where they differ |
