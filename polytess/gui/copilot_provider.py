# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""GitHub Copilot backend for the studio assistants (Copilot SDK).

Uses the official ``github-copilot-sdk`` (``pip install
github-copilot-sdk``), which bundles the Copilot CLI. Authentication is
the user's Copilot login (one-time ``copilot login``, on GitHub
Enterprise ``copilot login --host https://<tenant>.ghe.com``) or a
GitHub token. The configured enterprise host is exported as
``COPILOT_GH_HOST``/``GH_HOST`` for the spawned CLI, which routes all
traffic to the tenant-local endpoints.

The session gets OUR system prompt via ``system_message: replace``.
Without a *workdir* the assistants are plain chat: every permission
request is denied. With a workdir (the code assistant's custom-library
folder) file reads/writes INSIDE that folder are approved automatically,
mirroring the Claude provider; shell commands, URLs and anything outside
the folder stay denied.
"""

from __future__ import annotations

import asyncio
import os


def path_within(path: str, root: str) -> bool:
    """True when *path* (absolute or relative to *root*) lies inside *root*."""
    if not root:
        return False
    root_abs = os.path.realpath(os.path.expanduser(root))
    candidate = os.path.expanduser(str(path or ""))
    if not os.path.isabs(candidate):
        candidate = os.path.join(root_abs, candidate)
    candidate = os.path.realpath(candidate)
    return candidate == root_abs or candidate.startswith(root_abs + os.sep)


def permission_allowed(request, workdir: str) -> bool:
    """Decide a Copilot permission request: only file reads/writes whose
    target lies inside *workdir* are approved; everything else (shell,
    URL fetches, MCP, files elsewhere) is denied."""
    if not workdir:
        return False
    kind = getattr(request, "kind", "")
    if kind == "read":
        return path_within(getattr(request, "resolved_path", None)
                           or getattr(request, "path", ""), workdir)
    if kind == "write":
        return path_within(getattr(request, "resolved_path", None)
                           or getattr(request, "file_name", ""), workdir)
    return False


def enterprise_env(github_host: str) -> dict[str, str]:
    """Environment overrides routing the Copilot CLI to a GHE tenant."""
    host = (github_host or "").strip().rstrip("/")
    if not host:
        return {}
    return {"COPILOT_GH_HOST": host, "GH_HOST": host}


def build_transcript_prompt(messages: list[dict]) -> str:
    """Flatten the chat history into one prompt (the SDK session is used
    stateless per request; earlier turns are provided as transcript)."""
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


def stream_copilot(system_prompt: str, messages: list[dict], *,
                   model: str, github_host: str = "",
                   github_token: str = "", workdir: str = "",
                   on_chunk=None, is_cancelled=None) -> str:
    """Run one streaming Copilot request; returns the full response text.

    With *workdir* set, the session runs in that directory and file
    reads/writes inside it are approved (the code assistant's custom
    library). Without it the session is plain chat.

    Raises RuntimeError with a helpful message when the SDK is missing
    or the user is not authenticated."""
    try:
        from copilot import CopilotClient
        from copilot.session import (PermissionDecisionApproveOnce,
                                     PermissionDecisionReject)
        from copilot.session_events import (AssistantMessageDeltaData,
                                            SessionIdleData)
    except ImportError:
        raise RuntimeError(
            "The 'github-copilot-sdk' package is not installed — run: "
            "pip install github-copilot-sdk") from None

    for key, value in enterprise_env(github_host).items():
        os.environ[key] = value

    async def drive() -> str:
        client_kwargs = {}
        if github_token.strip():
            client_kwargs["github_token"] = github_token.strip()
        parts: list[str] = []
        done = asyncio.Event()

        def decide_permission(request, _invocation=None):
            if permission_allowed(request, workdir):
                return PermissionDecisionApproveOnce()
            return PermissionDecisionReject(
                feedback="polytess only allows file access inside the "
                         "custom-library folder; no shell or network.")

        session_kwargs = {}
        if workdir:
            session_kwargs["working_directory"] = workdir

        async with CopilotClient(**client_kwargs) as client:
            session = await client.create_session(
                model=model,
                streaming=True,
                on_permission_request=decide_permission,
                system_message={"mode": "replace",
                                "content": system_prompt},
                **session_kwargs,
            )
            async with session:
                def on_event(event):
                    data = getattr(event, "data", None)
                    if isinstance(data, AssistantMessageDeltaData):
                        delta = data.delta_content or ""
                        parts.append(delta)
                        if on_chunk is not None:
                            on_chunk(delta)
                    elif isinstance(data, SessionIdleData):
                        done.set()

                session.on(on_event)
                await session.send(build_transcript_prompt(messages))
                while not done.is_set():
                    if is_cancelled is not None and is_cancelled():
                        break
                    try:
                        await asyncio.wait_for(done.wait(), timeout=0.2)
                    except asyncio.TimeoutError:
                        pass
        return "".join(parts)

    try:
        return asyncio.run(drive())
    except RuntimeError:
        raise
    except Exception as exc:
        message = str(exc)
        if "auth" in message.lower() or "login" in message.lower() or \
                "401" in message or "credentials" in message.lower():
            host_hint = f" --host {github_host}" if github_host.strip() else ""
            raise RuntimeError(
                f"Copilot is not authenticated — run once: copilot "
                f"login{host_hint}  (or set a GitHub token in "
                f"Settings).") from exc
        raise RuntimeError(f"Copilot request failed: "
                           f"{exc.__class__.__name__}: {exc}") from exc
