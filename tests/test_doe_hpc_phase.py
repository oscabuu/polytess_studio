"""Tests for the core building blocks: tables, wait/retry primitives,
templates with delimiters, HPC dry-run, job pool (dry + local), DOE sampling,
and an end-to-end mini training chain.

polytess_hpc/polytess_doe are local-only example plugins (not in git —
see .gitignore); this whole module is skipped where they're absent, e.g.
on a fresh checkout or CI."""

import asyncio
import os
import sys

import pytest

polytess_hpc = pytest.importorskip("polytess_hpc")
polytess_doe = pytest.importorskip("polytess_doe")

import polytess.library  # noqa: F401,E402
from polytess.core import Context, GlobalScope, InstructionList
from polytess.core import tables
from polytess.core.properties import (GetPathFormat, GetTableCell,
                                    PropertyGetNumber, PropertyGetString,
                                    SetGraphVariable)
from polytess.core.signals import signals
from polytess.library.conditions.condition_file_contains_text import FileContainsText
from polytess.library.conditions.condition_files_exist import FilesExist
from polytess.library.conditions.condition_table_row_count import TableRowCount
from polytess.library.conditions.condition_file_exists import FileExists
from polytess.library.instructions.instruction_clean_folder import CleanFolder
from polytess.library.instructions.instruction_compute_hash import ComputeHash
from polytess.library.instructions.instruction_filter_table import FilterTable
from polytess.library.instructions.instruction_format_value_list import FormatValueList
from polytess.library.instructions.instruction_loop_table import LoopTable
from polytess.library.instructions.instruction_read_csv_to_table import ReadCsvToTable
from polytess.library.instructions.instruction_render_template_file import RenderTemplateFile
from polytess.library.instructions.instruction_repeat_until import RepeatUntil
from polytess.library.instructions.instruction_set_table_cell import SetTableCell
from polytess.library.instructions.instruction_set_string import SetString
from polytess.library.instructions.instruction_wait_for_file import WaitForFile
from polytess.library.instructions.instruction_wait_for_files import WaitForFiles
from polytess.library.instructions.instruction_write_table_to_csv import WriteTableToCsv
from polytess.library.instructions.instruction_write_text_file import WriteTextFile
from polytess_hpc.instruction_run_job_pool import RunJobPool
from polytess_hpc.instruction_submit_hpc_job import SubmitHpcJob
from polytess_doe.instruction_generate_doe_table import GenerateDoeTable
from polytess_doe.instruction_generate_full_factorial import GenerateFullFactorial


class FakeGraph:
    def __init__(self):
        from polytess.core.variables import ListVariables, NameVariables
        self.variables = NameVariables()
        self.lists = ListVariables()


@pytest.fixture(autouse=True)
def fresh_globals():
    GlobalScope.reset()
    signals.clear()
    yield
    GlobalScope.reset()
    signals.clear()


def make_ctx(tmp_path):
    return Context(graph=FakeGraph(), workdir=str(tmp_path),
                   logger=lambda l, m: None)


# --------------------------------------------------------------------------- #
# tables
# --------------------------------------------------------------------------- #

async def test_csv_roundtrip_and_types(tmp_path):
    ctx = make_ctx(tmp_path)
    csv_path = tmp_path / "config.csv"
    csv_path.write_text("Part;cpus;active\nGEH;4;true\nLAG_A;8;false\n",
                        encoding="utf-8")
    await InstructionList(ReadCsvToTable("config.csv", "config")).run(ctx)
    table = tables.get_table(ctx, "graph", "config")
    assert tables.row_count(table) == 2
    assert tables.cell(table, 0, "cpus") == 4          # int converted
    assert tables.cell(table, 1, "active") is False    # bool converted
    assert tables.cell(table, 0, "Part") == "GEH"

    out_path = tmp_path / "out.csv"
    write = WriteTableToCsv("config", "out.csv")
    await InstructionList(write).run(ctx)
    text = out_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "Part;cpus;active"
    assert "GEH;4;True" in text


