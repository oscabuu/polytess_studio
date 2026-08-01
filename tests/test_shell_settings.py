"""App settings, ssh command wrapping (tcsh-safe) and the native
Abaqus Syntax Check / Generate FBI File instructions."""

import os
import stat
import sys

import pytest

from polytess.core import Context, GlobalScope
from polytess.core.app_settings import AppSettings
from polytess.core.shell import build_argv, remote_command, remote_server, run_console
from polytess.graph.model import Graph


@pytest.fixture(autouse=True)
def local_settings():
    GlobalScope.reset()
    yield
    # restore the suite default: local execution, non-persistent
    AppSettings.reset(path="", use_command_server=False)
    GlobalScope.reset()


def _ctx(tmp_path):
    graph = Graph("shell")
    graph.ensure_endpoints()
    return Context(graph=graph, logger=lambda lvl, msg: None,
                   workdir=str(tmp_path))


# ---- settings ---------------------------------------------------------------- #

def test_settings_roundtrip(tmp_path):
    path = str(tmp_path / "settings.json")
    settings = AppSettings.reset(path=path)
    assert settings.get("command_server") == ""   # shipped default: local execution
    assert settings.get("use_command_server") is False
    settings.set("command_server", "myserver")
    settings.save()
    reloaded = AppSettings.reset(path=path)
    assert reloaded.get("command_server") == "myserver"


def test_sync_python_include_paths_add_and_remove(tmp_path):
    from polytess.core.app_settings import sync_python_include_paths
    p1 = str(tmp_path / "a")
    p2 = str(tmp_path / "b")

    AppSettings.reset(path="", python_include_paths=[p1, p2])
    sync_python_include_paths()
    assert p1 in sys.path and p2 in sys.path

    # narrowing the setting drops the removed path, keeps the other
    AppSettings.reset(path="", python_include_paths=[p2])
    sync_python_include_paths()
    assert p1 not in sys.path and p2 in sys.path

    # empty setting cleans up fully
    AppSettings.reset(path="", python_include_paths=[])
    sync_python_include_paths()
    assert p1 not in sys.path and p2 not in sys.path


def test_sync_python_include_paths_ignores_foreign_entries():
    from polytess.core.app_settings import sync_python_include_paths
    foreign = "/some/other/path-not-managed-by-us"
    sys.path.append(foreign)
    try:
        AppSettings.reset(path="", python_include_paths=[])
        sync_python_include_paths()
        assert foreign in sys.path      # never touches paths it didn't add
    finally:
        sys.path.remove(foreign)


# ---- command wrapping -------------------------------------------------------- #

def test_build_argv_local():
    AppSettings.reset(path="", use_command_server=False)
    argv, cwd, env, server = build_argv("echo hello", "/work", {"A": "1"})
    assert argv[:2] == ["echo", "hello"]
    assert cwd == "/work" and server == ""
    assert env["A"] == "1" and "PATH" in env


def test_build_argv_remote_is_tcsh_safe():
    AppSettings.reset(path="", use_command_server=True,
                      command_server="clusterhost",
                      ssh_options="-o BatchMode=yes")
    argv, cwd, env, server = build_argv(
        "abaqus job=x.inp interactive", "/proj/run 1", {"LM_LICENSE": "42@srv"})
    assert argv[0] == "ssh" and "-o" in argv and "BatchMode=yes" in argv
    assert server == "clusterhost" and argv[-2] == "clusterhost"
    remote = argv[-1]
    # tcsh syntax: setenv (no '='), cd "..." &&, original command last
    assert 'setenv LM_LICENSE "42@srv" ;' in remote
    assert 'cd "/proj/run 1" &&' in remote
    assert remote.endswith("abaqus job=x.inp interactive")
    assert "export " not in remote
    assert cwd is None and env is None


def test_remote_short_circuits(monkeypatch):
    AppSettings.reset(path="", use_command_server=True,
                      command_server="clusterhost")
    monkeypatch.setattr("socket.gethostname", lambda: "CLUSTERHOST.example.com")
    assert remote_server() == ""            # already on the server -> local
    monkeypatch.setattr("socket.gethostname", lambda: "windows-pc")
    assert remote_server() == "clusterhost"
    argv, _, _, server = build_argv("echo x", force_local=True)
    assert server == "" and argv == ["echo", "x"]


