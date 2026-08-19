"use strict";

const { spawnSync } = require("child_process");
const { existsSync, readFileSync } = require("fs");
const { join } = require("path");

function ok(msg)   { console.log(`  \x1b[32m✓\x1b[0m  ${msg}`); }
function warn(msg) { console.log(`  \x1b[33m!\x1b[0m  ${msg}`); }
function err(msg)  { console.log(`  \x1b[31m✗\x1b[0m  ${msg}`); }

function findSyncScript(cwd) {
  const candidates = [
    join(cwd, "..", "scripts", "sync-platform-memory.sh"),
    join(cwd, "scripts", "sync-platform-memory.sh"),
  ];
  return candidates.find(existsSync) || null;
}

function getOrgRemote(cwd) {
  const configPath = join(cwd, "cruxhive.config.yaml");
  if (!existsSync(configPath)) return null;
  const content = readFileSync(configPath, "utf8");
  const m = content.match(/org_remote\s*:\s*(.+)/);
  return m ? m[1].trim() : null;
}

async function sync(_args) {
  const cwd = process.cwd();
  console.log(`\n\x1b[1mcruxhive sync\x1b[0m`);

  // Try workspace-level sync script first
  const script = findSyncScript(cwd);
  if (script) {
    const r = spawnSync(script, [], { cwd, stdio: "inherit" });
    if (r.status === 0) {
      ok("Org context synced via sync-platform-memory.sh");
    } else {
      err("Sync script exited with non-zero status");
    }
    return;
  }

  // Git-based org remote: disabled. `.llm/` is a subdirectory of the project
  // repo, not a repo of its own, so `git pull --rebase <remote> main` with
  // cwd=.llm walked up and rebased the user's ENTIRE PROJECT onto an unrelated
  // org-context remote. Nothing ever created cruxhive.config.yaml, so this path
  // was unreachable in practice — but it must not be re-enabled as written.
  // A correct implementation clones the org remote to its own directory
  // outside the project tree and copies entries in.
  const remote = getOrgRemote(cwd);
  if (remote) {
    err("Git-based org sync is disabled (it rebased the parent project repo).");
    console.log(`
  Your cruxhive.config.yaml sets org_remote: ${remote}
  Track re-implementation before relying on this path.
`);
    return;
  }

  warn("No sync source configured.");
  console.log(`
  Options:
    1. Workspace sync script at ../scripts/sync-platform-memory.sh
    2. Git-based org sync — disabled pending a safe re-implementation
`);
}

module.exports = { sync };
