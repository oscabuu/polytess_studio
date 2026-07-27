# Copyright (c) 2026 Winthir Studios. All rights reserved.
"""Solver profiles (Settings → Solvers): shell dialects, path mapping,
ssh routing and the empty-command fallback."""

import sys

import pytest

from polytess.core.app_settings import AppSettings
from polytess.core.shell import (map_solver_path, run_solver, solver_argv,
                                 solver_server, wrap_for_shell)


@pytest.fixture(autouse=True)
def local_settings():
    AppSettings.reset(path="", use_command_server=False)
    yield
    AppSettings.reset(path="", use_command_server=False)


def _ctx():
    from polytess.core import Context, GlobalScope
    from polytess.graph.model import Graph
    GlobalScope.reset()
    return Context(graph=Graph(), logger=lambda level, message: None)


# ---- shell dialects --------------------------------------------------------- #

def test_wrap_tcsh():
    line = wrap_for_shell("abaqus job=x", "/proj/run", {"LM": "42@srv"}, "tcsh")
    assert line == 'setenv LM "42@srv" ; cd "/proj/run" && abaqus job=x'


def test_wrap_bash():
    line = wrap_for_shell("abaqus job=x", "/proj/run", {"LM": "42@srv"}, "bash")
    assert line == 'export LM="42@srv" ; cd "/proj/run" && abaqus job=x'


def test_wrap_cmd():
    line = wrap_for_shell("solver.exe run", r"D:\calc", {"LM": "42@srv"}, "cmd")
    assert line == 'set "LM=42@srv" && cd /d "D:\\calc" && solver.exe run'


# ---- path mapping ------------------------------------------------------------ #

def _remote_fem(**extra):
    AppSettings.reset(path="", use_command_server=False, fem_use_ssh=True,
                      fem_host="linux01", fem_shell="tcsh",
                      fem_path_local=r"P:\projects",
                      fem_path_remote="/proj/projects", **extra)


def test_map_windows_to_linux():
    _remote_fem()
    assert map_solver_path("fem", r"P:\projects\MR\run7") \
        == "/proj/projects/MR/run7"
    # outside the prefix: untouched
    assert map_solver_path("fem", r"C:\temp\x") == r"C:\temp\x"


def test_map_to_windows_remote():
    AppSettings.reset(path="", use_command_server=False, mks_use_ssh=True,
                      mks_host="winbox", mks_shell="cmd",
                      mks_path_local="/Volumes/proj",
                      mks_path_remote=r"\\srv\proj")
    assert map_solver_path("mks", "/Volumes/proj/mbs/model.spck") \
        == r"\\srv\proj\mbs\model.spck"


def test_no_mapping_when_local():
    AppSettings.reset(path="", use_command_server=False,
                      fem_path_local=r"P:\projects",
                      fem_path_remote="/proj/projects")   # use_ssh False
    assert map_solver_path("fem", r"P:\projects\MR") == r"P:\projects\MR"


# ---- routing ----------------------------------------------------------------- #

def test_solver_argv_ssh_wraps_and_maps():
    _remote_fem()
    argv, cwd, env, server = solver_argv(
        "fem", r"abaqus job=P:\projects\MR\deck.inp interactive",
        workdir=r"P:\projects\MR")
    assert argv[0] == "ssh" and server == "linux01" and cwd is None
    wrapped = argv[-1]
    assert wrapped == ('cd "/proj/projects/MR" && '
                       "abaqus job=/proj/projects/MR/deck.inp interactive")


def test_solver_argv_local():
    argv, cwd, env, server = solver_argv("fem", "abaqus job=x",
                                         workdir="/tmp/run")
    assert server == "" and argv[0] == "abaqus" and cwd == "/tmp/run"


def test_hostname_shortcircuit(monkeypatch):
    import socket
    _remote_fem()
    monkeypatch.setattr(socket, "gethostname", lambda: "linux01.example.com")
    assert solver_server("fem") == ""
    argv, _cwd, _env, server = solver_argv("fem", "abaqus job=x")
    assert server == "" and argv[0] == "abaqus"


# ---- execution + settings fallback ------------------------------------------- #

async def test_run_solver_uses_settings_command(tmp_path):
    AppSettings.reset(path="", use_command_server=False,
                      fem_command=f'"{sys.executable}" -c "print(42)"')
    code, output = await run_solver(_ctx(), "fem", "", workdir=str(tmp_path))
    assert code == 0 and output.strip() == "42"


async def test_run_solver_without_command_raises():
    AppSettings.reset(path="", use_command_server=False, fem_command="")
    with pytest.raises(RuntimeError, match="Settings"):
        await run_solver(_ctx(), "fem", "")


async def test_run_solver_instruction_fallback(tmp_path):
    from polytess.core.instructions import InstructionList
    from polytess.library.instructions.instruction_run_solver import RunSolver
    AppSettings.reset(path="", use_command_server=False,
                      mks_command=f'"{sys.executable}" -c "print(7)"')
    instruction = RunSolver(solver="mks")
    ctx = _ctx()
    ctx.workdir = str(tmp_path)
    await InstructionList(instruction).run(ctx)
