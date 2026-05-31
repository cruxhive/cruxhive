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

  // Try git-based org remote (Phase 4 pattern)
  const remote = getOrgRemote(cwd);
  if (remote) {
    console.log(`  Pulling org context from: ${remote}`);
    const r = spawnSync("git", ["pull", "--rebase", remote, "main"], {
      cwd: join(cwd, ".llm"),
      stdio: "inherit",
    });
    if (r.status === 0) {
      ok("Org context synced from remote");
    } else {
      err("git pull failed — check your org_remote in cruxhive.config.yaml");
    }
    return;
  }

  warn("No sync source configured.");
  console.log(`
  Options:
    1. Workspace sync script at ../scripts/sync-platform-memory.sh
    2. Set org_remote in cruxhive.config.yaml for git-based org sync
    3. Use Mozbridge for managed cloud sync (Phase 6)
`);
}

module.exports = { sync };
