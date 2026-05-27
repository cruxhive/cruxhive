"use strict";

const { spawnSync } = require("child_process");
const { mkdirSync, writeFileSync, existsSync, readFileSync } = require("fs");
const { join } = require("path");
const { createInterface } = require("readline");

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

const MCP_ENTRY = {
  command: "uvx",
  args: ["cruxhive-mcp"],
  type: "stdio",
};

function ok(msg)   { console.log(`  \x1b[32m✓\x1b[0m  ${msg}`); }
function info(msg) { console.log(`  \x1b[36m·\x1b[0m  ${msg}`); }
function warn(msg) { console.log(`  \x1b[33m!\x1b[0m  ${msg}`); }
function step(msg) { console.log(`\n\x1b[1m${msg}\x1b[0m`); }

function hasBin(name) {
  return spawnSync(name, ["--version"], { stdio: "pipe" }).status === 0;
}

function installMcp() {
  if (hasBin("uv")) {
    const r = spawnSync("uv", ["pip", "install", "cruxhive-mcp"], { stdio: "inherit" });
    if (r.status !== 0) throw new Error("uv pip install cruxhive-mcp failed");
    return "uv";
  }
  if (hasBin("pip3") || hasBin("pip")) {
    const pip = hasBin("pip3") ? "pip3" : "pip";
    const r = spawnSync(pip, ["install", "cruxhive-mcp"], { stdio: "inherit" });
    if (r.status !== 0) throw new Error(`${pip} install cruxhive-mcp failed`);
    return pip;
  }
  throw new Error(
    "Neither uv nor pip found. Install uv (https://docs.astral.sh/uv/) or pip first."
  );
}

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

  cfg.mcpServers.cruxhive = MCP_ENTRY;
  writeFileSync(mcpPath, JSON.stringify(cfg, null, 2) + "\n");
  ok("cruxhive-mcp registered in .mcp.json");
}

function wireClaudeMd(cwd) {
  const claudePath = join(cwd, "CLAUDE.md");
  const contextPath = ".llm/CONTEXT.md";

  if (existsSync(claudePath)) {
    const content = readFileSync(claudePath, "utf8");
    if (content.includes("CONTEXT.md")) {
      info("CLAUDE.md already references CONTEXT.md");
      return;
    }
    writeFileSync(claudePath, content.trimEnd() + "\n\n<!-- CruxHive canonical context: .llm/CONTEXT.md -->\n");
    ok("CLAUDE.md patched with CONTEXT.md reference");
  } else {
    const target = contextPath;
    // Create a thin symlink — requires filesystem support
    try {
      require("fs").symlinkSync(target, claudePath);
      ok("CLAUDE.md → .llm/CONTEXT.md (symlink)");
    } catch {
      warn("Could not create CLAUDE.md symlink — copy .llm/CONTEXT.md to CLAUDE.md manually");
    }
  }
}

async function init(args) {
  const cwd = process.cwd();
  const date = new Date().toISOString().split("T")[0];
  const projectName = cwd.split("/").pop();

  console.log(`\n\x1b[1mCruxHive init\x1b[0m — ${projectName}`);

  // ─── .llm/ structure ─────────────────────────────────────────────────────
  step("1/4  Creating .llm/ structure");

  const dirs = [".llm", ".llm/plans", ".llm/context", ".llm/memory"];
  for (const dir of dirs) {
    mkdirSync(join(cwd, dir), { recursive: true });
  }
  ok("directories: .llm/ .llm/plans/ .llm/context/ .llm/memory/");

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

  // ─── install cruxhive-mcp ─────────────────────────────────────────────────
  step("2/4  Installing cruxhive-mcp");
  const installer = installMcp();
  ok(`cruxhive-mcp installed via ${installer}`);

  // ─── wire .mcp.json ───────────────────────────────────────────────────────
  step("3/4  Wiring .mcp.json");
  wireMcp(cwd);

  // ─── wire AI tool context files ───────────────────────────────────────────
  step("4/4  Wiring AI tools");
  wireClaudeMd(cwd);

  // ─── done ─────────────────────────────────────────────────────────────────
  console.log(`
\x1b[32m✓ CruxHive initialized in ${projectName}\x1b[0m

Next steps:
  1. Edit \x1b[36m.llm/CONTEXT.md\x1b[0m — describe your project, stack, and conventions
  2. Reload your AI tool — the cruxhive-mcp server is now available
  3. Run \x1b[36mcruxhive health\x1b[0m to see knowledge base status

MCP tools now available: context_radar, context_next_slice, context_write_plan, context_sync_memory
`);
}

module.exports = { init };
