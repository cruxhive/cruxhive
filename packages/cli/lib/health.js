"use strict";

const { existsSync, readdirSync, readFileSync, statSync } = require("fs");
const { join } = require("path");

function countFiles(dir) {
  if (!existsSync(dir)) return 0;
  try {
    return readdirSync(dir).filter((f) => f.endsWith(".md")).length;
  } catch {
    return 0;
  }
}

function staleCheck(filePath, maxDays = 90) {
  if (!existsSync(filePath)) return null;
  const mtime = statSync(filePath).mtimeMs;
  const ageDays = (Date.now() - mtime) / 86400000;
  return ageDays > maxDays ? Math.floor(ageDays) : null;
}

function parseFrontmatter(content) {
  const m = content.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return {};
  const obj = {};
  for (const line of m[1].split("\n")) {
    const [k, ...rest] = line.split(":");
    if (k && rest.length) obj[k.trim()] = rest.join(":").trim();
  }
  return obj;
}

function badge(ok) {
  return ok ? "\x1b[32m✓\x1b[0m" : "\x1b[31m✗\x1b[0m";
}

function fmt(label, value, note = "") {
  const pad = " ".repeat(Math.max(0, 14 - label.length));
  const n = note ? `  \x1b[90m${note}\x1b[0m` : "";
  console.log(`  ${label}${pad}${value}${n}`);
}

async function health(_args) {
  const cwd = process.cwd();
  const date = new Date().toISOString().split("T")[0];
  const project = cwd.split("/").pop();

  console.log(`\n\x1b[1mcruxhive health\x1b[0m — ${date} · ${project}`);
  console.log("  " + "─".repeat(44));

  const contextExists = existsSync(join(cwd, ".llm", "CONTEXT.md"));
  const mcpConfigured = (() => {
    const p = join(cwd, ".mcp.json");
    if (!existsSync(p)) return false;
    try {
      const cfg = JSON.parse(readFileSync(p, "utf8"));
      return !!(cfg.mcpServers?.cruxhive);
    } catch {
      return false;
    }
  })();

  const plansDir = join(cwd, ".llm", "plans");
  const memoryDir = join(cwd, ".llm", "memory");
  const contextDir = join(cwd, ".llm", "context");

  const planCount = countFiles(plansDir) - (existsSync(join(plansDir, "active.md")) ? 1 : 0);
  const memCount = countFiles(memoryDir);
  const contextCount = countFiles(contextDir);

  // Count all entries across .llm/ tree
  let totalEntries = 0;
  let constraintCount = 0;
  let pendingCount = 0;
  let stalePaths = [];

  const scanDir = (dir) => {
    if (!existsSync(dir)) return;
    for (const f of readdirSync(dir)) {
      if (!f.endsWith(".md")) continue;
      const p = join(dir, f);
      try {
        const content = readFileSync(p, "utf8");
        const fm = parseFrontmatter(content);
        if (fm.type) {
          totalEntries++;
          if (fm.type === "constraint") constraintCount++;
          if (!fm.approved_by || fm.approved_by === "~") pendingCount++;
        }
        const stale = staleCheck(p, 90);
        if (stale) stalePaths.push({ path: f, days: stale });
      } catch {}
    }
  };

  scanDir(memoryDir);
  scanDir(contextDir);
  scanDir(plansDir);

  // Output
  fmt("CONTEXT.md", `${badge(contextExists)} ${contextExists ? "present" : "missing"}`,
    contextExists ? "" : "run: cruxhive init");
  fmt("MCP server", `${badge(mcpConfigured)} ${mcpConfigured ? "configured" : "not wired"}`,
    mcpConfigured ? "" : "run: cruxhive init");

  console.log("  " + "─".repeat(44));

  fmt("Plans", planCount.toString());
  fmt("Memory files", memCount.toString());
  fmt("Context files", contextCount.toString());
  if (totalEntries > 0) {
    fmt("Typed entries", totalEntries.toString(), `${constraintCount} constraints`);
  }
  if (pendingCount > 0) {
    fmt("Pending approval", pendingCount.toString(), "\x1b[33mapproval needed\x1b[0m");
  }
  if (stalePaths.length > 0) {
    fmt("Stale (>90d)", stalePaths.length.toString(), stalePaths.map((s) => s.path).join(", "));
  }

  console.log("  " + "─".repeat(44));

  if (!contextExists || !mcpConfigured) {
    console.log("\n  Run \x1b[36mcruxhive init\x1b[0m to finish setup.\n");
  } else {
    console.log("\n  \x1b[32m✓ Ready.\x1b[0m MCP tools: context_radar, context_next_slice, context_write_plan\n");
  }
}

module.exports = { health };
