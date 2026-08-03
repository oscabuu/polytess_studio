# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import asyncio
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool, PropertyGetNumber, PropertyGetPath, PropertyGetString,
    PropertySetNumber, PropertySetString,
)

async def _stream(stream, log, level: str, collect: list[str]) -> None:
    while True:
        line = await stream.readline()
        if not line:
            return
        text = line.decode(errors="replace").rstrip()
        collect.append(text)
        log(level, text)


@meta(title="Run Command", category="Process/Run Command", icon="terminal", color="red",
      description="Runs an external program; stdout/stderr stream into the log. "
                  "Fails the node on non-zero exit code unless disabled. With a "
                  "configured command server (Settings) the command runs there "
                  "via ssh — 'Force Local' bypasses that.",
      parameters=(("Command", "Program + arguments (shell-like syntax)"),
                  ("Workdir", "Working directory (empty = workflow directory)"),
                  ("Timeout", "Seconds; 0 = no timeout"),
                  ("Check exit code", "Raise on non-zero exit"),
                  ("Force Local", "Run on this machine even when a command "
                   "server is configured"),
                  ("Exit code ->", "Variable receiving the exit code"),
                  ("Output ->", "Variable receiving captured stdout")),
      keywords=("execute", "shell", "solver", "batch", "subprocess", "simpack", "abaqus"))
class RunCommand(Instruction):

    FIELD_HELP = {
        "command": "Program plus arguments in shell-like syntax; empty "
                   "commands are skipped with a warning. With a command "
                   "server configured in Settings the command runs "
                   "there via ssh.",
        "workdir": "Working directory for the process; empty = the "
                   "workflow's working directory.",
        "extra_env": "Additional environment variables, one NAME=value "
                     "per line; they are added on top of the inherited "
                     "environment.",
        "timeout": "Maximum runtime in seconds; 0 = no timeout. On "
                   "expiry the process is killed and the node fails.",
        "check_exit_code": "When enabled (default), a non-zero exit "
                           "code fails the node; otherwise it is only "
                           "logged.",
        "force_local": "Run on this machine even when a command server "
                       "is configured in Settings.",
        "exit_code_to": "Optional variable that receives the process "
                        "exit code as a number.",
        "output_to": "Optional variable that receives the captured "
                     "stdout text (stderr goes to the log only).",
    }

    def __init__(self, command: str = "", workdir: str = "", timeout: float = 0.0,
                 check_exit_code: bool = True):
        super().__init__()
        self.command = PropertyGetString(command)
        self.workdir = PropertyGetPath(workdir)
        self.extra_env = ""                # "NAME=value" lines
        self.timeout = PropertyGetNumber(timeout)
        self.check_exit_code = PropertyGetBool(check_exit_code)
        self.force_local = PropertyGetBool(False)
        self.exit_code_to = PropertySetNumber()
        self.output_to = PropertySetString()

    @property
    def title(self) -> str:
        return f"Run {self.command}"

    async def run(self, ctx):
        from polytess.core.shell import build_argv
        command = self.command.get(ctx)
        if not command.strip():
            ctx.warning("Run Command: empty command")
            return
        env = {}
        for line in self.extra_env.splitlines():
            name, sep, value = line.partition("=")
            if sep:
                env[name.strip()] = value.strip()
        workdir = self.workdir.get(ctx) or ctx.workdir
        argv, cwd, full_env, server = build_argv(
            command, workdir, env, force_local=self.force_local.get(ctx))

        ctx.info(f"$ {f'[ssh {server}] ' if server else ''}{command}")
        process = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd, env=full_env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        out_lines: list[str] = []
        err_lines: list[str] = []
        streams = asyncio.gather(
            _stream(process.stdout, ctx.log, "info", out_lines),
            _stream(process.stderr, ctx.log, "warning", err_lines))

        timeout = self.timeout.get(ctx)
        try:
            if timeout and timeout > 0:
                await asyncio.wait_for(process.wait(), timeout=timeout)
            else:
                # poll so cooperative cancellation can kill the process
                while process.returncode is None:
                    if ctx.is_cancelled or (self._parent is not None and self._parent.is_cancelled):
                        process.terminate()
                        break
                    try:
                        await asyncio.wait_for(process.wait(), timeout=0.2)
                    except asyncio.TimeoutError:
                        pass
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            await streams
            raise TimeoutError(f"Command timed out after {timeout:g}s: {command}")
        except asyncio.CancelledError:
            process.terminate()
            raise
        finally:
            try:
                await streams
            except Exception:
                pass

        code = process.returncode if process.returncode is not None else -1
        self.exit_code_to.set(float(code), ctx)
        self.output_to.set("\n".join(out_lines), ctx)
        ctx.log("info" if code == 0 else "error", f"Exit code {code}: {argv[0]}")
        if code != 0 and self.check_exit_code.get(ctx):
            raise RuntimeError(f"Command failed with exit code {code}: {command}")
