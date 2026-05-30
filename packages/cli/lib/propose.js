"use strict";

const { spawnSync } = require("child_process");
const { createInterface } = require("readline");
const { writeFileSync, unlinkSync, readFileSync } = require("fs");
const { tmpdir } = require("os");
const { join } = require("path");

const TYPES = ["fact", "decision", "plan", "pattern", "constraint", "research", "outcome"];

function prompt(rl, question) {
  return new Promise((res) => rl.question(question, res));
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

async function selectType(rl) {
  console.log("\n  Type:");
  TYPES.forEach((t, i) => console.log(`    ${i + 1}. ${t}`));
  const ans = await prompt(rl, "  Choose [1-7]: ");
  const idx = parseInt(ans, 10) - 1;
  return TYPES[idx] || null;
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

async function propose(_args) {
  const cwd = process.cwd();
  console.log(`\n\x1b[1mcruxhive propose\x1b[0m — add a knowledge entry`);

  const rl = createInterface({ input: process.stdin, output: process.stdout });

  const type = await selectType(rl);
  if (!type) {
    console.log("  Invalid selection.");
    rl.close();
    return;
  }

  const topic = (await prompt(rl, `\n  Topic (1-3 words): `)).trim();
  if (!topic) { rl.close(); return; }

  const scope = (await prompt(rl, `  Scope [project]: `)).trim() || "project";

  // ── Dedup check ──────────────────────────────────────────────────────────
  const similar = searchSimilar(`${topic} ${type}`, 3);
  if (similar.length) {
    console.log(`\n  \x1b[33m!\x1b[0m  Similar entries already exist:`);
    for (const s of similar) {
      const snip = (s.snippet || "").trim().replace(/\s+/g, " ").slice(0, 80);
      console.log(`     · ${s.path}  \x1b[90m[${s.type || "?"}]\x1b[0m  ${snip}`);
    }
    const ans = (await prompt(rl, `\n  Proceed anyway? [y/N]: `)).trim().toLowerCase();
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

module.exports = { propose };
