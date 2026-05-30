"use strict";

const { spawnSync } = require("child_process");

async function status(args) {
  const r = spawnSync("cruxhive-status", args, { stdio: "inherit" });
  if (r.error) {
    if (!args.includes("--quiet") && !args.includes("-q")) {
      console.error("\n  \x1b[31m✗\x1b[0m  cruxhive-status not found.");
      console.error("       Install: \x1b[36muv tool install cruxhive-mcp\x1b[0m\n");
    }
    process.exit(1);
  }
  if (r.status !== 0) process.exit(r.status);
}

module.exports = { status };
