"""Phase-3 tests: built-in library + an end-to-end demo workflow
(create folder -> render template -> run process -> check condition)."""

import os
import sys

import pytest

import polytess.library  # noqa: F401  (register built-ins)
from polytess.core import Context, GlobalScope, InstructionList
from polytess.core.conditions import ConditionList
from polytess.core.properties import (
    GetGraphVariable, GetPathFormat, GetStringFormat, PropertyGetNumber,
    PropertyGetString, PropertySetNumber, PropertySetString, SetGraphVariable,
)
from polytess.graph import ActionsNode, ConditionsNode, Graph, GraphProcessor, StartNode
from polytess.library.conditions.condition_compare_number import CompareNumber
from polytess.library.conditions.condition_compare_string import CompareString
from polytess.library.conditions.condition_file_exists import FileExists
from polytess.library.conditions.condition_folder_exists import FolderExists
from polytess.library.instructions.instruction_log_message import LogMessage
from polytess.library.instructions.instruction_copy_path import CopyPath
from polytess.library.instructions.instruction_create_folder import CreateFolder
from polytess.library.instructions.instruction_delete_path import DeletePath
from polytess.library.instructions.instruction_render_template_file import RenderTemplateFile
from polytess.library.instructions.instruction_replace_in_file import ReplaceInFile
from polytess.library.instructions.instruction_write_text_file import WriteTextFile
from polytess.library.instructions.instruction_emit_signal import EmitSignal
from polytess.library.instructions.instruction_skip_next import SkipNext
from polytess.library.instructions.instruction_wait_seconds import WaitSeconds
from polytess.library.instructions.instruction_run_command import RunCommand
from polytess.library.instructions.instruction_add_to_list import AddToList
from polytess.library.instructions.instruction_find_files import FindFiles
from polytess.library.instructions.instruction_loop_list import LoopList
from polytess.library.instructions.instruction_loop_range import LoopRange
from polytess.library.instructions.instruction_number_operation import NumberOperation
from polytess.library.instructions.instruction_set_number import SetNumber
from polytess.library.instructions.instruction_set_string import SetString


@pytest.fixture(autouse=True)
def fresh_globals():
    GlobalScope.reset()
    yield
    GlobalScope.reset()


class FakeGraph:
    def __init__(self):
        from polytess.core.variables import ListVariables, NameVariables
        self.variables = NameVariables()
        self.lists = ListVariables()


def make_ctx(tmp_path):
    return Context(graph=FakeGraph(), workdir=str(tmp_path), logger=lambda l, m: None)


async def test_set_and_math(tmp_path):
    ctx = make_ctx(tmp_path)
    lst = InstructionList(
        SetNumber(PropertySetNumber(SetGraphVariable("a")), 6),
        NumberOperation(PropertySetNumber(SetGraphVariable("b")),
                        PropertyGetNumber(GetGraphVariable("a")), "*", 7),
        SetString(PropertySetString(SetGraphVariable("label")),
                  PropertyGetString(GetStringFormat("run_{b}"))),
    )
    await lst.run(ctx)
    assert ctx.graph_variables.get("b") == 42.0
    assert ctx.graph_variables.get("label") == "run_42"


