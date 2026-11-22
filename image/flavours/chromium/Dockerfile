# Browser flavour: the base desktop plus Chromium.
# The wrapper adds --disable-dev-shm-usage only: /dev/shm is 64 MB in a container, which makes
# Chromium flaky on heavy pages. The renderer sandbox stays ON — we run as an unprivileged user, so
# Chromium uses the namespace sandbox.
ARG BASE=localhost/agent-deskbench/desktop:1
FROM ${BASE}

# The base image ends as the unprivileged user; installing needs root again.
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      chromium \
      fonts-liberation \
 && rm -rf /var/lib/apt/lists/* \
 && printf '#!/bin/sh\n# --disable-dev-shm-usage only: keep the renderer sandbox.\nexec /usr/bin/chromium --disable-dev-shm-usage "$@"\n' \
      > /usr/local/bin/chromium-desk \
 && chmod +x /usr/local/bin/chromium-desk
USER 1000
