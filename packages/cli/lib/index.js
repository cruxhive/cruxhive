"use strict";

const { spawnSync } = require("child_process");

function ok(msg)  { console.log(`  \x1b[32m✓\x1b[0m  ${msg}`); }
function err(msg) { console.log(`  \x1b[31m✗\x1b[0m  ${msg}`); }

async function index(_args) {
  const cwd = process.cwd();
  console.log(`\n\x1b[1mcruxhive index\x1b[0m`);

  const r = spawnSync("cruxhive-index", [], { cwd, stdio: "inherit" });
  if (r.error) {
    err("cruxhive-index not found — run: pip install cruxhive-mcp");
    process.exit(1);
  }
  if (r.status !== 0) process.exit(r.status);
}

module.exports = { index };
