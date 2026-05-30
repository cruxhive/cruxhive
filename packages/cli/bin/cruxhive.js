#!/usr/bin/env node
"use strict";

const { init }    = require("../lib/init");
const { sync }    = require("../lib/sync");
const { health }  = require("../lib/health");
const { ui }      = require("../lib/ui");
const { index }   = require("../lib/index");
const { propose } = require("../lib/propose");
const { review }  = require("../lib/review");
const { stats }   = require("../lib/stats");
const { digest }  = require("../lib/digest");
const { status }  = require("../lib/status");
const { doctor } = require("../lib/doctor");

const [, , cmd, ...args] = process.argv;

const commands = { init, sync, health, ui, index, propose, review, stats, digest, status, doctor };

if (!cmd || cmd === "--help" || cmd === "-h") {
  console.log(`cruxhive v${require("../package.json").version}

Usage: cruxhive <command>

Commands:
  init      Bootstrap CruxHive in the current project
  index     Index .llm/ markdown files into the local knowledge base
  propose   Propose a new knowledge entry for human review
  review    Interactively approve or reject pending proposals
  sync      Sync org-layer context from the configured remote
  health    Show knowledge base health summary
  stats     Usage observability — searches, hit rate, gaps, by AI tool
  digest    Weekly markdown digest — gaps, decayed entries, queue health
  status    One-line health summary (use --quiet for hooks)
  doctor    Diagnose CruxHive setup — symlinks, hooks, slash commands
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
