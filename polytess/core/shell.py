# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Console-command execution honoring the global command server.

With ``use_command_server`` active every console command runs as::

    ssh <server> 'setenv A "x" ; cd "workdir" && command'

so Linux tools (abaqus, simpack-flx, ...) work from a Windows workstation
too (Windows 10/11 ships the OpenSSH client). The remote side is the user's
login shell — **tcsh** here — so only tcsh-safe syntax is generated
(``setenv``, ``cd "..." && ...``; no bash-isms). Running ON the command
server itself is detected via the hostname and short-circuits to plain
local execution.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import socket

from polytess.core.app_settings import AppSettings


def remote_server() -> str:
    """The active command server, or '' when commands run locally."""
    settings = AppSettings.instance()
    if not settings.get("use_command_server"):
        return ""
    server = str(settings.get("command_server") or "").strip()
    if not server:
        return ""
    host = socket.gethostname().split(".")[0].lower()
    if host == server.split(".")[0].lower():
        return ""          # already on the command server
    return server


SHELLS = ("tcsh", "bash", "cmd")     # supported remote login-shell dialects


def wrap_for_shell(command: str, workdir: str | None = None,
                   env: dict | None = None, shell: str = "tcsh") -> str:
    """One remote command line in the target login shell's dialect.

    The remote side of ssh always runs the user's LOGIN shell — the
    dialect is a property of the target machine, not a choice:
    ``tcsh`` (setenv), ``bash``/POSIX (export) or ``cmd`` for Windows
    remotes (OpenSSH on Windows starts cmd.exe: set + cd /d)."""
    parts = []
    if shell == "cmd":
        for name, value in (env or {}).items():
            parts.append(f'set "{name}={value}" &&')
        if workdir:
            parts.append(f'cd /d "{workdir}" &&')
    elif shell == "bash":
        for name, value in (env or {}).items():
            parts.append(f'export {name}="{value}" ;')
        if workdir:
            parts.append(f'cd "{workdir}" &&')
    else:                                          # tcsh / csh
        for name, value in (env or {}).items():
            parts.append(f'setenv {name} "{value}" ;')
        if workdir:
            parts.append(f'cd "{workdir}" &&')
    parts.append(command)
    return " ".join(parts)


def remote_command(command: str, workdir: str | None = None,
                   env: dict | None = None) -> str:
    """tcsh-safe remote command line (the global command server's shell)."""
    return wrap_for_shell(command, workdir, env, shell="tcsh")


def build_argv(command: str, workdir: str | None = None,
               env: dict | None = None, force_local: bool = False
               ) -> tuple[list[str], str | None, dict | None, str]:
    """(argv, cwd, env, server) for a console command — via ssh when a
    command server is configured, plain local otherwise (server == '')."""
    server = "" if force_local else remote_server()
    if server:
        settings = AppSettings.instance()
        options = shlex.split(str(settings.get("ssh_options") or ""))
        argv = ["ssh", *options, server, remote_command(command, workdir, env)]
        return argv, None, None, server
    argv = shlex.split(command, posix=(os.name != "nt"))
    full_env = None
    if env:
        full_env = dict(os.environ)
        full_env.update({str(k): str(v) for k, v in env.items()})
    return argv, workdir or None, full_env, ""


# --------------------------------------------------------------------------- #
# solver profiles (MKS / FEM) — per-target run mode, shell dialect, mapping
# --------------------------------------------------------------------------- #

def solver_profile(kind: str) -> dict:
    """Settings of one solver profile; *kind* is ``"mks"`` or ``"fem"``."""
    settings = AppSettings.instance()
    return {
        "command": str(settings.get(f"{kind}_command") or "").strip(),
        "use_ssh": bool(settings.get(f"{kind}_use_ssh")),
        "host": str(settings.get(f"{kind}_host") or "").strip(),
        "shell": str(settings.get(f"{kind}_shell") or "tcsh").strip(),
        "path_local": str(settings.get(f"{kind}_path_local") or "").strip(),
        "path_remote": str(settings.get(f"{kind}_path_remote") or "").strip(),
    }


def _solver_server(profile: dict) -> str:
    """The ssh target of a profile, or '' when it runs locally."""
    if not profile["use_ssh"] or not profile["host"]:
        return ""
    host = socket.gethostname().split(".")[0].lower()
    if host == profile["host"].split(".")[0].lower():
        return ""              # already on the target machine
    return profile["host"]


def solver_server(kind: str) -> str:
    """The ssh target of the MKS/FEM profile, or '' when it runs locally."""
    return _solver_server(solver_profile(kind))


def map_solver_path(kind_or_profile, path: str) -> str:
    """Translate a local path into the remote view of the shared storage
    (prefix swap + separator style of the remote shell). Paths outside the
    mapped prefix pass through unchanged."""
    profile = (solver_profile(kind_or_profile)
               if isinstance(kind_or_profile, str) else kind_or_profile)
    local, remote = profile["path_local"], profile["path_remote"]
    if not local or not remote or not path or not _solver_server(profile):
        return path
    norm = path.replace("\\", "/")
    prefix = local.replace("\\", "/").rstrip("/")
    if not norm.lower().startswith(prefix.lower()):
        return path
    rest = norm[len(prefix):].lstrip("/")
    sep = "\\" if profile["shell"] == "cmd" else "/"
    mapped = remote.rstrip("/\\")
    return mapped + (sep + rest.replace("/", sep) if rest else "")


