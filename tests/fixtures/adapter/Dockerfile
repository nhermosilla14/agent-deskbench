# Test fixture: a deskbench-compatible image with a non-default viewer.
#
# The base stack still starts (Xvnc, openbox, the capture helper), but the published viewer is a
# plain HTTP server on port 3000 at "/". The image's default entrypoint is deliberately wrong so a
# manifest must override it. Tests build this as localhost/agent-deskbench/adapter-fixture:1.
FROM localhost/agent-deskbench/desktop:1

USER root
RUN mkdir -p /srv/adapter \
 && printf '<!doctype html><title>adapter</title><h1>adapter viewer</h1>\n' \
      > /srv/adapter/index.html \
 && printf '#!/bin/sh\n/usr/local/bin/deskbench-entrypoint &\nexec python3 -m http.server 3000 --directory /srv/adapter\n' \
      > /usr/local/bin/adapter-entrypoint \
 && printf '#!/bin/sh\nexec /usr/local/bin/deskbench-capture "$1" 0\n' \
      > /usr/local/bin/adapter-shot \
 && chmod +x /usr/local/bin/adapter-entrypoint /usr/local/bin/adapter-shot

USER 1000
EXPOSE 3000
ENTRYPOINT ["/bin/false"]
