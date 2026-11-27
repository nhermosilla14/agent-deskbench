# Terminal sessions

`exec` runs one command per call and keeps nothing. A session is a long-lived shell inside the
desktop whose visible pane the agent reads as plain text and types into, and which a human can join
from their own terminal.

## Behaviours

### Starting a session
`deskbench term start NAME --cells WxH [--session S]` starts a detached tmux session that runs `sh`
as a login shell, pins the grid, and returns once tmux answers for it.
- Criteria:
  - The grid is required and validated before the runtime is touched: columns 20–500, rows 5–200;
    malformed or out-of-range values exit 1 naming the problem.
  - The session runs `sh -l` explicitly, not the image's passwd shell, as the user recorded on the
    container at creation.
  - The grid is pinned so an attached client cannot reflow what the agent reads. The pin is read
    back, and a tmux that cannot pin fails with a message naming the limitation instead of starting a
    session whose size would drift.
  - `remain-on-exit` is set in the same tmux invocation, so a shell that exits immediately still
    leaves its pane behind.
  - Several sessions may exist per desktop, `main` by default; a duplicate name exits 1 naming it.
  - An existing session whose shell has exited is reported as ended, with the instruction to read it
    and then `term stop` it; it is never silently replaced.
  - The live capability probe runs first. Without tmux, the command exits 1 naming the flavour, the
    capability and a route that fits that image's package managers, and no message assumes apt.
  - An unknown desktop fails before anything is touched, and the runtime calls are bounded so a
    wedged exec cannot hang the caller.
- Tests: tests.test_term.Grammar.test_accepts_grids_at_the_bounds, tests.test_term.Grammar.test_refuses_grids_out_of_bounds, tests.test_term.Grammar.test_refuses_malformed_grids, tests.test_term.Grammar.test_new_session_sets_remain_on_exit_in_the_same_invocation, tests.test_term.StartFailures.test_missing_tmux_names_the_flavour_and_route_not_a_raw_runtime_error, tests.test_term.StartFailures.test_ad_hoc_image_is_named_by_its_image_only, tests.test_term.StartFailures.test_a_desktop_without_the_flavour_label_names_its_image, tests.test_term.StartFailures.test_session_verbs_are_bounded_by_a_timeout, tests.test_term.Sessions.test_duplicate_session_name_is_refused, tests.test_term.Sessions.test_unknown_desktop_fails_before_anything_runs, tests.test_term.Sessions.test_pin_reads_back_as_manual, tests.test_term.Sessions.test_start_on_an_ended_session_explains_it_and_stop_then_start_works

### Reading the screen
`deskbench term screen NAME [--session S] [--history N]` prints the visible pane as plain text and
nothing else.
- Criteria:
  - The output is the pane a human would be reading: wrapped lines joined, no escape sequences, the
    visible area only by default.
  - `--history N` prepends up to N lines of scrollback above the visible pane.
  - The read is a snapshot: it returns while a program inside waits for input or loops, and never
    blocks on the program.
  - A full-screen program is readable as a frame with its layout intact, which is the point: no
    image, no OCR.
- Tests: tests.test_term.Sessions.test_echo_is_read_back_through_screen, tests.test_term.Sessions.test_history_shows_a_line_that_scrolled_off, tests.test_term.Sessions.test_full_screen_program_is_readable_as_a_frame, tests.test_term.Sessions.test_screen_returns_while_a_program_waits_for_input, tests.test_term.Grammar.test_history_adds_scrollback_start_only_when_asked

### Typing into a session
`deskbench term send NAME [--session S] -- TEXT` types TEXT and presses Enter; `--key KEY` sends one
named key.
- Criteria:
  - TEXT is typed literally, so text that looks like an option is not read as one, and Enter follows
    it.
  - `--key` sends one key such as `C-c`, which is how a prompt is answered, a TUI is driven and a
    foreground program is interrupted.
  - Passing both TEXT and `--key`, or neither, is refused before anything runs.
  - Sending into a session whose shell has exited is refused, naming the session and the exit status
    when tmux reports it, and pointing at `term screen`, `term stop` and `term start`.
- Tests: tests.test_term.Sessions.test_a_prompt_is_answered_through_send, tests.test_term.Grammar.test_text_is_literal_and_cannot_be_read_as_an_option, tests.test_term.Sessions.test_send_to_an_ended_session_names_it_and_its_status, tests.test_term.Grammar.test_exited_message_names_the_session_and_its_status, tests.test_term.Grammar.test_status_is_named_as_unknown_when_tmux_gave_none

### Listing sessions
`deskbench term list NAME [--json]` reports each session's name, grid, attached-client count and
whether its shell has exited.
- Criteria:
  - A desktop with no sessions prints `no term sessions` and an empty JSON array.
  - Each entry carries `name`, `grid`, `attached` and `ended`; an ended session shows as ended rather
    than as an attached count.
  - The keys are part of the interface: renaming one is a breaking change.
  - Sessions belong to their own desktop and only the visible ones are listed; a private shell is
    never one of them.
- Tests: tests.test_term.Sessions.test_list_json_reports_grid_and_attached_count, tests.test_term.Grammar.test_parse_list_reads_each_session_grid_and_attached_count, tests.test_term.Grammar.test_parse_list_reads_a_dead_pane_as_ended, tests.test_term.Grammar.test_parse_list_of_nothing_is_empty, tests.test_tray_menu.Model.test_sessions_belong_to_their_own_desktop