def test_remote_command_minimal():
    assert remote_command("ls") == "ls"
    assert remote_command("ls", "/a b") == 'cd "/a b" && ls'


async def test_run_console_local(tmp_path):
    AppSettings.reset(path="", use_command_server=False)
    ctx = _ctx(tmp_path)
    code, output = await run_console(
        ctx, f'"{sys.executable}" -c "print(41 + 1)"')
    assert code == 0 and output.strip() == "42"
    code, _ = await run_console(
        ctx, f'"{sys.executable}" -c "raise SystemExit(3)"')
    assert code == 3


# ---- native instructions ------------------------------------------------------ #

def _fake_tool(tmp_path, name: str, body: str) -> str:
    """An executable python script posing as abaqus / simpack-flx."""
    script = tmp_path / f"{name}.py"
    script.write_text(body)
    return f'"{sys.executable}" "{script}"'


@pytest.mark.skipif(
    not os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "custom_instructions",
        "instruction_abaqus_syntax_check.py")),
    reason="company custom instructions not present")
async def test_abaqus_syntax_check(tmp_path):
    AbaqusSyntaxCheck = sys.modules[
        "polytess_custom.instruction_abaqus_syntax_check"].AbaqusSyntaxCheck
    AppSettings.reset(path="", use_command_server=False)
    deck = tmp_path / "MR_001.inp"
    deck.write_text("*STEP\n*END STEP\n")
    ctx = _ctx(tmp_path)

    ok = AbaqusSyntaxCheck(str(deck))
    ok.abaqus.source.value = _fake_tool(tmp_path, "abaqus_ok",
                                        'print("Analysis completed")')
    await ok.run(ctx)

    bad = AbaqusSyntaxCheck(str(deck))
    bad.abaqus.source.value = _fake_tool(tmp_path, "abaqus_bad",
                                         'print("ERROR in keyword *STEP")')
    with pytest.raises(RuntimeError):
        await bad.run(ctx)

    dry = AbaqusSyntaxCheck(str(deck))
    dry.dry_run.source.value = True
    await dry.run(ctx)


@pytest.mark.skipif(
    not os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "custom_instructions",
        "instruction_abaqus_syntax_check.py")),
    reason="company custom instructions not present")
async def test_generate_fbi_file(tmp_path):
    GenerateFbiFile = sys.modules[
        "polytess_custom.instruction_generate_fbi_file"].GenerateFbiFile
    AppSettings.reset(path="", use_command_server=False)
    deck = tmp_path / "MR_001.inp"
    deck.write_text("deck\n")
    sim = tmp_path / "MR_001.simp_Z1.sim"
    sim.write_text("sim\n")
    ctx = _ctx(tmp_path)

    # the fake simpack-flx creates the .fbi next to the deck (like the real one)
    tool = _fake_tool(
        tmp_path, "flx",
        "import pathlib, sys\n"
        f"pathlib.Path(r'{tmp_path}/MR_001.fbi').write_text('fbi')\n"
        "print('converted')\n")
    instr = GenerateFbiFile(str(tmp_path / "db" / "MR_001.fbi"))
    instr.input_files.source.items = [str(deck), str(sim)]
    instr.simpack_flx.source.value = tool
    await instr.run(ctx)
    assert (tmp_path / "db" / "MR_001.fbi").read_text() == "fbi"
    assert not (tmp_path / "MR_001.fbi").exists()      # moved, not copied

    fail = GenerateFbiFile(str(tmp_path / "x.fbi"))
    fail.input_files.source.items = [str(deck)]
    fail.simpack_flx.source.value = _fake_tool(tmp_path, "flx_bad",
                                               'print("ERROR: no license")')
    with pytest.raises(RuntimeError):
        await fail.run(ctx)

    dry = GenerateFbiFile(str(tmp_path / "dry.fbi"))
    dry.input_files.source.items = [str(deck)]
    dry.dry_run.source.value = True
    await dry.run(ctx)
    assert (tmp_path / "dry.fbi").exists()