async def test_file_instructions_and_conditions(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.graph_variables.declare("case", "string", "case01")
    ctx.graph_variables.declare("speed", "number", 120)

    template = tmp_path / "model.tpl"
    template.write_text("CASE = {case}\nSPEED = {speed}\n", encoding="utf-8")

    lst = InstructionList(
        CreateFolder("runs/{case}"),
        RenderTemplateFile("model.tpl", "runs/{case}/model.inp"),
        ReplaceInFile("runs/{case}/model.inp", "SPEED", "VELOCITY"),
        WriteTextFile("runs/{case}/notes.txt", "hello"),
        CopyPath("runs/{case}/notes.txt", "runs/{case}/notes_copy.txt"),
    )
    # paths with {vars} need the formatted path source
    lst.instructions[0].path.source = GetPathFormat("runs/{case}")
    lst.instructions[1].destination.source = GetPathFormat("runs/{case}/model.inp")
    lst.instructions[2].path.source = GetPathFormat("runs/{case}/model.inp")
    lst.instructions[3].path.source = GetPathFormat("runs/{case}/notes.txt")
    lst.instructions[4].source.source = GetPathFormat("runs/{case}/notes.txt")
    lst.instructions[4].destination.source = GetPathFormat("runs/{case}/notes_copy.txt")
    await lst.run(ctx)

    run_dir = tmp_path / "runs" / "case01"
    assert (run_dir / "model.inp").read_text(encoding="utf-8") == "CASE = case01\nVELOCITY = 120\n"
    assert (run_dir / "notes_copy.txt").read_text(encoding="utf-8") == "hello"

    assert FolderExists("runs/case01").check(ctx) is True
    cond = FileExists("runs/case01/model.inp")
    assert cond.check(ctx) is True
    cond.sign = False
    assert cond.check(ctx) is False

    delete = DeletePath("runs/case01/notes.txt")
    await InstructionList(delete).run(ctx)
    assert not (run_dir / "notes.txt").exists()


async def test_find_files_and_loop(tmp_path):
    ctx = make_ctx(tmp_path)
    for name in ("a.inp", "b.inp", "c.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    await InstructionList(FindFiles("*.inp", "inputs")).run(ctx)
    lst = ctx.graph_lists.get("inputs")
    assert [os.path.basename(p) for p in lst.items] == ["a.inp", "b.inp"]

    loop = LoopList("inputs")
    inner = SetString(PropertySetString(SetGraphVariable("last")),
                      PropertyGetString(GetStringFormat("saw {target}")))
    loop.actions.instructions.append(inner)
    counter = NumberOperation(PropertySetNumber(SetGraphVariable("n")),
                              PropertyGetNumber(GetGraphVariable("n")), "+", 1)
    loop.actions.instructions.append(counter)
    await InstructionList(loop).run(ctx)
    assert ctx.graph_variables.get("n") == 2.0
    assert "b.inp" in ctx.graph_variables.get("last")


async def test_loop_range_and_skip(tmp_path):
    ctx = make_ctx(tmp_path)
    loop = LoopRange(0, 5, 1)
    loop.actions.instructions.append(
        NumberOperation(PropertySetNumber(SetGraphVariable("sum")),
                        PropertyGetNumber(GetGraphVariable("sum")), "+", 1))
    await InstructionList(loop).run(ctx)
    assert ctx.graph_variables.get("sum") == 5.0

    lst = InstructionList(
        SkipNext(1),
        SetNumber(PropertySetNumber(SetGraphVariable("skipped")), 1),
        SetNumber(PropertySetNumber(SetGraphVariable("kept")), 1),
    )
    await lst.run(ctx)
    assert ctx.graph_variables.get("skipped") is None
    assert ctx.graph_variables.get("kept") == 1.0


async def test_run_command(tmp_path):
    ctx = make_ctx(tmp_path)
    cmd = RunCommand(f'"{sys.executable}" -c "print(6*7)"')
    cmd.exit_code_to.source = SetGraphVariable("code")
    cmd.output_to.source = SetGraphVariable("out")
    await InstructionList(cmd).run(ctx)
    assert ctx.graph_variables.get("code") == 0.0
    assert ctx.graph_variables.get("out").strip() == "42"


async def test_run_command_failure(tmp_path):
    ctx = make_ctx(tmp_path)
    cmd = RunCommand(f'"{sys.executable}" -c "import sys; sys.exit(3)"')
    with pytest.raises(RuntimeError):
        await InstructionList(cmd).run(ctx)


async def test_end_to_end_demo_workflow(tmp_path):
    """Full graph: Start -> prepare folder+file -> Conditions -> ok/fail."""
    graph = Graph("demo")
    graph.ensure_endpoints()
    graph.variables.declare("case", "string", "demo01")
    start = next(iter(graph.nodes_of_type(StartNode)))

    prepare = graph.add_node(ActionsNode())
    create = CreateFolder()
    create.path.source = GetPathFormat("out/{case}")
    write = WriteTextFile("", "RESULT = 1\n")
    write.path.source = GetPathFormat("out/{case}/result.txt")
    prepare.instructions.instructions += [create, write, EmitSignal("prepared")]

    check = graph.add_node(ConditionsNode())
    exists = FileExists()
    exists.path.source = GetPathFormat("out/{case}/result.txt")
    check.conditions.conditions.append(exists)

    ok = graph.add_node(ActionsNode())
    ok.instructions.instructions.append(
        SetString(PropertySetString(SetGraphVariable("status")), "ok"))
    bad = graph.add_node(ActionsNode())
    bad.instructions.instructions.append(
        SetString(PropertySetString(SetGraphVariable("status")), "bad"))

    graph.connect(start, "out", prepare, "in")
    graph.connect(prepare, "out", check, "in")
    graph.connect(check, "success", ok, "in")
    graph.connect(check, "fail", bad, "in")

    ctx = Context(graph=graph, workdir=str(tmp_path), logger=lambda l, m: None)
    await GraphProcessor(graph).run(ctx)
    assert graph.variables.get("status") == "ok"
    assert (tmp_path / "out" / "demo01" / "result.txt").exists()


async def test_library_serialization_roundtrip(tmp_path):
    from polytess.core.serialization import from_data, to_data
    lst = InstructionList(
        LogMessage("hi", "info"),
        WaitSeconds(0.01),
        CreateFolder("x"),
        RunCommand("echo 1", check_exit_code=False),
    )
    clone = from_data(to_data(lst))
    assert [type(i).__name__ for i in clone.instructions] == \
        ["LogMessage", "WaitSeconds", "CreateFolder", "RunCommand"]
    cond = ConditionList(CompareNumber(1, "<", 2), CompareString("a", "equals", "a"))
    clone_c = from_data(to_data(cond))
    ctx = make_ctx(tmp_path)
    assert clone_c.check(ctx) is True


def test_field_help_mechanism():
    """FIELD_HELP dicts merge along the MRO and reach get_field_help."""
    from polytess.core.metadata import get_field_help
    helps = get_field_help(CreateFolder)
    assert "path" in helps and "working directory" in helps["path"]

    class _Derived(CreateFolder):
        FIELD_HELP = {"extra": "Extra field."}

    merged = get_field_help(_Derived)
    assert "path" in merged and merged["extra"] == "Extra field."


def test_every_library_block_field_has_help():
    """Every public parameter of every shipped Instruction/Condition/Event
    carries a FIELD_HELP tooltip text."""
    from polytess.core.conditions import Condition
    from polytess.core.events import Event
    from polytess.core.instructions import Instruction
    from polytess.core.metadata import get_field_help, iter_subclasses

    missing: list[str] = []
    for base in (Instruction, Condition, Event):
        for cls in iter_subclasses(base, include_hidden=True):
            if not cls.__module__.startswith("polytess.library"):
                continue
            try:
                instance = cls()
            except Exception:
                continue
            helps = get_field_help(cls)
            for attr in vars(instance):
                if attr.startswith("_") or attr in ("is_enabled", "breakpoint"):
                    continue
                if not str(helps.get(attr, "")).strip():
                    missing.append(f"{cls.__name__}.{attr}")
    assert not missing, \
        f"{len(missing)} fields without FIELD_HELP: " + ", ".join(missing[:40])


def test_titles_never_read_values_without_ctx():
    """`title` renders with no active run (ctx=None) — it must not crash
    even when every PropertyGet* field is bound to a variable source."""
    from polytess.core.events import Event
    from polytess.core.instructions import Instruction
    from polytess.core.metadata import iter_subclasses
    from polytess.core.properties import GetGraphVariable, PropertyGet

    for base in (Instruction, Event):
        for cls in iter_subclasses(base, include_hidden=True):
            if not cls.__module__.startswith("polytess.library"):
                continue
            try:
                instance = cls()
            except Exception:
                continue
            for attr, value in vars(instance).items():
                if isinstance(value, PropertyGet):
                    setattr(instance, attr,
                            type(value)(GetGraphVariable("some_var")))
            str(instance.title)          # must not raise without a ctx


def test_rename_references_rewrites_sources_templates_and_fields():
    """rename_references() keeps every reference working after a rename:
    property sources, {name} templates and plain name fields."""
    from polytess.core.refs import find_references, rename_references
    from polytess.graph.flow_builder import build_flow

    graph = build_flow({
        "name": "rename-test",
        "variables": [{"name": "deck", "type": "string", "value": "MR_001"}],
        "nodes": [
            {"id": "a", "kind": "actions", "instructions": [
                {"type": "LogMessage",
                 "params": {"message": {"template": "Deck {deck} ready"}}},
                {"type": "SetString",
                 "params": {"target": "deck", "value": {"var": "deck"}}},
            ]},
        ],
        "edges": [{"from": "start", "to": "a"}],
    }).graph

    before = find_references(graph, "deck")
    assert len(before) >= 3          # template + set-target + get-source

    count = rename_references(graph, "deck", "deck_name")
    assert count >= 3
    assert not find_references(graph, "deck")
    after = find_references(graph, "deck_name")
    assert len(after) == len(before)

    # the flow still works end to end under the new name
    graph.variables.rename("deck", "deck_name")
    ctx = Context(graph=graph, logger=lambda level, message: None)
    log = list(next(iter(graph.nodes_of_type(ActionsNode))).instructions)[0]
    assert log.message.get(ctx) == "Deck MR_001 ready"


def test_variable_group_persists_and_defaults_empty(tmp_path):
    from polytess.core.serialization import from_data, to_data
    from polytess.core.variables import NameVariable, NameVariables

    variables = NameVariables()
    variables.declare("a", "string", "x")
    variables.variable("a").group = "Inputs"
    variables.declare("b", "number", 1)

    clone = from_data(to_data(variables))
    assert clone.variable("a").group == "Inputs"
    assert clone.variable("b").group == ""

    # old files without the key load with the default
    legacy = to_data(NameVariable("c"))
    legacy.pop("group")
    assert from_data(legacy).group == ""


async def test_send_email_falls_back_to_report_email(tmp_path, monkeypatch):
    """Empty "to" uses the report_email setting; both empty -> skipped."""
    import shutil as _shutil

    from polytess.core.app_settings import AppSettings
    from polytess.library.instructions.instruction_send_email import SendEmail

    monkeypatch.setattr(_shutil, "which", lambda name: None)  # no sendmail
    warnings = []
    ctx = Context(graph=FakeGraph(), workdir=str(tmp_path),
                  logger=lambda level, m: warnings.append((level, m)))

    AppSettings.reset(path="", report_email="team@example.com")
    await SendEmail("", "subject", "body").run(ctx)
    assert any("team@example.com" in m for _l, m in warnings)

    warnings.clear()
    AppSettings.reset(path="", report_email="")
    await SendEmail("", "subject", "body").run(ctx)
    assert any("skipped" in m for _l, m in warnings)
    AppSettings.reset(path="", use_command_server=False)
