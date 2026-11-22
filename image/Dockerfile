FROM debian:stable-slim

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    DISPLAY=:1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tigervnc-standalone-server \
      openbox \
      novnc \
      python3-websockify \
      dbus-x11 \
      xterm \
      x11-apps \
      xfonts-base \
      x11-utils \
      scrot \
      procps \
      fonts-dejavu-core \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN fc-cache -f >/dev/null 2>&1 || true

COPY entrypoint.sh /usr/local/bin/deskbench-entrypoint
COPY capture.sh /usr/local/bin/deskbench-capture
RUN chmod +x /usr/local/bin/deskbench-entrypoint /usr/local/bin/deskbench-capture

EXPOSE 6080

ENTRYPOINT ["/usr/local/bin/deskbench-entrypoint"]
