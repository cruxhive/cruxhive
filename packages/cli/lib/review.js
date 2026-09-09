"use strict";

const { spawnSync } = require("child_process");
const { createInterface } = require("readline");

/** Turn an rl into an `ask(question)` that queues 'line' events instead of
 * using rl.question() directly.
 *
 * rl.question() only works reliably when each answer arrives strictly AFTER
 * the question that asked for it — true for a human typing at a TTY, but
 * NOT for piped/batched input (e.g. `printf 'a\nb\n' | cruxhive review`,
 * or this file's own bulk-mode tests): readline parses every buffered line
 * into 'line' events as fast as the stream delivers them, so a second and
 * third answer can each fire before the code has even called question() for
 * them — and since question() only attaches a ONE-TIME 'line' listener,
 * those events are dropped and the prompt hangs forever. Queuing every
 * 'line' event up front and handing them out in order fixes both cases.
 */
function makeAsker(rl) {
  const queue = [];
  let pendingResolve = null;
  rl.on("line", (line) => {
    if (pendingResolve) {
      const res = pendingResolve;
      pendingResolve = null;
      res(line);
    } else {
      queue.push(line);
    }
  });
  return function ask(question) {
    process.stdout.write(question);
    if (queue.length) return Promise.resolve(queue.shift());
    return new Promise((resolve) => { pendingResolve = resolve; });
  };
}

function badge(type) {
  const colors = {
    fact: "\x1b[34m", constraint: "\x1b[31m", decision: "\x1b[32m",
    pattern: "\x1b[33m", plan: "\x1b[35m", research: "\x1b[36m", outcome: "\x1b[32m",
  };
  const c = colors[type] || "\x1b[90m";
  return `${c}[${type || "?"}]\x1b[0m`;
}

/** `git config user.name`, or "" if unset/unavailable. Mirrors the default
 * pattern in cruxhive_mcp/cli.py's `solo()` (~line 792-799). */
function gitUserName(cwd) {
  try {
    const r = spawnSync("git", ["config", "user.name"], { cwd, stdio: ["ignore", "pipe", "ignore"] });
    if (r.status === 0) return (r.stdout || "").toString().trim();
  } catch {}
  return "";
}

function approveOne(cwd, path, approver) {
  const r = spawnSync("cruxhive-approve", [path, approver], { cwd, stdio: "inherit" });
  return r.status === 0;
}

function rejectOne(cwd, path) {
  const r = spawnSync("cruxhive-reject", [path], { cwd, stdio: "inherit" });
  return r.status === 0;
}

function printItem(p) {
  const preview = (p.preview || "").trim().slice(0, 120);
  console.log(`  ${badge(p.type)} \x1b[1m${p.path}\x1b[0m`);
  console.log(`  topic: ${p.topic || "—"}  ·  proposed: ${p.valid_at || "?"}`);
  if (p.reconcile) {
    const verb = p.reconcile === "duplicate" ? "\x1b[31m⧉ duplicate of\x1b[0m" : "\x1b[33m↻ updates\x1b[0m";
    console.log(`  ${verb} ${p.reconcile_target}${p.reconcile_score ? ` (${p.reconcile_score})` : ""}`);
  }
  if (preview) console.log(`  \x1b[90m${preview}…\x1b[0m`);
}

async function review(args) {
  const argv = Array.isArray(args) ? args : [];
  const wantsAll = argv.includes("--all");
  const wantsAllSafe = argv.includes("--all-safe");

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

  const defaultApprover = gitUserName(cwd);
  const nonInteractive = wantsAll || wantsAllSafe;

  // One readline.Interface for the whole command. Creating and closing
  // several in sequence on the same (piped, non-TTY) stdin drops buffered
  // input between them — the first prompt would consume its answer fine,
  // but the interface after it would never see the rest of the pipe.
  const rl = nonInteractive ? null : createInterface({ input: process.stdin, output: process.stdout });
  const ask = rl ? makeAsker(rl) : null;

  // ── approver name — asked once, up front, not per item ──────────────────
  let approver = defaultApprover;
  if (rl) {
    const suffix = defaultApprover ? ` [${defaultApprover}]` : "";
    const answer = (await ask(`  Your name${suffix}: `)).trim();
    approver = answer || defaultApprover;
  }
  if (!approver) {
    console.log("  \x1b[31m✗\x1b[0m  No name given and `git config user.name` is unset.");
    console.log("  Set git user.name, or answer the name prompt, and try again.");
    if (rl) rl.close();
    process.exit(1);
  }

  // ── bulk mode selection ──────────────────────────────────────────────────
  let mode; // "all" | "safe" | "interactive"
  if (wantsAll) {
    mode = "all";
  } else if (wantsAllSafe) {
    mode = "safe";
  } else {
    const ans = (await ask(
      `  [A]pprove all / [n]on-conflicting only / [i]nteractive [i]: `
    )).trim().toLowerCase();
    if (ans === "a" || ans === "approve" || ans === "all") mode = "all";
    else if (ans === "n" || ans === "non-conflicting" || ans === "safe") mode = "safe";
    else mode = "interactive";
  }

  let approved = 0, rejected = 0, skipped = 0;

  if (mode === "all" || mode === "safe") {
    if (rl) rl.close();
    for (const p of pending) {
      if (mode === "safe" && p.reconcile) {
        console.log(`  \x1b[33m↻\x1b[0m  ${p.path} — has a reconcile verdict (${p.reconcile}), skipped (non-conflicting mode)`);
        skipped++;
        continue;
      }
      const ok = approveOne(cwd, p.path, approver);
      if (ok) {
        console.log(`  \x1b[32m✓\x1b[0m  ${p.path} approved`);
        approved++;
      } else {
        console.log(`  \x1b[31m✗\x1b[0m  ${p.path} failed to approve`);
      }
    }
    console.log(`\n  Done: ${approved} approved · ${skipped} skipped (approver: ${approver})\n`);
    return;
  }

  // ── interactive: existing single-item flow, minus the per-item name prompt ──
  for (const p of pending) {
    printItem(p);

    const ans = (await ask(`  [a]pprove / [r]eject / [s]kip: `)).trim().toLowerCase();

    if (ans === "a" || ans === "approve") {
      if (approveOne(cwd, p.path, approver)) approved++;
    } else if (ans === "r" || ans === "reject") {
      if (rejectOne(cwd, p.path)) rejected++;
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
