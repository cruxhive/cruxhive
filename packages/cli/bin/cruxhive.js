#!/usr/bin/env node
"use strict";

const { init }   = require("../lib/init");
const { sync }   = require("../lib/sync");
const { health } = require("../lib/health");
const { ui }     = require("../lib/ui");

const [, , cmd, ...args] = process.argv;

const commands = { init, sync, health, ui };

if (!cmd || cmd === "--help" || cmd === "-h") {
  console.log(`cruxhive v${require("../package.json").version}

Usage: cruxhive <command>

Commands:
  init      Bootstrap CruxHive in the current project
  sync      Sync org-layer context from the configured remote
  health    Show knowledge base health summary
  ui        Open the approval queue dashboard (localhost:3847)

Options:
  --help    Show this help message
`);
  process.exit(0);
}

const fn = commands[cmd];
if (!fn) {
  console.error(`Unknown command: ${cmd}\nRun cruxhive --help for usage.`);
  process.exit(1);
}

fn(args).catch((err) => {
  console.error(`\nError: ${err.message}`);
  process.exit(1);
});
