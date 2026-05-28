"use strict";

const { spawnSync } = require("child_process");
const { mkdirSync, writeFileSync, existsSync, readFileSync, symlinkSync } = require("fs");
const { join, dirname } = require("path");

const CONTEXT_TEMPLATE = (projectName, date) => `---
type: fact
scope: project
topic: project-context
valid_at: ${date}
confidence: high
source: human
---

# ${projectName} — Context

> One sentence describing what this project is and does.

**Stack**: [your stack here]

## Always read first

\`.llm/plans/active.md\` — current sprint focus.

## Repository layout

| Path | Contents |
|---|---|
| \`src/\` | Source code |

## Conventions

- Add your team's key conventions here
- Each rule should explain WHY, not just WHAT

## Three-tier context model (CruxHive)

| Tier | Location | Contents |
|---|---|---|
| **Org** | Shared remote | Cross-project facts, guardrails, architecture decisions |
| **Project** | \`.llm/\` (this repo) | Plans, audits, context — project-specific |
| **Personal** | \`~/.cruxhive/personal/\` | Developer preferences — never shared |
`;

function ok(msg)   { console.log(`  \x1b[32m✓\x1b[0m  ${msg}`); }
function info(msg) { console.log(`  \x1b[36m·\x1b[0m  ${msg}`); }
function warn(msg) { console.log(`  \x1b[33m!\x1b[0m  ${msg}`); }
function step(msg) { console.log(`\n\x1b[1m${msg}\x1b[0m`); }

function hasBin(name) {
  return spawnSync(name, ["--version"], { stdio: "pipe" }).status === 0;
}

// ─── install cruxhive-mcp ──────────────────────────────────────────────────

function installMcp() {
  // Skip if already on PATH
  if (hasBin("cruxhive-mcp")) {
    info("cruxhive-mcp already installed — skipped");
    return null;
  }

  if (hasBin("uv")) {
    const r = spawnSync("uv", ["tool", "install", "cruxhive-mcp"], { stdio: "inherit" });
    if (r.status !== 0) throw new Error("uv tool install cruxhive-mcp failed");
    return "uv tool";
  }

  if (hasBin("pip3") || hasBin("pip")) {
    const pip = hasBin("pip3") ? "pip3" : "pip";
    const r = spawnSync(pip, ["install", "cruxhive-mcp"], { stdio: "inherit" });
    if (r.status !== 0) throw new Error(`${pip} install cruxhive-mcp failed`);
    warn(`Installed via ${pip} — cruxhive-mcp binary may not be on PATH.`);
    warn(`For a cleaner install: uv tool install cruxhive-mcp (https://docs.astral.sh/uv/)`);
    return pip;
  }

  throw new Error(
    "Neither uv nor pip found.\nInstall uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
  );
}

function mcpEntry() {
  // If cruxhive-mcp binary is on PATH, use it directly (uv tool install path)
  if (hasBin("cruxhive-mcp")) return { command: "cruxhive-mcp", type: "stdio" };
  // Fallback: let uvx fetch it from PyPI at runtime
  return { command: "uvx", args: ["cruxhive-mcp"], type: "stdio" };
}

// ─── wire .mcp.json ────────────────────────────────────────────────────────

function wireMcp(cwd) {
  const mcpPath = join(cwd, ".mcp.json");
  let cfg = existsSync(mcpPath)
    ? JSON.parse(readFileSync(mcpPath, "utf8"))
    : { mcpServers: {} };

  if (!cfg.mcpServers) cfg.mcpServers = {};

  if (cfg.mcpServers.cruxhive) {
    info(".mcp.json already has cruxhive entry");
    return;
  }

  cfg.mcpServers.cruxhive = mcpEntry();
  writeFileSync(mcpPath, JSON.stringify(cfg, null, 2) + "\n");
  ok("cruxhive-mcp registered in .mcp.json");
}

// ─── wire AI tool context files ────────────────────────────────────────────

const CONTEXT_REL = ".llm/CONTEXT.md";

