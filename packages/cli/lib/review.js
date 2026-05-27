"use strict";

const { spawnSync } = require("child_process");
const { createInterface } = require("readline");

function prompt(rl, question) {
  return new Promise((res) => rl.question(question, res));
}

function badge(type) {
  const colors = {
    fact: "\x1b[34m", constraint: "\x1b[31m", decision: "\x1b[32m",
    pattern: "\x1b[33m", plan: "\x1b[35m", research: "\x1b[36m", outcome: "\x1b[32m",
  };
  const c = colors[type] || "\x1b[90m";
  return `${c}[${type || "?"}]\x1b[0m`;
}

async function review(_args) {
  const cwd = process.cwd();
  console.log(`\n\x1b[1mcruxhive review\x1b[0m — pending proposals\n`);

  const r = spawnSync("cruxhive-review", [], { cwd, stdio: ["inherit", "pipe", "inherit"] });
  if (r.error) {
    console.log("  \x1b[31m✗\x1b[0m  cruxhive-review not found — run: pip install cruxhive-mcp");
    process.exit(1);
  }

  let pending;
  try {
    pending = JSON.parse(r.stdout.toString());
  } catch {
    console.log("  No pending proposals or index not built. Run: cruxhive index");
    return;
  }

  if (pending.error) {
    console.log(`  \x1b[31m✗\x1b[0m  ${pending.error}`);
    return;
  }

  if (!pending.length) {
    console.log("  \x1b[32m✓\x1b[0m  No pending proposals — knowledge base is fully reviewed.");
    return;
  }

  console.log(`  ${pending.length} pending proposal(s)\n`);

  const rl = createInterface({ input: process.stdin, output: process.stdout });

  let approved = 0, rejected = 0, skipped = 0;

  for (const p of pending) {
    const preview = (p.preview || "").trim().slice(0, 120);
    console.log(`  ${badge(p.type)} \x1b[1m${p.path}\x1b[0m`);
    console.log(`  topic: ${p.topic || "—"}  ·  proposed: ${p.valid_at || "?"}`);
    if (preview) console.log(`  \x1b[90m${preview}…\x1b[0m`);

    const ans = (await prompt(rl, `  [a]pprove / [r]eject / [s]kip: `)).trim().toLowerCase();

    if (ans === "a" || ans === "approve") {
      const approver = (await prompt(rl, `  Your name: `)).trim();
      if (!approver) { console.log("  Skipped (no name given).\n"); skipped++; continue; }
      const ra = spawnSync("cruxhive-approve", [p.path, approver], { cwd, stdio: "inherit" });
      if (ra.status === 0) approved++;
    } else if (ans === "r" || ans === "reject") {
      const rr = spawnSync("cruxhive-reject", [p.path], { cwd, stdio: "inherit" });
      if (rr.status === 0) rejected++;
    } else {
      console.log("  Skipped.");
      skipped++;
    }
    console.log("");
  }

  rl.close();
  console.log(`  Done: ${approved} approved · ${rejected} rejected · ${skipped} skipped\n`);
}

module.exports = { review };
