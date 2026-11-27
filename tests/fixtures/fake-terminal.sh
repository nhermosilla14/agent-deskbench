#!/bin/sh
# Stands in for a terminal emulator in tests: records the argv it was given and exits.
printf '%s\n' "$@" > "${FAKE_TERMINAL_LOG:?}"
