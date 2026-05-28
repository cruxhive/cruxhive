"use strict";

const { spawnSync, spawn } = require("child_process");
const { existsSync } = require("fs");

const PORT = 3847;

function ok(msg)   { console.log(`  \x1b[32m✓\x1b[0m  ${msg}`); }
function info(msg) { console.log(`  \x1b[36m·\x1b[0m  ${msg}`); }
function err(msg)  { console.log(`  \x1b[31m✗\x1b[0m  ${msg}`); }

function openBrowser(url) {
  const platform = process.platform;
  const cmd = platform === "darwin" ? "open" : platform === "win32" ? "start" : "xdg-open";
  spawnSync(cmd, [url], { stdio: "ignore" });
}

function uvicornCmd() {
  // Prefer the uvicorn inside the uv-managed cruxhive-mcp tool environment
  const uv = spawnSync("uv", ["tool", "run", "--from", "cruxhive-mcp", "uvicorn", "--version"], { stdio: "pipe" });
  if (uv.status === 0) return ["uv", "tool", "run", "--from", "cruxhive-mcp", "uvicorn"];
  const direct = spawnSync("uvicorn", ["--version"], { stdio: "pipe" });
  if (direct.status === 0) return ["uvicorn"];
  return null;
}

async function ui(args) {
  const cwd = process.cwd();
  const serve = args.includes("--serve");

  console.log(`\n\x1b[1mcruxhive ui\x1b[0m — approval dashboard`);

  if (!existsSync(`${cwd}/.llm/cruxhive.db`)) {
    console.log(`\n  \x1b[33m!\x1b[0m  Knowledge base not indexed yet.`);
    console.log(`       Run: \x1b[36mcruxhive index\x1b[0m (or context_index MCP tool)\n`);
  }

  const uvcmd = uvicornCmd();
  if (!uvcmd) {
    err("uvicorn not found — install the [ui] extra:");
    console.log(`\n       \x1b[36muv tool install "cruxhive-mcp[ui]"\x1b[0m\n`);
    process.exit(1);
  }

  const url = `http://localhost:${PORT}`;
  info(`Starting approval queue at ${url}`);

  const [bin, ...binArgs] = uvcmd;
  const proc = spawn(
    bin,
    [
      ...binArgs,
      "cruxhive_mcp.ui:app",
      "--host", "0.0.0.0",
      "--port", String(PORT),
      "--factory",
    ],
    {
      cwd,
      stdio: "inherit",
      env: { ...process.env, CRUXHIVE_ROOT: cwd },
    }
  );

  proc.on("error", (e) => {
    err(`Failed to start server: ${e.message}`);
    process.exit(1);
  });

  // Give the server a moment to bind, then open browser
  setTimeout(() => {
    ok(`Server running at ${url}`);
    openBrowser(url);
  }, 1200);

  process.on("SIGINT", () => {
    proc.kill();
    process.exit(0);
  });
}

module.exports = { ui };
