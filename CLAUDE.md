# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A minimal FastAPI HTTP bridge that wraps the local `claude` CLI binary, enabling programmatic REST API access to Claude Code. It spawns `claude --print --output-format json` as a subprocess per request and returns structured responses.

## Running the Server

```bash
pip install -r requirements.txt
python main.py
```

Server starts on `http://localhost:8000` with hot reload enabled.

## Architecture

Everything lives in `main.py`. Key elements:

- **`CLAUDE_BIN`** — detected at startup via `shutil.which("claude")`; server refuses to start if not found
- **`run_claude(req)`** — core async function that builds the CLI command, spawns a subprocess via `asyncio.create_subprocess_exec`, and parses the JSON output
- **`POST /prompt`** — main endpoint; accepts `PromptRequest`, returns `PromptResponse`
- **`GET /health`** — returns status and the resolved claude binary path

### Request/Response flow

`PromptRequest` → `run_claude()` → `claude --print --output-format json [flags] "<prompt>"` subprocess → parse stdout JSON → `PromptResponse`

`PromptRequest` fields: `prompt` (required), `cwd`, `session_id`, `system_prompt`, `allowed_tools`, `disallowed_tools`

`PromptResponse` fields: `response` (the result text), `session_id`, `cost_usd`

### Session continuity

Pass `session_id` from a previous `PromptResponse` back into `PromptRequest` to continue a conversation (maps to `--resume`). Claude Code manages session state; this server is otherwise stateless.

### Tool control

Three layers, in priority order:
1. `disallowed_tools` in request body — hard-block, wins over everything (`--disallowedTools`)
2. `allowed_tools` in request body — auto-approve without prompting (`--allowedTools`)
3. `.claude/settings.json` (project root) or `~/.claude/settings.json` — persistent defaults

Tool name examples: `"Read"`, `"Edit"`, `"Write"`, `"Bash(git:*)"`, `"Bash(npm test)"`, `"Bash(rm:*)"` (good to disallow).

## Dependencies

- `fastapi` + `uvicorn[standard]` only — no direct Anthropic SDK usage; auth is handled by the locally installed `claude` CLI (OAuth, not API keys)
