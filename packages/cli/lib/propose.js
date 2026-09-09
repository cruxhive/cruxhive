"use strict";

const { spawnSync } = require("child_process");
const { createInterface } = require("readline");
const { writeFileSync, unlinkSync, readFileSync } = require("fs");
const { tmpdir } = require("os");
const { join } = require("path");

const TYPES = ["fact", "decision", "plan", "pattern", "constraint", "research", "outcome"];
const DEFAULT_SCOPE = "project";

/** Turn an rl into an `ask(question)` that queues 'line' events instead of
 * using rl.question() directly. Ported from review.js's makeAsker (fixed
 * this same bug there earlier this session) — see that file for the full
 * explanation of why rl.question() drops answers under piped/batched input.
 *
 * Additionally resolves pending/future asks with `null` on rl "close" (EOF)
 * so a pipe that closes mid-wizard fails the current `ask()` instead of
 * leaving its promise unresolved forever (the original silent-hang bug).
 */
function makeAsker(rl) {
  const queue = [];
  let pendingResolve = null;
  let closed = false;
  rl.on("line", (line) => {
    if (pendingResolve) {
      const res = pendingResolve;
      pendingResolve = null;
      res(line);
    } else {
      queue.push(line);
    }
  });
  rl.on("close", () => {
    closed = true;
    if (pendingResolve) {
      const res = pendingResolve;
      pendingResolve = null;
      res(null); // EOF while a question was outstanding
    }
  });
  return function ask(question) {
    process.stdout.write(question);
    if (queue.length) return Promise.resolve(queue.shift());
    if (closed) return Promise.resolve(null);
    return new Promise((resolve) => { pendingResolve = resolve; });
  };
}

function searchSimilar(query, n = 3) {
  const r = spawnSync("cruxhive-search", [query, String(n)], { stdio: ["ignore", "pipe", "pipe"] });
  if (r.status !== 0) return [];
  try {
    const out = JSON.parse(r.stdout.toString());
    if (Array.isArray(out)) return out;
  } catch { /* fall through */ }
  return [];
}

function printSimilar(similar) {
  console.log(`\n  \x1b[33m!\x1b[0m  Similar entries already exist:`);
  for (const s of similar) {
    const snip = (s.snippet || "").trim().replace(/\s+/g, " ").slice(0, 80);
    console.log(`     · ${s.path}  \x1b[90m[${s.type || "?"}]\x1b[0m  ${snip}`);
  }
}

function openEditor(initial) {
  const tmp = join(tmpdir(), `cruxhive-propose-${Date.now()}.md`);
  writeFileSync(tmp, initial, "utf8");
  const editor = process.env.EDITOR || process.env.VISUAL || "nano";
  spawnSync(editor, [tmp], { stdio: "inherit" });
  const content = readFileSync(tmp, "utf8").trim();
  unlinkSync(tmp);
  return content;
}

function parseFlags(args) {
  const out = { type: null, topic: null, scope: null, content: null };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--type") out.type = args[++i];
    else if (a === "--topic") out.topic = args[++i];
    else if (a === "--scope") out.scope = args[++i];
    else if (a === "--content") out.content = args[++i];
  }
  return out;
}

function readStdinSync() {
  try {
    return readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

/** All validation and writing lives Python-side (cli.py's propose(),
 * ~line 112-181) — this always shells out to the same `cruxhive-propose
 * <type> <topic> <scope>` call with content on stdin, regardless of whether
 * type/topic/scope/content were gathered via flags or the wizard. */
function submit(cwd, type, topic, scope, content) {
  const r = spawnSync(
    "cruxhive-propose",
    [type, topic, scope],
    { cwd, stdio: ["pipe", "inherit", "inherit"], input: content }
  );
  if (r.error) {
    console.log("  \x1b[31m✗\x1b[0m  cruxhive-propose not found — run: pip install cruxhive-mcp");
    process.exit(1);
  }
  if (r.status !== 0) process.exit(r.status);
}

async function propose(_args) {
  const argv = Array.isArray(_args) ? _args : [];
  const cwd = process.cwd();

  // ── Non-interactive flag mode ────────────────────────────────────────────
  // For AI agents / scripts: skip readline and $EDITOR (unusable
  // non-interactively anyway) entirely once type+topic+content are all given.
  const flags = parseFlags(argv);
  if (flags.type && flags.topic && flags.content !== null) {
    const type = flags.type;
    const topic = flags.topic;
    const scope = flags.scope || DEFAULT_SCOPE;
    const content = flags.content === "-" ? readStdinSync() : flags.content;

    // Fast client-side check (TYPES is duplicated from cli.py only for this
    // shell-out-free error) — the authoritative check still runs Python-side.
    if (!TYPES.includes(type)) {
      console.log(`  \x1b[31m✗\x1b[0m  Invalid type '${type}'. Use: ${TYPES.join(", ")}`);
      process.exit(1);
    }

    // Advisory-only dedup check — never blocks non-interactive use.
    const similar = searchSimilar(`${topic} ${type}`, 3);
    if (similar.length) printSimilar(similar);

    submit(cwd, type, topic, scope, content);
    return;
  }

  // ── Interactive wizard ────────────────────────────────────────────────────
  console.log(`\n\x1b[1mcruxhive propose\x1b[0m — add a knowledge entry`);

  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const ask = makeAsker(rl);

  function abort(label) {
    console.log(`  \x1b[31m✗\x1b[0m  Input ended before ${label} was given.`);
    rl.close();
    process.exit(1);
  }

  console.log("\n  Type:");
  TYPES.forEach((t, i) => console.log(`    ${i + 1}. ${t}`));
  const typeAns = await ask("  Choose [1-7]: ");
  if (typeAns == null) { abort("a type"); return; }
  const idx = parseInt(typeAns, 10) - 1;
  const type = TYPES[idx];
  if (!type) {
    console.log("  Invalid selection.");
    rl.close();
    return;
  }

  const topicAns = await ask(`\n  Topic (1-3 words): `);
  if (topicAns == null) { abort("a topic"); return; }
  const topic = topicAns.trim();
  if (!topic) { rl.close(); return; }

  // Scope has a default, so EOF here (pipe ended right after the topic) is
  // treated the same as a blank interactive answer — fall back, don't error.
  const scopeAns = await ask(`  Scope [project]: `);
  const scope = (scopeAns || "").trim() || DEFAULT_SCOPE;

  // ── Dedup check ──────────────────────────────────────────────────────────
  const similar = searchSimilar(`${topic} ${type}`, 3);
  if (similar.length) {
    printSimilar(similar);
    // EOF here defaults to "N" (cancel) — the safe choice, not an error.
    const ansRaw = await ask(`\n  Proceed anyway? [y/N]: `);
    const ans = (ansRaw || "").trim().toLowerCase();
    if (ans !== "y" && ans !== "yes") {
      console.log("  Proposal cancelled — edit the existing entry instead, or rerun with a different topic.");
      rl.close();
      return;
    }
  }
  rl.close();

  console.log(`\n  Opening editor for content…`);
  const placeholder = `<!-- Describe the ${type}: what, why, and any relevant context -->\n`;
  const content = openEditor(placeholder);

  if (!content || content === placeholder.trim()) {
    console.log("  \x1b[33m!\x1b[0m  Empty content — proposal cancelled.");
    return;
  }

  submit(cwd, type, topic, scope, content);
}

module.exports = { propose };