def map_solver_text(kind_or_profile, text: str) -> str:
    """Apply the path mapping to every occurrence of the local prefix in a
    command line (both separator spellings)."""
    profile = (solver_profile(kind_or_profile)
               if isinstance(kind_or_profile, str) else kind_or_profile)
    local, remote = profile["path_local"], profile["path_remote"]
    if not local or not remote or not text or not _solver_server(profile):
        return text
    sep = "\\" if profile["shell"] == "cmd" else "/"
    wrong = "/" if sep == "\\" else "\\"
    mapped = remote.rstrip("/\\")
    for spelling in {local, local.replace("\\", "/"),
                     local.replace("/", "\\")}:
        spelling = spelling.rstrip("/\\")
        if spelling and spelling in text:
            text = text.replace(spelling, mapped)
    if mapped in text:
        # fix separators in the path remainders that follow the mapped
        # prefix (token-wise: up to the next whitespace)
        out, position = [], 0
        while True:
            index = text.find(mapped, position)
            if index < 0:
                out.append(text[position:])
                break
            end = index + len(mapped)
            while end < len(text) and not text[end].isspace():
                end += 1
            out.append(text[position:index])
            out.append(text[index:end].replace(wrong, sep))
            position = end
        text = "".join(out)
    return text


def solver_argv(kind: str, command: str, workdir: str | None = None,
                env: dict | None = None
                ) -> tuple[list[str], str | None, dict | None, str]:
    """(argv, cwd, env, server) for a solver-profile command."""
    profile = solver_profile(kind)
    server = _solver_server(profile)
    if server:
        settings = AppSettings.instance()
        options = shlex.split(str(settings.get("ssh_options") or ""))
        mapped_workdir = map_solver_path(profile, workdir) if workdir else None
        mapped_command = map_solver_text(profile, command)
        wrapped = wrap_for_shell(mapped_command, mapped_workdir, env,
                                 shell=profile["shell"])
        return ["ssh", *options, server, wrapped], None, None, server
    argv = shlex.split(command, posix=(os.name != "nt"))
    full_env = None
    if env:
        full_env = dict(os.environ)
        full_env.update({str(k): str(v) for k, v in env.items()})
    return argv, workdir or None, full_env, ""


async def run_solver(ctx, kind: str, command: str = "", *,
                     workdir: str | None = None, env: dict | None = None,
                     timeout: float = 0.0, cancel_parent=None
                     ) -> tuple[int, str]:
    """Run a command through the MKS/FEM solver profile (Settings →
    Solvers). Empty *command* uses the profile's configured solver call."""
    profile = solver_profile(kind)
    command = command.strip() or profile["command"]
    if not command:
        raise RuntimeError(f"No {kind.upper()} solver command configured — "
                           f"Settings → Solvers.")
    argv, cwd, full_env, server = solver_argv(kind, command, workdir, env)
    where = f" [{kind} @ ssh {server}/{profile['shell']}]" if server \
        else f" [{kind}]"
    ctx.info(f"${where} {command}")
    return await _execute(ctx, command, argv, cwd, full_env,
                          timeout=timeout, cancel_parent=cancel_parent)


async def run_console(ctx, command: str, *, workdir: str | None = None,
                      env: dict | None = None, force_local: bool = False,
                      timeout: float = 0.0, cancel_parent=None
                      ) -> tuple[int, str]:
    """Run a console command (locally or via the command server), stream its
    output into the log and return (exit code, combined output)."""
    argv, cwd, full_env, server = build_argv(command, workdir, env, force_local)
    where = f" [ssh {server}]" if server else ""
    ctx.info(f"${where} {command}")
    return await _execute(ctx, command, argv, cwd, full_env,
                          timeout=timeout, cancel_parent=cancel_parent)


async def _execute(ctx, command: str, argv: list[str], cwd, full_env, *,
                   timeout: float = 0.0, cancel_parent=None
                   ) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        *argv, cwd=cwd, env=full_env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)

    lines: list[str] = []

    async def pump():
        while True:
            line = await process.stdout.readline()
            if not line:
                return
            text = line.decode(errors="replace").rstrip()
            lines.append(text)
            ctx.info(text)

    pump_task = asyncio.ensure_future(pump())
    try:
        if timeout and timeout > 0:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        else:
            while process.returncode is None:
                cancelled = ctx.is_cancelled or (
                    cancel_parent is not None and cancel_parent.is_cancelled)
                if cancelled:
                    process.terminate()
                    break
                try:
                    await asyncio.wait_for(process.wait(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError(f"Command timed out after {timeout:g}s: {command}")
    except asyncio.CancelledError:
        process.terminate()
        raise
    finally:
        try:
            await pump_task
        except Exception:
            pass

    code = process.returncode if process.returncode is not None else -1
    return code, "\n".join(lines)
