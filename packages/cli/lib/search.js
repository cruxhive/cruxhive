"use strict";

const { spawnSync } = require("child_process");

/** Format one hit the way propose.js's searchSimilar dedup preview does
 * (`· {path}  [{type}]  {snippet}`), numbered per the front-page mock
 * (docs/index.html) and with a project column in --workspace mode. */
function formatResult(r, i, workspaceMode) {
  const type = r.type || "?";
  const snippet = (r.snippet || "").trim().replace(/\s+/g, " ");
  const project = workspaceMode && r.project ? `\x1b[1m${r.project}\x1b[0m  ` : "";
  const entityTag = r.entity_match ? "  \x1b[36mentity\x1b[0m" : "";
  const num = `${i + 1}.`.padStart(3);
  return `  ${num} ${project}${r.path}  \x1b[90m[${type}]\x1b[0m  ${snippet}${entityTag}`;
}

/** Split --json out of argv without corrupting a query/positional that
 * happens to literally be the string "--json" (a blind `.filter(a => a !==
 * "--json")` stripped EVERY matching token regardless of position, so
 * `cruxhive search "--json" 5` silently dropped the query and only sent
 * `5` to the underlying binary).
 *
 * cruxhive-search's own signature is `[--workspace|-w] <query> [n]` — query
 * is the first token that isn't --workspace/-w, and --json doesn't exist to
 * the Python binary at all (it's JS-only). So: --workspace/-w always pass
 * through untouched, wherever they appear (matches the binary's own
 * position-agnostic handling of those two). The query slot is always filled
 * by the first non-workspace token, even if that token is literally
 * "--json" — only a LATER "--json" (after the query slot is filled) is our
 * own flag, and that's the only one stripped.
 */
function splitArgs(argv) {
  let querySeen = false;
  let jsonMode = false;
  const passthrough = [];
  for (const a of argv) {
    const isWorkspaceFlag = a === "--workspace" || a === "-w";
    if (a === "--json" && querySeen) {
      jsonMode = true;
      continue;
    }
    if (!isWorkspaceFlag) querySeen = true;
    passthrough.push(a);
  }
  return { jsonMode, passthrough };
}

async function search(args) {
  const argv = Array.isArray(args) ? args : [];
  const { jsonMode, passthrough } = splitArgs(argv);
  const workspaceMode = passthrough.includes("--workspace") || passthrough.includes("-w");

  const r = spawnSync("cruxhive-search", passthrough, { stdio: ["ignore", "pipe", "pipe"] });
  if (r.error) {
    console.error("\n  \x1b[31m✗\x1b[0m  cruxhive-search not found.");
    console.error("       Install: \x1b[36muv tool install cruxhive-mcp\x1b[0m\n");
    process.exit(1);
  }

  const stdout = (r.stdout || "").toString();
  const stderr = (r.stderr || "").toString();

  if (jsonMode) {
    // docs/guide.html promises JSON output for scripting — relay stdout
    // byte-for-byte, exactly what `cruxhive-search` itself would print.
    process.stdout.write(stdout);
    if (stderr) process.stderr.write(stderr);
    process.exit(typeof r.status === "number" ? r.status : 0);
    return;
  }

  // cruxhive-search prints usage errors to stderr and non-JSON to stdout in
  // that case (e.g. no args) — surface that clearly instead of trying to
  // JSON.parse an empty string.
  let data;
  try {
    data = JSON.parse(stdout);
  } catch {
    console.error("  \x1b[31m✗\x1b[0m  cruxhive-search produced no parseable output.");
    if (stderr.trim()) console.error(`  ${stderr.trim()}`);
    else if (stdout.trim()) console.error(`  ${stdout.trim()}`);
    process.exit(1);
    return;
  }

  // cruxhive-search still exits 0 on its own {"error": ...} output — the
  // `error` key, not the exit code, is the actual failure signal.
  if (data && !Array.isArray(data) && data.error) {
    console.error(`  \x1b[31m✗\x1b[0m  ${data.error}`);
    process.exit(1);
    return;
  }

  if (!Array.isArray(data) || !data.length) {
    console.log("\n  No results.\n");
    return;
  }

  console.log(
    `\n  ${workspaceMode ? "Searching workspace" : "cruxhive search"} — ${data.length} result(s)\n`
  );
  data.forEach((res, i) => console.log(formatResult(res, i, workspaceMode)));
  console.log("");
}

module.exports = { search };
