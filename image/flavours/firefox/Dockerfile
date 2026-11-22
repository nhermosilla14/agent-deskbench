# Browser flavour: the base desktop plus Firefox ESR.
ARG BASE=localhost/agent-deskbench/desktop:1
FROM ${BASE}

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      firefox-esr \
      fonts-liberation \
 && rm -rf /var/lib/apt/lists/*
