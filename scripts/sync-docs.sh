#!/usr/bin/env bash
# Copy the user-facing docs into the cruxhive-mcp package directory so the
# wheel can ship them. Run before `uv build` / `uv publish` whenever
# docs/guide.html changes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${ROOT}/docs/guide.html"
DST="${ROOT}/packages/mcp/cruxhive_mcp/static/guide.html"

if [ ! -f "$SRC" ]; then
  echo "✗ Source not found: $SRC" >&2
  exit 1
fi

mkdir -p "$(dirname "$DST")"
cp "$SRC" "$DST"

src_bytes=$(wc -c < "$SRC" | tr -d ' ')
dst_bytes=$(wc -c < "$DST" | tr -d ' ')
echo "✓ Synced docs/guide.html → packages/mcp/cruxhive_mcp/static/guide.html ($dst_bytes bytes)"
