# Settings

The defaults that belong to the human rather than the agent live in one host file and are edited from
the tray. Settings are preferences, never desktop state: a preference cannot invent, list or outlive a
desktop.

## Behaviours

### The settings file
One TOML file holds the human's preferences, beside the flavour manifests.
- Criteria:
  - It lives at `$XDG_CONFIG_HOME/agent-deskbench/settings.toml`, or `~/.config/agent-deskbench/`
    when the variable is unset. `DESKBENCH_FLAVOURS_DIR` never redirects it.
  - It holds `[term] default_size`, defaulting to `120x40`.
  - An absent, unreadable, non-UTF-8 or corrupt file yields the default instead of an error; a
    directory in its place does the same.
  - A value outside the `--cells` bounds is refused on save, and the stored value is left untouched.
  - Writes are atomic: a temporary file in the same directory, then a rename, with no temporary left
    behind on success or failure.
  - Only `[term]` is written, so a hand-edited file keeps anything else it holds.
- Tests: tests.test_settings.Load.test_absent_file_gives_the_default, tests.test_settings.Load.test_corrupt_file_gives_the_default, tests.test_settings.Load.test_non_utf8_file_gives_the_default, tests.test_settings.Load.test_wrong_types_and_bad_grids_give_the_default, tests.test_settings.Load.test_a_directory_in_place_of_the_file_gives_the_default, tests.test_settings.Save.test_round_trip, tests.test_settings.Save.test_file_holds_only_the_term_table, tests.test_settings.Save.test_invalid_value_is_refused_and_the_stored_one_is_untouched, tests.test_settings.Save.test_no_temporary_file_is_left_behind, tests.test_settings.Save.test_a_failed_replace_leaves_the_old_file_and_no_temporary, tests.test_settings.Save.test_validation_reuses_the_cli_bounds, tests.test_settings.Location.test_xdg_override_is_honoured, tests.test_settings.Location.test_flavours_dir_never_redirects_settings, tests.test_settings.Location.test_defaults_to_home_config_when_xdg_is_unset

### The settings window
The tray's Settings item opens a separate GTK dialog with one field, `Default size for new
terminals`, and Save and Cancel.
- Criteria:
  - It is a separate window, not a menu widget, created once and reused, so it can stay open while
    the indicator menu is dismissed.
  - Save validates the value with the same bounds as `--cells`; an invalid one is shown in the window
    and the stored value is untouched.
  - Closing the window with its own button hides it and the tray keeps running.
  - The stored size applies to the tray's `New terminal…` and to nothing else: `term start` still
    requires `--cells`, and the private shell follows the human's terminal.
  - A failure to save reaches the human as a notification.
- Unverified: the dialog itself. The store and the menu model are covered by tests, but the window
  needs a human to open it once; there is no headless assertion for GTK.

## Not supported

- Any setting other than the default terminal size.
- Per-desktop overrides of a preference.
- Editing settings from the CLI: the window is the human's path, and the CLI stays the agent's
  interface.
