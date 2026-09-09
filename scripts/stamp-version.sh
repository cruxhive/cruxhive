#!/usr/bin/env bash
# Stamp the released version numbers + test count into docs/index.html and
# CLAUDE.md, read straight from the source of truth (pyproject.toml,
# package.json, pytest). This is exactly the manual step that let the public
# site silently claim "0.12 / 0.12 / 32 tests" for 7+ minor versions while
# 0.19.x/0.20.x had already shipped — run this every release instead of
# hand-editing docs/index.html.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MCP_VERSION=$(grep -m1 '^version' "$ROOT/packages/mcp/pyproject.toml" | sed -E 's/version = "(.*)"/\1/')
CLI_VERSION=$(node -e "console.log(require('$ROOT/packages/cli/package.json').version)")

echo "→ Counting tests (packages/mcp)..."
TEST_COUNT=$(cd "$ROOT/packages/mcp" && uv run --with pytest --with mcp pytest -q --collect-only 2>/dev/null | tail -1 | grep -oE '[0-9]+' | head -1 || true)

if [ -z "$TEST_COUNT" ]; then
  echo "✗ Could not determine test count — leaving the test count in docs/index.html and CLAUDE.md untouched" >&2
fi

INDEX="$ROOT/docs/index.html"
sed -i.bak -E "s#(<b>cruxhive-mcp</b> )[0-9.]+#\1${MCP_VERSION}#" "$INDEX"
sed -i.bak -E "s#(<b>@cruxhive/cli</b> )[0-9.]+#\1${CLI_VERSION}#" "$INDEX"
sed -i.bak -E "s#(cruxhive-mcp <b style=\"color:var\(--accent\)\">)[0-9.]+#\1${MCP_VERSION}#" "$INDEX"
sed -i.bak -E "s#(@cruxhive/cli <b style=\"color:var\(--accent\)\">)[0-9.]+#\1${CLI_VERSION}#" "$INDEX"
if [ -n "$TEST_COUNT" ]; then
  sed -i.bak -E "s#[0-9]+ tests#${TEST_COUNT} tests#g" "$INDEX"
fi
rm -f "$INDEX.bak"

CLAUDEMD="$ROOT/CLAUDE.md"
sed -i.bak -E "s#cruxhive-mcp@[0-9.]+#cruxhive-mcp@${MCP_VERSION}#" "$CLAUDEMD"
sed -i.bak -E "s#@cruxhive/cli@[0-9.]+#@cruxhive/cli@${CLI_VERSION}#" "$CLAUDEMD"
if [ -n "$TEST_COUNT" ]; then
  sed -i.bak -E "s#[0-9]+ pytest tests#${TEST_COUNT} pytest tests#" "$CLAUDEMD"
fi
rm -f "$CLAUDEMD.bak"

echo "✓ Stamped cruxhive-mcp ${MCP_VERSION} / @cruxhive/cli ${CLI_VERSION} / ${TEST_COUNT:-<unchanged>} tests into docs/index.html and CLAUDE.md"
