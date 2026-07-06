"use strict";

// cruxhive skills — distribute a canonical skills directory to every AI-tool dialect.
//
//   cruxhive skills sync [--from <dir>]
//
// Source of truth (default .llm/skills/): flat <name>.md files or <name>/SKILL.md dirs.
// Targets, in the current project:
//   .claude/skills/<name>/SKILL.md    Claude Code   (name + description frontmatter)
//   .opencode/commands/<name>.md      OpenCode      (description-only frontmatter)
//   .agents/skills/<name>/SKILL.md    Antigravity   (name + description frontmatter)
//
// Sync semantics: targets are generated artifacts and are always overwritten.
// Dialect rules match init.js writeCommandFile().

const {
  mkdirSync, writeFileSync, existsSync, readFileSync, readdirSync,
  statSync, cpSync, rmSync,
} = require("fs");
const { join, dirname } = require("path");

function ok(msg)   { console.log(`  \x1b[32m✓\x1b[0m  ${msg}`); }
function info(msg) { console.log(`  \x1b[36m·\x1b[0m  ${msg}`); }
function warn(msg) { console.log(`  \x1b[33m!\x1b[0m  ${msg}`); }
function step(msg) { console.log(`\n\x1b[1m${msg}\x1b[0m`); }

const MARKER = (src) =>
  `<!-- AUTO-SYNCED by \`cruxhive skills sync\` from ${src} — edit the source, then re-sync -->`;

// Parse a skill markdown file into { name, description, body }.
// Only single-line `description:` values are supported (folded scalars are flagged).
function parseSkill(mdPath, fallbackName) {
  const raw = readFileSync(mdPath, "utf8");
  const m = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) return { name: fallbackName, description: null, body: raw };
  const fm = m[1];
  const body = m[2].replace(/^\n+/, "");
  const name = (fm.match(/^name:[ \t]*(.+)$/m) || [])[1] || fallbackName;
  const description = (fm.match(/^description:[ \t]*(.+)$/m) || [])[1] || null;
  return { name: name.trim(), description: description ? description.trim() : null, body };
}

// Discover skills in the source dir: flat *.md files and <name>/SKILL.md dirs.
function discoverSkills(srcDir) {
  const entries = [];
  for (const e of readdirSync(srcDir)) {
    const p = join(srcDir, e);
    if (statSync(p).isDirectory()) {
      const md = join(p, "SKILL.md");
      if (existsSync(md)) entries.push({ name: e, md, dir: p });
    } else if (e.endsWith(".md")) {
      entries.push({ name: e.slice(0, -3), md: p, dir: null });
    }
  }
  return entries;
}

function writeGenerated(filePath, content) {
  mkdirSync(dirname(filePath), { recursive: true });
  writeFileSync(filePath, content);
}

// Copy any support files from a dir-based skill (everything except SKILL.md).
function copySupportFiles(srcDir, destDir) {
  for (const e of readdirSync(srcDir)) {
    if (e === "SKILL.md") continue;
    cpSync(join(srcDir, e), join(destDir, e), { recursive: true });
  }
}

function syncSkills(cwd, srcRel) {
  const srcDir = join(cwd, srcRel);
  if (!existsSync(srcDir)) {
    warn(`No skills source at ${srcRel} — create it (or pass --from <dir>) and re-run.`);
    process.exit(1);
  }

  const skills = discoverSkills(srcDir);
  if (skills.length === 0) {
    info(`${srcRel} has no skills (flat <name>.md or <name>/SKILL.md) — nothing to sync.`);
    return;
  }

  step(`Syncing ${skills.length} skill(s) from ${srcRel}`);
  let synced = 0;

  for (const s of skills) {
    const { name, description, body } = parseSkill(s.md, s.name);
    if (!description) {
      warn(`${s.name}: no single-line \`description:\` in frontmatter — skipped (all dialects need it)`);
      continue;
    }
    const stamped = `${MARKER(srcRel)}\n\n${body}`;

    // Claude Code and Antigravity: { name, description }; OpenCode: { description } only.
    const fmFull = `---\nname: ${name}\ndescription: ${description}\n---\n\n`;
    const fmDesc = `---\ndescription: ${description}\n---\n\n`;

    const claudeDir = join(cwd, ".claude", "skills", name);
    const agDir = join(cwd, ".agents", "skills", name);
    if (existsSync(claudeDir)) rmSync(claudeDir, { recursive: true });
    if (existsSync(agDir)) rmSync(agDir, { recursive: true });

    writeGenerated(join(claudeDir, "SKILL.md"), fmFull + stamped);
    writeGenerated(join(cwd, ".opencode", "commands", `${name}.md`), fmDesc + stamped);
    writeGenerated(join(agDir, "SKILL.md"), fmFull + stamped);
    if (s.dir) {
      copySupportFiles(s.dir, claudeDir);
      copySupportFiles(s.dir, agDir);
    }
    ok(`${name} → .claude/skills + .opencode/commands + .agents/skills`);
    synced++;
  }

  console.log(`\nDone: ${synced}/${skills.length} skill(s) synced to 3 dialects.`);
  if (synced < skills.length) process.exit(1);
}

async function skills(args) {
  const cwd = process.cwd();
  const sub = args[0];

  if (sub === "sync") {
    const fromIdx = args.indexOf("--from");
    const srcRel = fromIdx !== -1 && args[fromIdx + 1] ? args[fromIdx + 1] : join(".llm", "skills");
    syncSkills(cwd, srcRel);
    return;
  }

  console.log(`
Usage: cruxhive skills sync [--from <dir>]

Distribute a canonical skills directory to every AI-tool dialect:
  .claude/skills/       Claude Code
  .opencode/commands/   OpenCode
  .agents/skills/       Antigravity

Source defaults to .llm/skills/ — flat <name>.md files or <name>/SKILL.md dirs.
Targets are generated artifacts: always overwritten, never hand-edit them.
`);
}

module.exports = { skills };