async def test_filter_set_cell_and_conditions(tmp_path):
    ctx = make_ctx(tmp_path)
    table = tables.new_table(rows=[
        {"Name": "a", "State": "pending", "cpus": 2},
        {"Name": "b", "State": "finished", "cpus": 8},
        {"Name": "c", "State": "pending", "cpus": 4}])
    tables.set_table(ctx, "graph", "jobs", table)

    await InstructionList(FilterTable("jobs", "State", "=", "pending", "open")).run(ctx)
    assert tables.row_count(tables.get_table(ctx, "graph", "open")) == 2
    await InstructionList(FilterTable("jobs", "cpus", ">", "3", "big")).run(ctx)
    assert [r["Name"] for r in tables.rows_of(tables.get_table(ctx, "graph", "big"))] \
        == ["b", "c"]
    # row-index filter (iloc equivalent)
    await InstructionList(FilterTable("jobs", "#", ">=", "1", "tail")).run(ctx)
    assert [r["Name"] for r in tables.rows_of(tables.get_table(ctx, "graph", "tail"))] \
        == ["b", "c"]

    setter = SetTableCell("jobs", "State")
    setter.match_column = "Name"
    setter.match_value = PropertyGetString("c")
    setter.value = PropertyGetString("finished")
    await InstructionList(setter).run(ctx)
    assert tables.cell(tables.get_table(ctx, "graph", "jobs"), 2, "State") == "finished"

    cond = TableRowCount("jobs", "=", 3)
    assert cond.check(ctx) is True
    # property sources
    cell = GetTableCell("jobs", column="cpus", match_column="Name", match_value="b")
    assert cell.get(ctx) == 8


async def test_add_table_row_from_empty(tmp_path):
    from polytess.library.instructions.instruction_add_table_row import AddTableRow
    ctx = make_ctx(tmp_path)
    ctx.graph_variables.set("case", "run7")
    add = AddTableRow("jobs", "Name={case};State=pending;cpus=4")
    await InstructionList(add, add.copy()).run(ctx)
    table = tables.get_table(ctx, "graph", "jobs")
    # regression: the FIRST row must not get lost to the coerce-copy
    assert tables.row_count(table) == 2
    assert tables.cell(table, 0, "Name") == "run7"
    assert tables.cell(table, 0, "cpus") == 4


async def test_loop_table_exposes_columns(tmp_path):
    ctx = make_ctx(tmp_path)
    tables.set_table(ctx, "graph", "cfg", tables.new_table(rows=[
        {"Part": "GEH", "cpus": 4}, {"Part": "LAG", "cpus": 8}]))
    loop = LoopTable("cfg")
    inner = SetString()
    inner.target.source = SetGraphVariable("last")
    from polytess.core.properties import GetStringFormat
    inner.value.source = GetStringFormat("{Part}:{cpus}")
    loop.actions.instructions.append(inner)
    await InstructionList(loop).run(ctx)
    assert ctx.graph_variables.get("last") == "LAG:8"
    assert ctx.graph_variables.get("row_index") == 1


# --------------------------------------------------------------------------- #
# wait / retry / files
# --------------------------------------------------------------------------- #

async def test_wait_for_file_and_timeout(tmp_path):
    ctx = make_ctx(tmp_path)
    target = tmp_path / "result.mat"

    async def create_later():
        await asyncio.sleep(0.15)
        target.write_text("done", encoding="utf-8")

    wait = WaitForFile("result.mat", poll_interval_s=0.05, timeout_hours=0.001)
    task = asyncio.ensure_future(create_later())
    await InstructionList(wait).run(ctx)
    await task
    assert target.exists()

    missing = WaitForFile("never.mat", poll_interval_s=0.02,
                          timeout_hours=0.00003)   # ~0.1 s
    with pytest.raises(TimeoutError):
        await InstructionList(missing).run(ctx)


async def test_wait_for_files_barrier(tmp_path):
    ctx = make_ctx(tmp_path)
    lst = ctx.graph_lists.declare("results", "path")
    paths = [tmp_path / f"r{i}.sim" for i in range(3)]
    for p in paths:
        lst.push(str(p))

    async def create_all():
        for p in paths:
            await asyncio.sleep(0.05)
            p.write_text("x", encoding="utf-8")

    wait = WaitForFiles("results", poll_interval_s=0.02, timeout_hours=0.001)
    task = asyncio.ensure_future(create_all())
    await InstructionList(wait).run(ctx)
    await task
    assert FilesExist("results").check(ctx) is True


