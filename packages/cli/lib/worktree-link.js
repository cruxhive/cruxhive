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

/** Walk `dir` collecting *.md file paths (relative to `dir`), plus any path
 * the walk could NOT confidently verify: an unreadable subdirectory
 * (permission denied, etc.) or a symlink of any kind (file or directory).
 *
 * Both cases used to be silently dropped — an unreadable dir made
 * readdirSync throw, caught and swallowed into an empty result for that
 * subtree, and a symlinked .md file simply isn't isFile()/isDirectory()
 * true (Dirent from withFileTypes uses lstat semantics), so it fell through
 * every branch and vanished from the walk entirely. Either way the caller
 * would report "all files match" without ever having looked — the opposite
 * of this tool's contract. Surfacing both as `problems`, treated exactly
 * like a divergent file by the caller, keeps the "never guess, refuse and
 * name it" rule intact instead of silently proceeding past what wasn't
 * actually checked. */
function walkTree(dir, base = dir) {
  const files = [];
  const problems = [];
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch (e) {
    problems.push({
      path: relative(base, dir) || ".",
      reason: `unreadable directory (${e.code || e.message})`,
    });
    return { files, problems };
  }
  for (const e of entries) {
    const full = join(dir, e.name);
    const relPath = relative(base, full);
    if (e.isSymbolicLink()) {
      // Don't try to cleverly resolve/compare through it — could point
      // anywhere, including outside .llm/ or back through itself.
      problems.push({ path: relPath, reason: "symlink — not verified" });
      continue;
    }
    if (e.isDirectory()) {
      const sub = walkTree(full, base);
      files.push(...sub.files);
      problems.push(...sub.problems);
    } else if (e.isFile() && e.name.endsWith(".md")) {
      files.push(relPath);
    }
  }
  return { files, problems };
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
  const { files: localFiles, problems: walkProblems } = walkTree(localLlm);
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

  // Tag every problem path with why it's a problem — divergent/unique
  // content, or something the walk couldn't even verify (unreadable dir,
  // symlink). All three refuse the link the same way.
  const tagFor = new Map();
  for (const rel of uniqueToWorktree) tagFor.set(rel, "unique to this worktree");
  for (const rel of divergent) tagFor.set(rel, "content differs");
  for (const p of walkProblems) tagFor.set(p.path, p.reason);
  const problems = [...tagFor.keys()];

  if (problems.length) {
    err(`Refusing to link — ${problems.length} file(s)/path(s) in this worktree's .llm/ `
      + `differ from, don't exist in, or couldn't be verified against the main worktree's .llm/:\n`);
    for (const p of problems) {
      console.log(`    - ${p}  \x1b[90m(${tagFor.get(p)})\x1b[0m`);
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
