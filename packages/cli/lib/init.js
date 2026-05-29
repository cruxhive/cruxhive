"use strict";

const { spawnSync } = require("child_process");
const { mkdirSync, writeFileSync, existsSync, readFileSync, symlinkSync } = require("fs");
const { homedir } = require("os");
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

// ─── slash command parity (Claude Code + OpenCode) ────────────────────────

const SLASH_COMMANDS = {
  radar: {
    description: "Plan coverage scan — surface git work that has no plan behind it. Usage: /radar [days]",
    body: `Call the \`context_radar\` MCP tool to scan recent git history and map commits to plan areas.

- If a number was passed as the first argument, pass it as the \`days\` parameter.
- Otherwise use the default (7 days).

Present the report output verbatim — it's already formatted for terminal display.

If there are UNCOVERED items, suggest \`/write-plan <area>\` to register them. If items are UNCLASSIFIED, suggest adding entries to \`.claude/areas.toml\` or \`.cruxhive/areas.toml\`.`,
  },
  "next-slice": {
    description: "Find the next unblocked work slice from the active plan. Usage: /next-slice [area]",
    body: `Call the \`context_next_slice\` MCP tool.

- If an argument was passed, use it as the \`area\` parameter (a plan keyword like \`cicd\` or \`auth\`).
- Otherwise leave \`area\` empty — the tool reads \`.llm/plans/active.md\`.

Present the result as-is. Do NOT start implementing — wait for the user to confirm scope.`,
  },
  review: {
    description: "List CruxHive proposals awaiting human approval.",
    body: `Call the \`context_review\` MCP tool and present its output verbatim.

If the queue is non-empty, ask the user whether they'd like to approve or reject each entry interactively — for each, propose calling \`context_approve\` with their git username or \`context_reject\`.`,
  },
  propose: {
    description: "Propose a new knowledge entry for human review. Usage: /propose",
    body: `Help the user write a new CruxHive knowledge entry. Ask for:

1. **Type** — one of: fact, decision, plan, pattern, constraint, research, outcome
2. **Topic** — one to three words (e.g. "auth", "database-schema", "ci-cd-tokens")
3. **Scope** — personal | project | org (default: project)
4. **Content** — the body. Explain what's true, when, and why.

Then call the \`context_propose\` MCP tool with those arguments. After it returns, remind the user that the entry is pending until approved via \`/review\` or \`cruxhive ui\`.`,
  },
  "write-plan": {
    description: "Write a new plan file to .llm/plans/ and register it in active.md.",
    body: `Help the user draft a plan. Ask for:

1. **Plan name** — kebab-case (e.g. \`cicd-fleet-architecture\`, \`auth-rewrite\`)
2. **Goal** — one sentence
3. **Phases** — phase headings with bulleted unchecked tasks (\`- [ ] ...\`)
4. **Open questions** — anything unresolved

Then call the \`context_write_plan\` MCP tool with \`plan_name\` and \`content\` (the full markdown).`,
  },
  extract: {
    description: "Distill the current conversation into proposed CruxHive knowledge entries. Dedupes, classifies, and queues for /review.",
    body: `You are extracting durable knowledge from the conversation so far. Make zero file changes directly — only call \`context_search\` (read) and \`context_propose\` (queue for human approval).

## Step 1 — Identify candidates

Re-read the conversation. List items that meet ALL of:

- Concrete and stable (not "let me try X" or "we considered Y")
- Established by the user (or confirmed by their approval)
- Worth referencing in future sessions (not session-specific debugging output)
- Not a secret, token, password, or other credential — silently skip these

Classify each as exactly one of:

- **fact** — objective truth ("API runs on port 8000")
- **decision** — a choice made between alternatives ("we use PostgreSQL, not MySQL")
- **constraint** — a rule that should not be violated ("never log raw tokens")
- **pattern** — a reusable approach ("for new features, scaffold via stack.sh")
- **plan** — multi-step intent for future work
- **research** — a finding from investigation
- **outcome** — a result observed

Skip: questions, half-thoughts, debugging traces, hypotheticals, things you (the AI) said that the user did not confirm.

If the conversation has fewer than 5 substantive exchanges, stop and say: "Not enough conversation to extract from yet."

## Step 2 — Dedup against existing knowledge

For EACH candidate, call \`context_search\` with the candidate's topic plus 2–3 keywords. Look at the top result.

- If a similar entry already exists AND the new info is the same → mark \`[DUP]\` (skip).
- If a similar entry exists BUT the new info refines or contradicts it → mark \`[UPDATE: <path>]\`.
- If no similar entry → mark \`[NEW]\`.

## Step 3 — Present for review

Print candidates as a numbered list, terse:

\`\`\`
1. [NEW] [decision] auth — Logto OIDC for all user-facing apps
2. [NEW] [constraint] secrets — never commit API keys to git (use Vault)
3. [DUP] hetzner — already covered in .llm/memory/platform_refs.md
4. [UPDATE: .llm/decisions/db.md] [decision] database — switching from MySQL to PostgreSQL
5. [NEW] [fact] hosts — platform IP is 91.99.212.250
\`\`\`

Then ask exactly: "Which would you like to propose? (numbers, 'all-new', or 'none')"

## Step 4 — File approved candidates

For each user-selected \`[NEW]\` candidate, call \`context_propose\` with:

- \`type\` — the classification
- \`topic\` — 1-3 words (e.g. "auth", "database-schema")
- \`content\` — the full body, including context and the *why*. NOT just the headline.
- \`scope\` — \`personal\` if it's a developer preference, \`org\` if it crosses projects, otherwise \`project\` (default)

For \`[UPDATE]\` candidates, do NOT call \`context_propose\`. Instead show the existing entry's path and suggest the user edit it directly.

## Step 5 — Wrap up

After all approved candidates are filed, print a one-line summary:

> Filed N new candidate(s) to \`.llm/pending/\`. Run \`/review\` (or \`cruxhive ui\`) to approve or reject.

## Output style

Terse. No prose explanations. The candidates list + the review question + the final summary line are the only required output.`,
  },
};