async def test_repeat_until_retries(tmp_path):
    ctx = make_ctx(tmp_path)
    marker = tmp_path / "third_try.txt"

    from polytess.core.instructions import Instruction
    from polytess.core.metadata import meta

    @meta(title="Test Flaky", category="Testing/Flaky", hidden=True)
    class TestingFlaky(Instruction):
        async def run(self, inner_ctx):
            # succeeds on the 3rd attempt (attempt number = Loop Target)
            if inner_ctx.target >= 3:
                marker.write_text("ok", encoding="utf-8")

    repeat = RepeatUntil(max_attempts=5, delay_s=0.01)
    repeat.actions.instructions.append(TestingFlaky())
    repeat.conditions.conditions.append(FileExists(str(marker)))
    await InstructionList(repeat).run(ctx)
    assert marker.exists()

    hopeless = RepeatUntil(max_attempts=2, delay_s=0.01)
    hopeless.conditions.conditions.append(FileExists(str(tmp_path / "nope")))
    with pytest.raises(RuntimeError):
        await InstructionList(hopeless).run(ctx)


# --------------------------------------------------------------------------- #
# text / files / templates
# --------------------------------------------------------------------------- #

async def test_hash_format_clean(tmp_path):
    ctx = make_ctx(tmp_path)
    hasher = ComputeHash("exp1", length=10)
    hasher.add_timestamp_salt.source.value = False
    hasher.target.source = SetGraphVariable("h")
    await InstructionList(hasher).run(ctx)
    digest = ctx.graph_variables.get("h")
    assert len(digest) == 10
    # deterministic without salt
    await InstructionList(hasher).run(ctx)
    assert ctx.graph_variables.get("h") == digest

    lst = ctx.graph_lists.declare("nodes", "integer", list(range(1, 12)))
    formatter = FormatValueList("nodes", items_per_line=8, separator=", ")
    formatter.target.source = SetGraphVariable("block")
    await InstructionList(formatter).run(ctx)
    lines = ctx.graph_variables.get("block").splitlines()
    assert lines[0] == "1, 2, 3, 4, 5, 6, 7, 8"
    assert lines[1] == "9, 10, 11"

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "model.inp").write_text("deck", encoding="utf-8")
    (job_dir / "model.odb").write_text("result", encoding="utf-8")
    (job_dir / "model.msg").write_text("log", encoding="utf-8")
    await InstructionList(CleanFolder(str(job_dir), "*.inp")).run(ctx)
    assert sorted(p.name for p in job_dir.iterdir()) == ["model.inp"]


