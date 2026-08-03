# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Claude backend for the studio assistants (Claude Agent SDK).

Uses the official ``claude-agent-sdk`` (``pip install claude-agent-sdk``),
which bundles the Claude Code CLI — no separate Node/npm install needed.
Authentication is the user's one-time ``claude login`` (Claude.ai account
or Anthropic Console); there is no API-key field, unlike the previous
plain Anthropic-API integration.

The assistants are plain chat: every built-in tool is disabled
(``allowed_tools=[]``) so the session only replies with text, exactly like
before — it does not read or write files on its own.
"""

from __future__ import annotations

import asyncio


def build_transcript_prompt(messages: list[dict]) -> str:
    """Flatten the chat history into one prompt (each request is a fresh,
    stateless ``query()`` call; earlier turns are given as transcript)."""
    if len(messages) == 1:
        return str(messages[0].get("content", ""))
    parts = ["Conversation so far:"]
    for message in messages[:-1]:
        speaker = "User" if message.get("role") == "user" else "Assistant"
        parts.append(f"{speaker}: {message.get('content', '')}")
    parts.append("")
    parts.append("Current user message — answer this:")
    parts.append(str(messages[-1].get("content", "")))
    return "\n".join(parts)


def stream_claude_agent(system_prompt: str, messages: list[dict], *,
                        model: str, on_chunk=None,
                        is_cancelled=None) -> str:
    """Run one Claude Agent SDK request; returns the full response text.

    "Streaming" here is per-assistant-message, not per-token — the SDK
    does not expose token-level deltas on the documented query() path.

    Raises RuntimeError with a helpful message when the SDK/CLI is
    missing or the user is not authenticated."""
    try:
        from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions,
                                      CLIConnectionError, CLINotFoundError,
                                      ProcessError, TextBlock, query)
    except ImportError:
        raise RuntimeError(
            "The 'claude-agent-sdk' package is not installed — run: "
            "pip install claude-agent-sdk") from None

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model or None,
        allowed_tools=[],          # assistants never execute tools
        permission_mode="default",
    )

    async def drive() -> str:
        parts: list[str] = []
        prompt = build_transcript_prompt(messages)
        async for message in query(prompt=prompt, options=options):
            if is_cancelled is not None and is_cancelled():
                break
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text:
                        parts.append(block.text)
                        if on_chunk is not None:
                            on_chunk(block.text)
        return "".join(parts)

    try:
        return asyncio.run(drive())
    except CLINotFoundError:
        raise RuntimeError(
            "The Claude Code CLI could not be found — reinstall with: "
            "pip install --force-reinstall claude-agent-sdk") from None
    except CLIConnectionError as exc:
        raise RuntimeError(
            "Not authenticated — run once in a terminal: claude login "
            f"({exc})") from exc
    except ProcessError as exc:
        raise RuntimeError(f"Claude Agent SDK process failed "
                           f"(exit {exc.exit_code}): {exc}") from exc
    except RuntimeError:
        raise
    except Exception as exc:
        message = str(exc)
        if "auth" in message.lower() or "login" in message.lower():
            raise RuntimeError(
                "Not authenticated — run once in a terminal: "
                "claude login") from exc
        raise RuntimeError(f"Claude Agent SDK request failed: "
                           f"{exc.__class__.__name__}: {exc}") from exc
