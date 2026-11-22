# Browser flavour: the base desktop plus Chromium.
# Chromium refuses to run as root without --no-sandbox, so a wrapper supplies the flag; call
# `chromium-desk` instead of `chromium` when you are root inside the container.
ARG BASE=localhost/agent-deskbench/desktop:1
FROM ${BASE}

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      chromium \
      fonts-liberation \
 && rm -rf /var/lib/apt/lists/* \
 && printf '#!/bin/sh\nexec /usr/bin/chromium --no-sandbox --disable-dev-shm-usage "$@"\n' \
      > /usr/local/bin/chromium-desk \
 && chmod +x /usr/local/bin/chromium-desk
