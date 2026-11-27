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
      sudo \
      tmux \
      fonts-dejavu-core \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Everything runs as an ordinary user, so applications behave like they would on a workstation.
# --userns=keep-id:uid=1000 maps this uid to whoever invoked the tool.
RUN useradd --create-home --uid 1000 --shell /bin/bash agent \
 && printf 'agent ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/agent \
 && chmod 0440 /etc/sudoers.d/agent

RUN fc-cache -f >/dev/null 2>&1 || true

COPY entrypoint.sh /usr/local/bin/deskbench-entrypoint
COPY capture.sh /usr/local/bin/deskbench-capture
RUN chmod +x /usr/local/bin/deskbench-entrypoint /usr/local/bin/deskbench-capture

ENV HOME=/home/agent

USER 1000

EXPOSE 6080

ENTRYPOINT ["/usr/local/bin/deskbench-entrypoint"]
