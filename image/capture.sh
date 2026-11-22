#!/bin/sh
# Capture the screen once it is worth capturing.
#
#   deskbench-capture OUT [SETTLE_MS] [BUDGET_MS]
#
# Three phases, sharing one budget:
#   1. wait for a client window the window manager reports as viewable;
#   2. if one exists, wait until the screen differs from the reference frame taken at container
#      start, because a managed window is not a painted window;
#   3. wait for the screen to stop changing, so a half-drawn frame is not captured.
#
# Always writes an image: an empty desktop is a legitimate answer, and an animation that never
# settles must not hang the caller.
set -eu

out=${1:?usage: deskbench-capture OUT [SETTLE_MS] [BUDGET_MS]}
settle=${2:-250}
budget=${3:-6000}
step=100
reference_file=/run/deskbench-blank.md5

fingerprint() {
    xwd -root -silent | md5sum | cut -d' ' -f1
}

any_client() {
    ids=$(xprop -root _NET_CLIENT_LIST 2>/dev/null | sed 's/.*# //' | tr ',' ' ')
    for id in $ids; do
        case "$id" in
            0x*) return 0 ;;
        esac
    done
    return 1
}

spent=0

# Phase 1: is there a client at all? Bounded separately and shorter than the total budget, so a
# screenshot of an empty desktop answers in about two seconds instead of burning the whole wait.
# A listed client is enough to keep going: the window manager registers it before it is mapped.
window_wait=2500
[ "$window_wait" -gt "$budget" ] && window_wait=$budget
while [ "$spent" -lt "$window_wait" ]; do
    any_client && break
    sleep 0.1
    spent=$((spent + step))
done

# Phase 2: has anything been painted over the empty desktop? This is the part that absorbs a slow
# first paint, so it uses whatever is left of the budget.
reference=""
[ -r "$reference_file" ] && reference=$(cat "$reference_file")
if [ -n "$reference" ] && any_client; then
    while [ "$spent" -lt "$budget" ]; do
        [ "$(fingerprint)" != "$reference" ] && break
        sleep 0.1
        spent=$((spent + step))
    done
fi

# Phase 3: has it stopped changing?
previous=""
still=0
while [ "$spent" -lt "$budget" ]; do
    current=$(fingerprint)
    if [ "$current" = "$previous" ]; then
        still=$((still + step))
        [ "$still" -ge "$settle" ] && break
    else
        still=0
        previous=$current
    fi
    sleep 0.1
    spent=$((spent + step))
done

exec scrot -o "$out"