### Stopping a session
`deskbench term stop NAME [--session S]` ends one session and leaves the desktop running.
- Criteria:
  - The session disappears from `term list`; the desktop and its other sessions are untouched.
  - An ended session can be stopped, which is how its pane is cleared.
  - An unknown desktop or session fails with a message naming it.
- Tests: tests.test_term.Sessions.test_stop_ends_one_session_and_leaves_the_desktop, tests.test_term.Sessions.test_stop_clears_an_ended_session

### An ended session keeps its pane
When a session's shell exits — the agent's `exit`, or a human pressing `Ctrl-D` in the shared pane —
the last frame and the exit status stay in the pane until the session is stopped.
- Criteria:
  - `term screen` keeps reading the pane, including tmux's `Pane is dead (status N, …)` line.
  - `term list` reports the session as ended.
  - `term send` refuses, naming the session and its status, and never types into a dead pane.
  - `term start` explains the ended session instead of claiming a duplicate; `term stop` then
    `term start` resumes.
  - Interrupting a foreground program with `Ctrl-C` leaves the shell alive, so the rule is about the
    shell, not the program.
- Tests: tests.test_term.Sessions.test_exit_keeps_the_frame_and_the_session_reports_ended, tests.test_term.Sessions.test_ctrl_c_of_a_foreground_program_leaves_the_session_usable, tests.test_term.Sessions.test_start_on_an_ended_session_explains_it_and_stop_then_start_works, tests.test_term.Grammar.test_parse_pane_status_reads_the_exit_status_only_when_dead, tests.test_term.Grammar.test_retained_message_explains_the_ended_session_to_start, tests.test_term.Grammar.test_ended_message_says_the_session_has_ended

### Attaching from the developer's terminal
`deskbench term attach NAME [--session S]` opens the session in a terminal emulator on the host, on
the same pane the agent reads.
- Criteria:
  - The desktop and the session are validated before anything is spawned, so a wrong name fails in
    the terminal that asked instead of becoming a window that flashes and dies.
  - The emulator is resolved in a documented order (`DESKBENCH_TERMINAL`, `$TERMINAL`,
    `xdg-terminal-exec`, `x-terminal-emulator`, then the common emulators), and each is called with
    its own argument convention. An explicit `DESKBENCH_TERMINAL` that is not installed is an error;
    a stale `$TERMINAL` is skipped.
  - With no emulator available the command exits 1 naming what it looked for.
  - The attach runs as the run user recorded on the container, because the tmux server belongs to
    that user.
  - On a TTY it warns when the host terminal is smaller than the pinned grid, and when the session
    has ended and only its last frame will be shown; then it attaches anyway.
  - `--print` writes the argv it would spawn and spawns nothing. It is a debugging surface, not a
    supported way to reach a desktop.
  - What either side types appears in the other's pane; closing the client detaches and the session
    survives.
- Tests: tests.test_attach.Attach.test_print_shows_the_run_user_and_session_and_spawns_nothing, tests.test_attach.Attach.test_a_real_attach_returns_zero_and_the_emulator_gets_the_command, tests.test_attach.Attach.test_a_missing_session_exits_one_and_no_emulator_runs, tests.test_attach.Attach.test_an_unknown_desktop_exits_one_and_no_emulator_runs, tests.test_attach.Attach.test_an_invalid_session_name_exits_one_before_anything_runs, tests.test_attach.Attach.test_no_emulator_names_what_was_looked_for, tests.test_attach.Attach.test_an_explicit_emulator_that_is_not_installed_is_an_error, tests.test_attach.Attach.test_declared_arguments_are_kept_before_the_command, tests.test_attach.Attach.test_known_emulators_use_their_own_separator, tests.test_attach.Attach.test_an_ended_session_warns_on_a_tty_only, tests.test_attach.Attach.test_a_live_session_does_not_warn_about_ended, tests.test_attach.Live.test_attach_to_a_real_session_and_the_shell_is_not_a_session

### The private shell
`deskbench shell NAME` runs an interactive `sh -l` in the current terminal, as the recorded user,
with no multiplexer.
- Criteria:
  - It appears in neither `term list` nor the tray, so the agent cannot read its screen; it is the
    documented place for a password or a token.
  - It shares everything else with the desktop: files, home, `DISPLAY` and bind mounts.
  - It is not a session: nothing retains it, and `Ctrl-D` or `exit` simply ends it.
- Tests: tests.test_attach.Attach.test_the_private_shell_is_sh_login_with_no_multiplexer, tests.test_attach.Live.test_attach_to_a_real_session_and_the_shell_is_not_a_session

## Not supported

- `term resize`: the grid is fixed for the life of a session, which is what makes reads comparable.
  Resizing would have to be an explicit, agent-visible act.
- Respawning a dead pane (`respawn-pane`): `term stop` then `term start` is the supported route.
- Preventing `Ctrl-D` at the shell: that needs bash's `ignoreeof`, and the contract guarantees only
  `sh`.
- Read-only attach, session recording (asciinema casts), mouse input and colour-preserving capture.
- A terminal window inside the desktop, or a web terminal: the human's terminal is the host's.
- Reading a private shell's screen: by design it is not a session.
- Sessions surviving `stop`: the tmux server dies with the container.
