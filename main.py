"""
Claude Code → FastAPI Bridge
Spawns your LOCAL `claude` CLI binary per request using --print --output-format json.

Auth:    uses your existing `claude` login (OAuth) — no API key needed in this server
Tools:   controlled via allowed_tools / disallowed_tools per request, or settings.json
Session: stateless by default; pass session_id to continue a conversation

Endpoints:
  POST /prompt   { "prompt", "cwd", "session_id", "allowed_tools", "disallowed_tools" }
  GET  /health

─── Tool permission quick reference ──────────────────────────────────────────────────
  Persistent (all requests):  .claude/settings.json  in your project root
                              ~/.claude/settings.json for all projects

  Per-request (in body):      allowed_tools   →  auto-approve these tools
                              disallowed_tools →  hard-block these tools (wins over allow)

  Tool name examples:
    "Read"                 read any file
    "Edit"                 edit files
    "Write"                create/overwrite files
    "Bash(git:*)"          any git command
    "Bash(npm test)"       exactly `npm test`
    "Bash(ls:*)"           any ls invocation
    "Bash(rm:*)"           ← good one to DISALLOW
──────────────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import json
import shutil

from fastapi import FastAPI, HTTPException, Request

from utils.schema import InboundMessage, PromptRequest, PromptResponse
from utils.telegram_utils import parse_telegram

app = FastAPI(title="Claude Code Local API", version="1.0.0")

# ── Locate the `claude` binary once at startup ────────────────────────────

CLAUDE_BIN = shutil.which("claude")


@app.on_event("startup")
def check_claude_binary():
    if not CLAUDE_BIN:
        raise RuntimeError(
            "`claude` binary not found in PATH.\n"
            "Install with:  npm install -g @anthropic-ai/claude-code\n"
            "Then log in:   claude"
        )
    print(f"✓ Claude Code binary: {CLAUDE_BIN}")


# ── Core: run claude CLI as subprocess ───────────────────────────────────

async def run_claude(req: PromptRequest) -> dict:
    """
    Builds and runs:
        claude --print --output-format json
               [--resume <session_id>]
               [--system-prompt "..."]
               [--allowedTools "Read,Edit,Bash(git:*)"]
               [--disallowedTools "Bash(rm:*)"]
               "<prompt>"

    Returns the parsed JSON object from Claude Code.
    """
    cmd = [
        CLAUDE_BIN,
        "--print",                  # headless / non-interactive
        "--output-format", "json",  # → {result, session_id, cost_usd, ...}
    ]

    if req.session_id:
        cmd += ["--resume", req.session_id]

    if req.system_prompt:
        cmd += ["--system-prompt", req.system_prompt]

    if req.allowed_tools:
        # Claude expects a comma-separated string: "Read,Edit,Bash(git:*)"
        cmd += ["--allowedTools", ",".join(req.allowed_tools)]

    if req.disallowed_tools:
        cmd += ["--disallowedTools", ",".join(req.disallowed_tools)]

    cmd.append(req.prompt)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=req.cwd,   # None → inherits server's working directory
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip() or "claude exited with a non-zero status"
        raise RuntimeError(f"Claude Code error (exit {proc.returncode}): {err}")

    raw = stdout.decode().strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse Claude Code JSON output: {exc}\n\nRaw:\n{raw}"
        )


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "claude_bin": CLAUDE_BIN}


@app.post("/telegram/webhook", response_model=InboundMessage)
async def telegram_webhook(request: Request):
    """
    Telegram Bot webhook endpoint.
    Telegram POSTs Update objects here; we parse them into InboundMessage.
    Register with: https://api.telegram.org/bot<TOKEN>/setWebhook?url=<your-url>/telegram/webhook
    """
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        msg = parse_telegram(update)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Cannot parse Telegram update: {exc}")

    # TODO: look up session_id and sender_role from DB using msg.sender_id / msg.group_id

    return msg


@app.post("/prompt", response_model=PromptResponse)
async def prompt_endpoint(body: PromptRequest):
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    try:
        data = await run_claude(body)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return PromptResponse(
        response=data.get("result", ""),
        session_id=data.get("session_id"),
        cost_usd=data.get("cost_usd"),
    )


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