async def test_template_delimiters(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.graph_variables.set("rpm", 4000.0)
    ctx.graph_variables.set("torque", -235.0)
    # '#name#' delimiter style
    (tmp_path / "spck.tmpl").write_text(
        "!rpm = #rpm#\n!torque = #torque#\n!keep #unknown#\n", encoding="utf-8")
    render = RenderTemplateFile("spck.tmpl", "out.spck",
                                open_delimiter="#", close_delimiter="#")
    await InstructionList(render).run(ctx)
    text = (tmp_path / "out.spck").read_text(encoding="utf-8")
    assert "!rpm = 4000" in text and "!torque = -235" in text
    assert "#unknown#" in text          # unresolved stays visible
    # '{{name}}' delimiter style
    (tmp_path / "deck.tmpl").write_text("*PARAM, V={{rpm}}\n", encoding="utf-8")
    render2 = RenderTemplateFile("deck.tmpl", "deck.inp",
                                 open_delimiter="{{", close_delimiter="}}")
    await InstructionList(render2).run(ctx)
    assert "V=4000" in (tmp_path / "deck.inp").read_text(encoding="utf-8")

    cond = FileContainsText("deck.inp", "*param")
    assert cond.check(ctx) is True


# --------------------------------------------------------------------------- #
# HPC dry-run + job pool
# --------------------------------------------------------------------------- #

async def test_submit_hpc_job_dry_run(tmp_path):
    ctx = make_ctx(tmp_path)
    submit = SubmitHpcJob("abaqus", str(tmp_path / "model.inp"))
    submit.dry_run.source.value = True
    submit.dry_run_result_file.source.value = str(tmp_path / "model.simp_Z1.sim")
    submit.dry_run_delay_s = PropertyGetNumber(0.05)
    submit.job_id_to.source = SetGraphVariable("job_id")
    await InstructionList(submit).run(ctx)
    assert str(ctx.graph_variables.get("job_id")).startswith("dry-")
    wait = WaitForFile("model.simp_Z1.sim", poll_interval_s=0.02,
                       timeout_hours=0.001)
    await InstructionList(wait).run(ctx)
    assert (tmp_path / "model.simp_Z1.sim").exists()


async def test_job_pool_dry_mode(tmp_path):
    ctx = make_ctx(tmp_path)
    rows = []
    for i in range(4):
        folder = tmp_path / f"var{i}"
        folder.mkdir()
        (folder / "model.inp").write_text("x", encoding="utf-8")
        rows.append({"Name": f"var{i}", "File": str(folder / "model.inp"),
                     "ResultFile": str(folder / "model.odb")})
    tables.set_table(ctx, "graph", "jobs", tables.new_table(rows=rows))

    finished = []
    signals.subscribe("job-done", lambda name, payload: finished.append(payload["Name"]))

    pool = RunJobPool("jobs", "dry")
    pool.max_parallel = PropertyGetNumber(2)
    pool.poll_interval_s = PropertyGetNumber(0.05)
    pool.dry_delay_s = PropertyGetNumber(0.1)
    pool.finished_signal = PropertyGetString("job-done")
    await InstructionList(pool).run(ctx)

    table = tables.get_table(ctx, "graph", "jobs")
    assert all(r["State"] == "finished" for r in tables.rows_of(table))
    assert sorted(finished) == ["var0", "var1", "var2", "var3"]
    assert all((tmp_path / f"var{i}" / "model.odb").exists() for i in range(4))


async def test_job_pool_resume_and_local_mode(tmp_path):
    ctx = make_ctx(tmp_path)
    done_dir = tmp_path / "done"
    done_dir.mkdir()
    (done_dir / "r.txt").write_text("already", encoding="utf-8")
    fresh_dir = tmp_path / "fresh"
    fresh_dir.mkdir()
    (fresh_dir / "in.txt").write_text("input", encoding="utf-8")
    rows = [
        {"Name": "done", "File": str(done_dir / "in.txt"),
         "ResultFile": str(done_dir / "r.txt")},
        {"Name": "fresh", "File": str(fresh_dir / "in.txt"),
         "ResultFile": str(fresh_dir / "r.txt")},
    ]
    tables.set_table(ctx, "graph", "jobs", tables.new_table(rows=rows))

    pool = RunJobPool("jobs", "local")
    pool.max_parallel = PropertyGetNumber(2)
    pool.poll_interval_s = PropertyGetNumber(0.05)
    pool.command_template = PropertyGetString(
        f'"{sys.executable}" -c "open(r\'{fresh_dir / "r.txt"}\', \'w\').write(\'ok\')"')
    await InstructionList(pool).run(ctx)

    table = tables.get_table(ctx, "graph", "jobs")
    states = {r["Name"]: r["State"] for r in tables.rows_of(table)}
    assert states == {"done": "finished", "fresh": "finished"}
    assert (fresh_dir / "r.txt").read_text(encoding="utf-8") == "ok"


async def test_job_pool_failure(tmp_path):
    ctx = make_ctx(tmp_path)
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "in.txt").write_text("x", encoding="utf-8")
    tables.set_table(ctx, "graph", "jobs", tables.new_table(rows=[
        {"Name": "bad", "File": str(folder / "in.txt"),
         "ResultFile": str(folder / "never.txt")}]))
    pool = RunJobPool("jobs", "local")
    pool.poll_interval_s = PropertyGetNumber(0.05)
    pool.command_template = PropertyGetString(f'"{sys.executable}" -c "exit(3)"')
    with pytest.raises(RuntimeError):
        await InstructionList(pool).run(ctx)
    table = tables.get_table(ctx, "graph", "jobs")
    assert tables.rows_of(table)[0]["State"] == "failed"


# --------------------------------------------------------------------------- #
# DOE sampling
# --------------------------------------------------------------------------- #

