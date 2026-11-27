# Keep the pane when the shell exits

- Status: Done
- Intents: 20261127-terminal-sessions
- ADRs: 20261127-sessions-are-tmux-read-as-text
- Depends on: 01

## Scope

A session survives the exit of its shell. The last frame and the exit status stay in the pane until
the session is stopped, so a human pressing `Ctrl-D` in a shared session cannot erase the agent's
transcript, and the agent can read what happened before deciding what to do.

```
deskbench term screen NAME      # keeps working, and shows "Pane is dead (status N)"
deskbench term list NAME        # reports the session as ended
deskbench term send NAME -- …   # refuses, naming the session and its status
deskbench term stop NAME        # clears the ended session
deskbench term start NAME …     # refuses with an explanation while the ended one exists
```

## Layers touched

- Foundation: `remain-on-exit` set in the same tmux invocation that creates the session, so the shell
  cannot exit before the option is on; `#{pane_dead}` and `#{pane_dead_status}` read through the
  list format and a status query.
- Services: `term list` grows an `ended` field (its JSON keys are contract); `send` checks the pane
  before typing; `start` explains an ended session instead of claiming a duplicate; `stop` still
  works because the session itself still exists.
- UI: the tray labels an ended session as ended rather than "0 attached"; `term attach` warns on a
  TTY that the session has ended and only its last frame will be shown.

## End-to-end test

Through the CLI on a container-backed desktop:

- Start a session, `send` `exit`, then: `screen` still returns the frame and the "Pane is dead"
  line; `list --json` reports `ended: true`; `send` fails naming the session; `start` fails with the
  explanation; `stop` then `start` works again.
- The same flow driven by `Ctrl-C` of a foreground program leaves the shell alive and the session
  usable, proving the check is about the pane, not the program.
- Grammar tests without a container: the list parser reads dead panes, and the ended message names
  the session and the status.

## Out of scope

- Restarting a dead pane in place (`respawn-pane`); `stop` then `start` is the supported route.
- Read-only attach, and preventing `Ctrl-D` at the shell (that needs bash's `ignoreeof`, and the
  contract guarantees `sh`).
- Retaining panes across `stop`: the container still takes everything with it.
