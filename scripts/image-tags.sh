#!/bin/sh
# Derive the tags a built-in image is published under from a release version.
#
# Usage: image-tags.sh VERSION [SHA]
#
# VERSION is X.Y.Z, with or without a leading v. The output is one tag per line:
# X.Y.Z, X.Y, X, latest, and sha-<SHA> when a SHA is supplied. The major tag is
# the one the CLI's built-in flavours resolve to. Exits 2 on an invalid version.
set -eu

invalid() {
  echo "image-tags: invalid version '$1': expected X.Y.Z, for example 1.2.3" >&2
  exit 2
}

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 VERSION [SHA]" >&2
  exit 2
fi

version=${1#v}

case $version in
  ''|*[!0-9.]*)
    invalid "$1"
    ;;
esac

# Exactly three parts: the wildcard needs two dots, and the patch check below
# rejects a fourth.
case $version in
  *.*.*)
    ;;
  *)
    invalid "$1"
    ;;
esac

major=${version%%.*}
rest=${version#*.}
minor=${rest%%.*}
patch=${rest#*.}

for part in "$major" "$minor" "$patch"; do
  case $part in
    ''|*[!0-9]*)
      invalid "$1"
      ;;
  esac
done

case $patch in
  *.*)
    invalid "$1"
    ;;
esac

printf '%s\n' "$version" "$major.$minor" "$major" "latest"

if [ "$#" -eq 2 ] && [ -n "$2" ]; then
  printf 'sha-%s\n' "$2"
fi
