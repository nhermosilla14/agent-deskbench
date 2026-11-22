# Browser flavour: the base desktop plus Chromium.
# Chromium refuses to run without a sandbox it cannot get in most containers, so a wrapper supplies
# --no-sandbox; call `chromium-desk` instead of `chromium`.
ARG BASE=localhost/agent-deskbench/desktop:1
FROM ${BASE}

# The base image ends as the unprivileged user; installing needs root again.
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      chromium \
      fonts-liberation \
 && rm -rf /var/lib/apt/lists/* \
 && printf '#!/bin/sh\nexec /usr/bin/chromium --no-sandbox --disable-dev-shm-usage "$@"\n' \
      > /usr/local/bin/chromium-desk \
 && chmod +x /usr/local/bin/chromium-desk
USER 1000