function trySymlink(target, linkPath, label) {
  if (existsSync(linkPath)) {
    info(`${label} already exists — skipped`);
    return;
  }
  try {
    mkdirSync(dirname(linkPath), { recursive: true });
    symlinkSync(target, linkPath);
    ok(`${label} → ${CONTEXT_REL} (symlink)`);
  } catch {
    warn(`Could not create ${label} symlink — create it manually: ln -s ${CONTEXT_REL} ${linkPath}`);
  }
}

function patchOrSymlink(filePath, label) {
  if (existsSync(filePath)) {
    const content = readFileSync(filePath, "utf8");
    if (content.includes("CONTEXT.md")) {
      info(`${label} already references CONTEXT.md`);
      return;
    }
    writeFileSync(filePath, content.trimEnd() + "\n\n<!-- CruxHive canonical context: .llm/CONTEXT.md -->\n");
    ok(`${label} patched with CONTEXT.md reference`);
  } else {
    trySymlink(CONTEXT_REL, filePath, label);
  }
}

function wireAiTools(cwd) {
  const tools = [
    // Claude Code
    { check: () => true, wire: () => patchOrSymlink(join(cwd, "CLAUDE.md"), "CLAUDE.md") },
    // OpenCode
    { check: () => true, wire: () => trySymlink(CONTEXT_REL, join(cwd, "AGENT.md"), "AGENT.md") },
    // Cursor
    { check: () => true, wire: () => trySymlink(CONTEXT_REL, join(cwd, ".cursor/rules/cruxhive.mdc"), ".cursor/rules/cruxhive.mdc") },
    // Windsurf
    { check: () => true, wire: () => trySymlink(CONTEXT_REL, join(cwd, ".windsurfRules"), ".windsurfRules") },
    // Gemini CLI
    { check: () => true, wire: () => trySymlink(CONTEXT_REL, join(cwd, "GEMINI.md"), "GEMINI.md") },
  ];

  for (const t of tools) t.wire();
}

// ─── main ──────────────────────────────────────────────────────────────────

async function init(_args) {
  const cwd = process.cwd();
  const date = new Date().toISOString().split("T")[0];
  const projectName = cwd.split("/").pop();

  console.log(`\n\x1b[1mCruxHive init\x1b[0m — ${projectName}`);

  // 1. .llm/ structure
  step("1/4  Creating .llm/ structure");
  for (const dir of [".llm", ".llm/plans", ".llm/pending", ".llm/context", ".llm/memory"]) {
    mkdirSync(join(cwd, dir), { recursive: true });
  }
  ok("directories: .llm/ .llm/plans/ .llm/pending/ .llm/context/ .llm/memory/");

  const contextPath = join(cwd, ".llm", "CONTEXT.md");
  if (!existsSync(contextPath)) {
    writeFileSync(contextPath, CONTEXT_TEMPLATE(projectName, date));
    ok(".llm/CONTEXT.md created");
  } else {
    info(".llm/CONTEXT.md already exists — skipped");
  }

  const activePath = join(cwd, ".llm", "plans", "active.md");
  if (!existsSync(activePath)) {
    writeFileSync(activePath, `# Active Plans\n\n_No active plans yet._\n`);
    ok(".llm/plans/active.md created");
  } else {
    info(".llm/plans/active.md already exists — skipped");
  }

  // 2. install cruxhive-mcp
  step("2/4  Installing cruxhive-mcp");
  const installer = installMcp();
  if (installer) ok(`cruxhive-mcp installed via ${installer}`);

  // 3. wire .mcp.json
  step("3/4  Wiring .mcp.json");
  wireMcp(cwd);

  // 4. wire AI tools
  step("4/4  Wiring AI tools");
  wireAiTools(cwd);

  console.log(`
\x1b[32m✓ CruxHive initialized in ${projectName}\x1b[0m

Next steps:
  1. Edit \x1b[36m.llm/CONTEXT.md\x1b[0m — describe your project, stack, and conventions
  2. Run \x1b[36mcruxhive index\x1b[0m to build the search index
  3. Reload your AI tool — MCP tools are now available

Docs: https://cruxhive.com/guide.html
`);
}

module.exports = { init };
