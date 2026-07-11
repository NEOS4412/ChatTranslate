#!/usr/bin/env bash
# Backward-compat: delegate to scripts/build-book.sh
exec bash "$(dirname "$0")/../scripts/build-book.sh" "$@"
