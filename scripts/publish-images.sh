#!/bin/sh
# Build and push the three built-in images with the tags image-tags.sh derives.
#
# Usage: publish-images.sh REGISTRY VERSION [SHA]
#
# REGISTRY is the prefix the images live under; VERSION is X.Y.Z. SHA defaults to
# the short commit of HEAD. The base is built first, then Firefox and Chromium
# on top of it, and every tag is applied to the already-built image. Uses podman,
# the project's local runtime; the workflow uses Docker independently.
set -eu

usage() {
  echo "usage: $0 REGISTRY VERSION [SHA]" >&2
  exit 2
}

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  usage
fi

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

registry=${1%/}
version=${2#v}

shift 2
if [ "$#" -eq 1 ]; then
  sha=$1
else
  sha=$(git rev-parse --short HEAD)
fi

tags=$(mktemp)
trap 'rm -f "$tags"' EXIT HUP INT TERM

# Validate the version before a single build starts.
./scripts/image-tags.sh "$version" "$sha" >"$tags"

base="$registry/desktop:$version"
podman build -t "$base" image
podman build --build-arg "BASE=$base" -t "$registry/desktop-firefox:$version" image/flavours/firefox
podman build --build-arg "BASE=$base" -t "$registry/desktop-chromium:$version" image/flavours/chromium

publish() {
  name=$1
  built="$registry/$name:$version"
  while IFS= read -r tag; do
    podman tag "$built" "$registry/$name:$tag"
    podman push "$registry/$name:$tag"
  done <"$tags"
}

publish desktop
publish desktop-firefox
publish desktop-chromium
