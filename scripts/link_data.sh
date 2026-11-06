#!/usr/bin/env bash
# Link the organizers' full dataset into ./data (never committed).
# Usage: scripts/link_data.sh /path/to/RETROFIT_AI_PARTICIPANTS_2026
set -euo pipefail

PACK="${1:?usage: scripts/link_data.sh <path-to-RETROFIT_AI_PARTICIPANTS_2026>}"
SRC="$PACK/data/full"

if [ ! -d "$SRC" ]; then
  echo "not found: $SRC" >&2
  exit 1
fi

ln -sfn "$SRC" data
echo "data -> $SRC"
