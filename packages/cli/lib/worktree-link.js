"use strict";

const {
  existsSync,
  readFileSync,
  readdirSync,
  renameSync,
  lstatSync,
  readlinkSync,
} = require("fs");
const { join, relative, resolve, dirname } = require("path");

const { gitMainWorktreeRoot, trySymlinkTo } = require("./init");

function ok(msg)   { console.log(`  \x1b[32m✓\x1b[0m  ${msg}`); }
function info(msg) { console.log(`  \x1b[36m·\x1b[0m  ${msg}`); }
function warn(msg) { console.log(`  \x1b[33m!\x1b[0m  ${msg}`); }
function err(msg)  { console.log(`  \x1b[31m✗\x1b[0m  ${msg}`); }

/** All *.md files under `dir`, as paths relative to `dir`. */
function walkMdFiles(dir, base = dir) {
  let out = [];
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const e of entries) {
    const full = join(dir, e.name);
    if (e.isDirectory()) {
      out = out.concat(walkMdFiles(full, base));
    } else if (e.isFile() && e.name.endsWith(".md")) {
      out.push(relative(base, full));
    }
  }
  return out;
}

function filesIdentical(a, b) {
  try {
    return readFileSync(a).equals(readFileSync(b));
  } catch {
    return false;
  }
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

async function worktreeLink(args) {
  const argv = Array.isArray(args) ? args : [];
  const dryRun = argv.includes("--dry-run");

  const cwd = process.cwd();
  console.log(`\n\x1b[1mcruxhive worktree-link\x1b[0m${dryRun ? " (dry run)" : ""}\n`);

  const mainRoot = gitMainWorktreeRoot(cwd);
  if (!mainRoot) {
    err("not a git repo — nothing to link.");
    process.exit(1);
  }
  if (resolve(mainRoot) === resolve(cwd)) {
    err("this IS the main worktree — nothing to link.");
    process.exit(1);
  }

  const mainLlm = join(mainRoot, ".llm");
  if (!existsSync(mainLlm)) {
    err(`main worktree has no .llm/ — run \`cruxhive init\` there first.`);
    err(`  main worktree: ${mainRoot}`);
    process.exit(1);
  }

  const localLlm = join(cwd, ".llm");

  // Already linked?
  if (existsSync(localLlm)) {
    try {
      const st = lstatSync(localLlm);
      if (st.isSymbolicLink()) {
        const target = resolve(dirname(localLlm), readlinkSync(localLlm));
        if (target === resolve(mainLlm)) {
          ok(".llm/ is already linked to the main worktree — nothing to do.");
          return;
        }
        warn(`.llm/ is a symlink but points elsewhere (${target}).`);
        warn(`Remove or fix it manually, then re-run.`);
        process.exit(1);
      }
    } catch { /* fall through */ }
  }

  if (!existsSync(localLlm)) {
    info("this worktree has no local .llm/ — nothing to diverge, safe to link.");
    if (dryRun) {
      console.log(`\n  Would symlink .llm/ → ${mainLlm}\n`);
      return;
    }
    trySymlinkTo(localLlm, relative(cwd, mainLlm), ".llm", { cwd, expectResolved: resolve(mainLlm) });
    console.log(`\n  \x1b[32m✓ Linked.\x1b[0m .llm/ now points at ${mainLlm}\n`);
    return;
  }

  // Compare every *.md file in this worktree's .llm/ against main's, byte-for-byte.
  const localFiles = walkMdFiles(localLlm);
  const divergent = [];
  for (const rel of localFiles) {
    const localPath = join(localLlm, rel);
    const mainPath = join(mainLlm, rel);
    if (!existsSync(mainPath)) continue; // handled below as uniqueToWorktree
    if (!filesIdentical(localPath, mainPath)) divergent.push(rel);
  }
  // Files that exist ONLY in this worktree are also divergent — main lacks
  // something this worktree has, so linking would silently discard it.
  const uniqueToWorktree = localFiles.filter((rel) => !existsSync(join(mainLlm, rel)));
  const problems = [...new Set([...divergent, ...uniqueToWorktree])];

  if (problems.length) {
    err(`Refusing to link — ${problems.length} file(s) in this worktree's .llm/ `
      + `differ from (or don't exist in) the main worktree's .llm/:\n`);
    for (const p of problems) {
      const tag = uniqueToWorktree.includes(p) && !divergent.includes(p) ? "unique to this worktree" : "content differs";
      console.log(`    - ${p}  \x1b[90m(${tag})\x1b[0m`);
    }
    console.log(`\n  Nothing was changed. Reconcile these manually (copy anything`);
    console.log(`  worth keeping into the main worktree's .llm/), then re-run.\n`);
    process.exit(1);
  }

  info(`checked ${localFiles.length} file(s) — all match the main worktree's .llm/ (or don't exist there).`);

  if (dryRun) {
    const backupPath = join(cwd, `.llm.bak-${timestamp()}`);
    console.log(`\n  Would back up .llm/ → ${backupPath}`);
    console.log(`  Would symlink .llm/ → ${mainLlm}\n`);
    return;
  }

  const backupPath = join(cwd, `.llm.bak-${timestamp()}`);
  renameSync(localLlm, backupPath);
  ok(`backed up .llm/ → ${backupPath}`);
  trySymlinkTo(localLlm, relative(cwd, mainLlm), ".llm", { cwd, expectResolved: resolve(mainLlm) });
  console.log(`\n  \x1b[32m✓ Linked.\x1b[0m .llm/ now points at ${mainLlm}`);
  console.log(`  Old contents preserved at ${backupPath} — delete once you've confirmed nothing was lost.\n`);
}

module.exports = { worktreeLink };
