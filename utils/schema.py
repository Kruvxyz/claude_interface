from typing import Optional

from pydantic import BaseModel


class InboundMessage(BaseModel):
    channel: str                    # "whatsapp" | "telegram"
    sender_id: str                  # unique per channel
    sender_role: str                # "owner" | "staff" | "client" | "unknown"
    context_type: str               # "private" | "group"
    group_id: Optional[str] = None
    is_mention: bool
    priority_flag: bool             # urgent / hot keyword detected
    text: str                       # clean text, @bot stripped
    media: Optional[dict] = None    # {"type": "image", "url": "...", "mime": "image/jpeg"}
    raw_timestamp: int
    session_id: Optional[str] = None  # filled after DB lookup


class PromptRequest(BaseModel):
    prompt: str

    # Working directory — Claude Code reads/writes relative to this path
    cwd: str | None = None

    # Pass the session_id from a previous response to continue a conversation
    session_id: str | None = None

    # Optional system prompt override
    system_prompt: str | None = None

    # Tools Claude is allowed to use without asking.
    # Examples: ["Read", "Edit", "Bash(git:*)", "Bash(npm test)"]
    # Falls back to whatever is set in .claude/settings.json if omitted.
    allowed_tools: list[str] | None = None

    # Tools Claude must never use, even if listed in allowed_tools.
    # Deny always wins. Example: ["Bash(rm:*)", "Bash(curl:*)"]
    disallowed_tools: list[str] | None = None


class PromptResponse(BaseModel):
    response: str
    session_id: str | None
    cost_usd: float | None