function writeCommandFile(filePath, name, def, dialect) {
  if (existsSync(filePath)) {
    info(`${dialect}/commands/${name}.md already exists — skipped`);
    return;
  }
  mkdirSync(dirname(filePath), { recursive: true });
  // Claude Code uses { name, description }; OpenCode uses { description }
  const fm = dialect === "claude"
    ? `---\nname: ${name}\ndescription: ${def.description}\n---\n\n`
    : `---\ndescription: ${def.description}\n---\n\n`;
  writeFileSync(filePath, fm + def.body + "\n");
  ok(`${dialect}/commands/${name}.md created`);
}

function wireSlashCommands(cwd) {
  for (const [name, def] of Object.entries(SLASH_COMMANDS)) {
    writeCommandFile(join(cwd, ".claude", "commands", `${name}.md`), name, def, ".claude");
    writeCommandFile(join(cwd, ".opencode", "commands", `${name}.md`), name, def, ".opencode");
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

function patchGitignore(cwd) {
  const ig = join(cwd, ".gitignore");
  const entries = [
    "# CruxHive: local knowledge index + usage log (do not commit)",
    ".llm/cruxhive.db",
    ".llm/cruxhive.db-shm",
    ".llm/cruxhive.db-wal",
    ".llm/pending/.cache",
  ];
  if (!existsSync(ig)) {
    writeFileSync(ig, entries.join("\n") + "\n");
    ok(".gitignore created with CruxHive entries");
    return;
  }
  const cur = readFileSync(ig, "utf8");
  if (cur.includes("cruxhive.db")) {
    info(".gitignore already has CruxHive entries");
    return;
  }
  writeFileSync(ig, cur.trimEnd() + "\n\n" + entries.join("\n") + "\n");
  ok(".gitignore patched with CruxHive entries");
}

// ─── main ──────────────────────────────────────────────────────────────────

function bootstrapPersonal() {
  const personalDir = join(homedir(), ".cruxhive", "personal");
  const readme = join(personalDir, "CONTEXT.md");
  if (existsSync(readme)) {
    info("~/.cruxhive/personal/ already exists");
    return;
  }
  mkdirSync(personalDir, { recursive: true });
  const date = new Date().toISOString().split("T")[0];
  writeFileSync(readme,
    `---
type: fact
scope: personal
topic: personal-preferences
valid_at: ${date}
confidence: high
source: human
approved_by: ~
---

# Personal preferences

> Edit this file with your cross-project developer preferences.
> These are indexed into every CruxHive project on this machine, but never
> committed to any project repo. They're yours alone.

## Coding style

- Add your personal coding preferences here

## Tools

- Editor, shell, terminal preferences

## Communication

- How you like AI to communicate with you (terse, verbose, formal, etc.)
`);
  ok(`~/.cruxhive/personal/CONTEXT.md created (visible to every project)`);
}

async function init(_args) {
  const cwd = process.cwd();
  const date = new Date().toISOString().split("T")[0];
  const projectName = cwd.split("/").pop();

  console.log(`\n\x1b[1mCruxHive init\x1b[0m — ${projectName}`);

  // 0. Personal layer (one-time bootstrap, machine-wide)
  step("0/7  Personal layer (~/.cruxhive/personal/)");
  bootstrapPersonal();

  // 1. .llm/ structure
  step("1/7  Creating .llm/ structure");
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
  step("2/7  Installing cruxhive-mcp");
  const installer = installMcp();
  if (installer) ok(`cruxhive-mcp installed via ${installer}`);

  // 3. wire .mcp.json
  step("3/7  Wiring .mcp.json");
  wireMcp(cwd);

  // 4. wire AI tools
  step("4/7  Wiring AI tools");
  wireAiTools(cwd);

  // 5. Slash command parity — same commands work in Claude Code AND OpenCode
  step("5/7  Wiring slash commands (Claude Code + OpenCode)");
  wireSlashCommands(cwd);

  // 6. .llm/memory/ for workspace platform_refs (filled by sync)
  step("6/7  Workspace memory dir (.llm/memory/)");
  const memDir = join(cwd, ".llm", "memory");
  mkdirSync(memDir, { recursive: true });
  ok(".llm/memory/ ready (will be filled by `cruxhive sync`)");

  // 7. .gitignore — keep cruxhive.db out of git
  step("7/7  .gitignore");
  patchGitignore(cwd);

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
