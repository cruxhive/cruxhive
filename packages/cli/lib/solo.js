"use strict";

const { spawnSync } = require("child_process");

async function solo(args) {
  const r = spawnSync("cruxhive-solo", args, { stdio: "inherit" });
  if (r.error) {
    console.error("\n  \x1b[31m✗\x1b[0m  cruxhive-solo not found.");
    console.error("       Install: \x1b[36muv tool install cruxhive-mcp\x1b[0m\n");
    process.exit(1);
  }
  if (r.status !== 0) process.exit(r.status);
}

module.exports = { solo };
