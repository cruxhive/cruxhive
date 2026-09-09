#!/usr/bin/env node
"use strict";

const { init }    = require("../lib/init");
const { sync }    = require("../lib/sync");
const { health }  = require("../lib/health");
const { ui }      = require("../lib/ui");
const { index }   = require("../lib/index");
const { propose } = require("../lib/propose");
const { review }  = require("../lib/review");
const { search }  = require("../lib/search");
const { stats }   = require("../lib/stats");
const { digest }  = require("../lib/digest");
const { status }  = require("../lib/status");
const { doctor } = require("../lib/doctor");
const { workspace } = require("../lib/workspace");
const { direnv }    = require("../lib/direnv");
const { solo }      = require("../lib/solo");
const { skills }    = require("../lib/skills");
const { worktreeLink } = require("../lib/worktree-link");

const [, , cmd, ...args] = process.argv;

const commands = {
  init, sync, health, ui, index, propose, review, search, stats, digest, status, doctor,
  workspace, direnv, solo, skills, "worktree-link": worktreeLink,
};

// Short per-command usage text for the generic `--help`/`-h` intercept below.
// Kept as literal copies of the lines in the top-level help block (not
// generated from it) so a refactor of one can't silently reformat the other.
const COMMAND_HELP = {
  init: "Bootstrap CruxHive in the current project",
  index: "Index .llm/ markdown files into the local knowledge base",
  propose: "Propose a new knowledge entry for human review\n" +
    "            Interactive wizard by default. Non-interactive:\n" +
    "            --type <t> --topic <t> --scope <s> --content <text|->\n" +
    "            (--content - reads the body from stdin)",
  review: "Interactively approve or reject pending proposals\n" +
    "            [--all] approve every pending item · [--all-safe] approve only\n" +
    "            non-conflicting items (no reconcile verdict), non-interactively",
  search: "Search the knowledge base from the terminal\n" +
    "            cruxhive search [--workspace] <query> [n]\n" +
    "            [--workspace] search all configured projects · [n] result count\n" +
    "            --json prints raw JSON (scripting)",
  sync: "Sync org-layer context from the configured remote",
  health: "Show knowledge base health summary",
  stats: "Usage observability — searches, hit rate, gaps, by AI tool",
  digest: "Weekly markdown digest — gaps, decayed entries, queue health",
  status: "One-line health summary (use --quiet for hooks)",
  doctor: "Diagnose CruxHive setup — symlinks, hooks, slash commands",
  workspace: "Cross-project rollup — aggregate KPIs across all configured projects",
  direnv: "Write a .envrc that auto-logs sessions for Cursor/Windsurf/Gemini",
  skills: "Sync a canonical skills dir to every AI-tool dialect\n" +
    "            (cruxhive skills sync [--from <dir>], default source .llm/skills/)",
  solo: "Enable/disable solo mode — auto-approve your own proposals\n" +
    "            Run with --status to check current mode, --disable to turn off",
  ui: "Open the approval queue dashboard (localhost:3847)\n" +
    "            Add --workspace to see cross-project rollup view",
  "worktree-link": "Relink a git worktree's diverged .llm/ to the main worktree's\n" +
    "            shared knowledge base (safe only if nothing would be lost).\n" +
    "            Add --dry-run to preview without changing anything.",
};

if (!cmd || cmd === "--help" || cmd === "-h") {
  console.log(`cruxhive v${require("../package.json").version}

Usage: cruxhive <command>

Commands:
  init      Bootstrap CruxHive in the current project
  index     Index .llm/ markdown files into the local knowledge base
  propose   Propose a new knowledge entry for human review
  review    Interactively approve or reject pending proposals
            [--all] approve every pending item · [--all-safe] approve only
            non-conflicting items (no reconcile verdict), non-interactively
  search    Search the knowledge base from the terminal
            [--workspace] search all configured projects · [n] result count
            · --json for raw JSON (scripting)
  sync      Sync org-layer context from the configured remote
  health    Show knowledge base health summary
  stats     Usage observability — searches, hit rate, gaps, by AI tool
  digest    Weekly markdown digest — gaps, decayed entries, queue health
  status    One-line health summary (use --quiet for hooks)
  doctor    Diagnose CruxHive setup — symlinks, hooks, slash commands
  workspace Cross-project rollup — aggregate KPIs across all configured projects
  direnv    Write a .envrc that auto-logs sessions for Cursor/Windsurf/Gemini
  skills    Sync a canonical skills dir to every AI-tool dialect
            (cruxhive skills sync [--from <dir>], default source .llm/skills/)
  solo      Enable/disable solo mode — auto-approve your own proposals
            Run with --status to check current mode, --disable to turn off
  ui        Open the approval queue dashboard (localhost:3847)
            Add --workspace to see cross-project rollup view
  worktree-link  Relink a git worktree's diverged .llm/ to the main worktree's
            shared knowledge base (safe only if nothing would be lost).
            Add --dry-run to preview without changing anything.

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

// Generic per-command `--help`/`-h` intercept: no command function parses
// this itself, so without this every command (propose most visibly) treated
// --help as ordinary args and ran for real instead of showing usage.
if (args.includes("--help") || args.includes("-h")) {
  console.log(`\ncruxhive ${cmd} — ${COMMAND_HELP[cmd] || "(no additional help available)"}\n`);
  process.exit(0);
}

fn(args).catch((err) => {
  console.error(`\nError: ${err.message}`);
  process.exit(1);
});
