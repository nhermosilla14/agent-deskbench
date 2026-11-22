#!/bin/sh
# Start a bare X desktop and a browser-viewable VNC server.
#   $DESKBENCH_SIZE  screen geometry, e.g. 1600x1000 (default 1600x1000)
#
# The X server is the desktop: if it exits, the container exits, so `deskbench ls` never
# reports a running desktop whose screen is gone.
set -eu

SIZE="${DESKBENCH_SIZE:-1600x1000}"
export DISPLAY=:1

# RFB stays on the container loopback; websockify is the only published port.
Xvnc "$DISPLAY" \
    -geometry "$SIZE" \
    -depth 24 \
    -SecurityTypes None \
    -localhost no \
    -rfbport 5901 \
    -AlwaysShared \
    -nolisten tcp &
xvnc_pid=$!

tries=0
while [ ! -S /tmp/.X11-unix/X1 ]; do
    tries=$((tries + 1))
    if [ "$tries" -gt 100 ]; then
        echo "deskbench: Xvnc never created $DISPLAY" >&2
        exit 1
    fi
    sleep 0.1
done

# Window manager: focus, dialogs and decorations.
openbox &

# The first X client in a fresh container pays a one-off cost (client initialisation, font
# caches) and can take seconds to paint. Pay it here, once, so the first real screenshot is not
# a race against the agent.
xclock -geometry 1x1+0+0 >/dev/null 2>&1 &
warmup=$!
sleep 1.5
kill "$warmup" 2>/dev/null || true
sleep 0.3

# Reference frame for "nothing has been painted yet". Captured with an empty desktop, so a later
# capture can tell an undrawn window from a genuinely empty one. /tmp is writable by our user;
# /run is not.
xwd -root -silent 2>/dev/null | md5sum | cut -d' ' -f1 > /tmp/deskbench-blank.md5 || true

# noVNC + WebSocket bridge on the single published port.
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5901 &

wait "$xvnc_pid"