async def test_generate_doe_table_lhs(tmp_path):
    ctx = make_ctx(tmp_path)
    tables.set_table(ctx, "graph", "doe_config", tables.new_table(rows=[
        {"Name": "speed", "Min": 1000, "Max": 2000, "Type": "table"},
        {"Name": "torque", "Min": -100, "Max": 100, "Type": "table"},
        {"Name": "const", "Min": 5, "Max": 5, "Type": "nominal"}]))
    gen = GenerateDoeTable("doe_config", samples=8, target_table="doe_table")
    gen.seed = PropertyGetNumber(42)
    await InstructionList(gen).run(ctx)
    table = tables.get_table(ctx, "graph", "doe_table")
    assert tables.row_count(table) == 8
    assert tables.columns_of(table) == ["Name", "speed", "torque"]
    speeds = sorted(r["speed"] for r in tables.rows_of(table))
    assert all(1000 <= s <= 2000 for s in speeds)
    # LHS stratification: exactly one sample per 1/8 stratum
    for i, s in enumerate(speeds):
        low = 1000 + i * 125
        assert low <= s <= low + 125
    # reproducible with seed
    await InstructionList(gen).run(ctx)
    speeds2 = sorted(r["speed"] for r in
                     tables.rows_of(tables.get_table(ctx, "graph", "doe_table")))
    assert speeds == speeds2


async def test_generate_full_factorial(tmp_path):
    ctx = make_ctx(tmp_path)
    tables.set_table(ctx, "graph", "factors", tables.new_table(rows=[
        {"Name": "rpm", "Min": 1000, "Max": 3000, "Levels": 3},
        {"Name": "mat", "Values": "steel;alu"}]))
    gen = GenerateFullFactorial("factors", "matrix")
    await InstructionList(gen).run(ctx)
    table = tables.get_table(ctx, "graph", "matrix")
    assert tables.row_count(table) == 6
    rpms = {r["rpm"] for r in tables.rows_of(table)}
    assert rpms == {1000.0, 2000.0, 3000.0}
    assert {r["mat"] for r in tables.rows_of(table)} == {"steel", "alu"}


# --------------------------------------------------------------------------- #
# E2E mini training chain (dry run): render -> submit -> wait -> collect
# --------------------------------------------------------------------------- #

async def test_e2e_mini_training_dry(tmp_path):
    from polytess.graph import ActionsNode, Graph, GraphProcessor, StartNode
    from polytess.library.instructions.instruction_loop_list import LoopList

    graph = Graph("mini-training")
    graph.ensure_endpoints()
    graph.variables.declare("abq_version", "string", "v20251")
    decks = graph.lists.declare("decks", "string", ["GEH", "LAG_A"])
    results = graph.lists.declare("results", "path")

    (tmp_path / "mr.tmpl").write_text(
        "** deck #deck# version #abq_version#\n", encoding="utf-8")

    start = next(iter(graph.nodes_of_type(StartNode)))
    build = graph.add_node(ActionsNode())

    loop = LoopList("decks")
    render = RenderTemplateFile("mr.tmpl", "", "#", "#")
    render.destination.source = GetPathFormat("MR_{target}.inp")
    set_deck = SetString()
    set_deck.target.source = SetGraphVariable("deck")
    from polytess.core.properties import GetTarget
    set_deck.value.source = GetTarget()
    submit = SubmitHpcJob("abaqus", "")
    submit.input_file.source = GetPathFormat("MR_{target}.inp")
    submit.dry_run.source.value = True
    submit.dry_run_result_file.source = GetPathFormat("MR_{target}.simp_Z1.sim")
    submit.dry_run_delay_s = PropertyGetNumber(0.1)
    from polytess.library.instructions.instruction_add_to_list import AddToList
    collect = AddToList("results")
    collect.value.source = GetPathFormat("MR_{target}.simp_Z1.sim")
    loop.actions.instructions += [set_deck, render, submit, collect]

    wait = WaitForFiles("results", poll_interval_s=0.03, timeout_hours=0.001)
    build.instructions.instructions += [loop, wait]

    graph.connect(start, "out", build, "in")
    ctx = Context(graph=graph, workdir=str(tmp_path), logger=lambda l, m: None)
    await GraphProcessor(graph).run(ctx)

    for deck in ("GEH", "LAG_A"):
        rendered = (tmp_path / f"MR_{deck}.inp").read_text(encoding="utf-8")
        assert f"deck {deck}" in rendered
        assert "v20251" in rendered
        assert (tmp_path / f"MR_{deck}.simp_Z1.sim").exists()
    assert len(results.items) == 2
