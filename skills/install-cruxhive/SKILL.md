---
name: install-cruxhive
description: Install and set up CruxHive (a shared, human-approved AI knowledge base) in the current project. Trigger when the user asks to "set up cruxhive", "install cruxhive", "add cruxhive to this project", or wants their AI tools to remember project knowledge between sessions.
---

You're setting up CruxHive for a human who wants their AI tools to remember project knowledge across sessions, with a human approval gate. Follow this sequence exactly — every step here was verified by actually running it, including two steps that catch mistakes an AI commonly makes on this exact task. Don't skip verification, and don't improvise steps that aren't listed.

## 0. Check if it's already set up

`cat .mcp.json 2>/dev/null | grep -q '"cruxhive"'` — if this matches, CruxHive is already wired into this project. Don't re-run `init` (it's safe to re-run, but redundant); skip to step 6 to pick up where a prior setup left off.

## 1. Check prerequisites

- `node --version` — need 18+.
- `uv --version` — need `uv`. If missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- Confirm you're inside a git repository (`git rev-parse --is-inside-work-tree`) — CruxHive requires one.

## 2. Install globally, not via `npx`

```
npm install -g @cruxhive/cli
```

This matters and is easy to get wrong: `npx @cruxhive/cli init` also works for the *install* step, but doesn't leave `cruxhive` on PATH afterward, so every command after that would fail with `command not found` unless you keep re-prefixing with `npx @cruxhive/cli`. `npm install -g` avoids that entirely — do this, not npx, when you're the one running the commands.

## 3. Verify before continuing

```
cruxhive --help
```

Must print usage, not an error. **Do not assume this worked just because the install command exited 0** — CruxHive itself shipped a bug where this exact assumption was wrong (an npm install can silently fail to update PATH in some shells). If it fails, check `npm bin -g` is actually on your `PATH`, fix that, and re-verify before moving on. Don't fall back to guessing at differently-named commands — see the warning in step 6 about why that's specifically dangerous for `review`.

## 4. Initialize, from the project's git root

```
cruxhive init
```

Read its output. It self-reports 8 steps (`.llm/` scaffold, installing the Python MCP server via `uv`, wiring `.mcp.json`, wiring `CLAUDE.md`/`AGENTS.md`/etc., slash commands, workspace memory dir, `.gitignore`, git hooks). If any step reports an error rather than `✓` or `·`, stop and report the exact error — don't proceed past a failed step.

## 5. Confirm it's healthy

```
cruxhive doctor
```

Should report no failures. If it does, fix what it names before continuing — it checks exactly the things steps 2-4 set up.

## 6. Describe the project

Edit `.llm/CONTEXT.md` (created by `init`) with a few real sentences: what this project is, its stack, and its conventions. This is what makes retrieval useful later — don't leave the placeholder text in place, and don't skip this step even if you're in a hurry.

## 7. Build the index

```
cruxhive index
```

## 8. Prove the loop actually works — don't just tell the user it's done

This is the step most likely to be skipped, and it's the one that actually matters — CruxHive's entire value proposition is the human approval gate, so confirm it's real rather than assuming the install succeeded:

1. **Propose one real fact** you've already learned about this project (from reading its code, its README, or this conversation) — via the `context_propose` MCP tool if your client already sees it (you may need to reload/restart your MCP connection after step 4 wired `.mcp.json`), otherwise `cruxhive propose` interactively.
2. **Confirm it is NOT yet retrievable**: `cruxhive search "<topic from what you just proposed>"`. It must **not** come back. This is the approval gate working correctly — do not treat this as a bug, and do not try to "fix" it by approving the entry yourself.
3. **Tell the user it's waiting, and stop there**: *"N proposal(s) pending your review — run `cruxhive review` to approve or reject."* **Do not approve it yourself.** The one exception: the user has explicitly told you, in this conversation, that they've enabled `cruxhive solo --enable` (meant for single-approver projects) — if they haven't said that, don't assume it, and don't enable it on their behalf either. Approval being a human action is the entire point of the tool; silently bypassing it defeats the reason it was installed.

## 9. Report back to the user

Summarize: what got installed, where `.llm/` lives, that a human needs to run `cruxhive review` (or `cruxhive ui` for a browser dashboard at `localhost:3847`) to start approving what gets learned, and confirm step 8's gate held.

## If anything fails

Run `cruxhive doctor` and report its exact output. Don't retry blindly, don't skip ahead to a later step hoping it'll self-resolve, and don't invent a workaround command that isn't listed above — in particular, the hyphenated `cruxhive-*` Python entry points that `init` installs alongside the `cruxhive` CLI are **not** a safe drop-in replacement for every subcommand. `cruxhive-review`, for one, just dumps pending items as raw JSON for the `cruxhive` CLI's own internal use — it is not the interactive/bulk approval flow a human would actually want, and running it directly and reporting success would be misleading the user about what happened.
