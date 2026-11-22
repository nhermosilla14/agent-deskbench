#!/bin/sh
# Start a bare X desktop and a browser-viewable VNC server.
#   $DESKBENCH_SIZE  screen geometry, e.g. 1600x1000 (default 1600x1000)
set -eu

SIZE="${DESKBENCH_SIZE:-1600x1000}"
export DISPLAY=:1

# X server. RFB stays on the container loopback; websockify is the only published port.
Xvnc "$DISPLAY" \
    -geometry "$SIZE" \
    -depth 24 \
    -SecurityTypes None \
    -localhost no \
    -rfbport 5901 \
    -AlwaysShared \
    -nolisten tcp &

# Window manager: focus, dialogs and decorations.
openbox &

# noVNC + WebSocket bridge on the single published port.
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5901 &

wait
