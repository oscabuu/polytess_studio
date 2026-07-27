"""Phase-1 tests: core framework (values, variables, properties,
instructions, conditions, signals, serialization)."""

import asyncio

import pytest

from polytess.core import (
    Branch, BranchList, CheckMode, Condition, ConditionList, Context,
    GlobalScope, Instruction, InstructionList, PropertyGetNumber,
    PropertyGetString, PropertySetNumber, ValueBool, ValueNumber, ValueString,
    from_data, meta, signals, to_data,
)
from polytess.core.metadata import category_tree, humanize, search_types
from polytess.core.properties import (
    GetConstantNumber, GetGlobalVariable, GetGraphVariable, GetStringFormat,
    SetGraphVariable,
)
from polytess.core.values import create_value, value_from_python


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


def make_ctx():
    return Context(graph=FakeGraph(), logger=lambda lvl, msg: None)


# --------------------------------------------------------------------------- #
# metadata
# --------------------------------------------------------------------------- #

def test_humanize():
    assert humanize("InstructionCreateFolder") == "Instruction Create Folder"


@meta(title="Test Add One", category="Testing/Math/Add One",
      keywords=("increment",), description="Adds one to a graph variable")
class TestingAddOne(Instruction):
    def __init__(self, name: str = "x"):
        super().__init__()
        self.name = name

    async def run(self, ctx):
        ctx.graph_variables.set(self.name, (ctx.graph_variables.get(self.name) or 0) + 1)


def test_category_tree_and_search():
    tree = category_tree(Instruction)
    testing = tree.folders.get("Testing")
    assert testing is not None and "Math" in testing.folders
    hits = search_types(Instruction, "increment")
    assert TestingAddOne in hits
    fuzzy = search_types(Instruction, "incrment")  # typo -> levenshtein
    assert TestingAddOne in fuzzy


# --------------------------------------------------------------------------- #
# values / variables
# --------------------------------------------------------------------------- #

def test_value_coercion():
    assert ValueNumber("3.5").get() == 3.5
    assert ValueBool("yes").get() is True
    assert ValueString(42).get() == "42"
    assert create_value("number", 2).get() == 2.0
    assert value_from_python(True).type_id == "bool"
    assert value_from_python(3).type_id == "integer"
    assert value_from_python(3.5).type_id == "number"


def test_value_integer():
    from polytess.core.values import ValueInteger
    assert ValueInteger("7").get() == 7
    assert ValueInteger(3.9).get() == 3
    assert ValueInteger("2.5").get() == 2
    assert create_value("integer", "5").get() == 5
    assert isinstance(create_value("integer", "5").get(), int)


def test_name_variables_and_events():
    ctx = make_ctx()
    changed = []
    ctx.graph_variables.on_change.append(changed.append)
    ctx.graph_variables.declare("count", "number", 5)
    assert ctx.graph_variables.get("count") == 5.0
    ctx.graph_variables.set("count", "7")   # coerced by ValueNumber
    assert ctx.graph_variables.get("count") == 7.0
    assert changed == ["count", "count"]


def test_list_variables():
    ctx = make_ctx()
    lst = ctx.graph_lists.declare("files", "string")
    lst.push("a.txt")
    lst.insert(0, "b.txt")
    lst.move(0, 1)
    assert lst.items == ["a.txt", "b.txt"]
    lst.remove_at(0)
    assert lst.items == ["b.txt"]


# --------------------------------------------------------------------------- #
# properties
# --------------------------------------------------------------------------- #

def test_property_constant_and_variable():
    ctx = make_ctx()
    ctx.graph_variables.declare("name", "string", "rotor")
    const = PropertyGetString("blade")
    assert const.get(ctx) == "blade"
    var = PropertyGetString(GetGraphVariable("name"))
    assert var.get(ctx) == "rotor"
    glob = PropertyGetNumber(GetGlobalVariable("g"))
    ctx.globals.variables.set("g", 9.81)
    assert glob.get(ctx) == 9.81


def test_property_set_and_format():
    ctx = make_ctx()
    setter = PropertySetNumber(SetGraphVariable("result"))
    setter.set(12, ctx)
    assert ctx.graph_variables.get("result") == 12
    fmt = GetStringFormat("run_{result}_{missing}")
    assert fmt.get(ctx) == "run_12_{missing}"


def test_property_number_coercion_safe():
    ctx = make_ctx()
    p = PropertyGetNumber(GetGraphVariable("nope"))
    assert p.get(ctx) == 0.0


# --------------------------------------------------------------------------- #
# instructions
# --------------------------------------------------------------------------- #

@meta(title="Test Jump", category="Testing/Jump", hidden=True)
class TestingJump(Instruction):
    def __init__(self, offset: int = 2):
        super().__init__()
        self.offset = offset

    async def run(self, ctx):
        self.jump(self.offset)


@meta(title="Test Stop", category="Testing/Stop", hidden=True)
class TestingStop(Instruction):
    async def run(self, ctx):
        self.stop_list()


async def test_instruction_list_sequence_and_pointer():
    ctx = make_ctx()
    lst = InstructionList(TestingAddOne(), TestingJump(2), TestingAddOne(), TestingAddOne())
    await lst.run(ctx)
    # jump(2) skips one AddOne -> 2 increments
    assert ctx.graph_variables.get("x") == 2


async def test_instruction_stop_and_disable():
    ctx = make_ctx()
    disabled = TestingAddOne()
    disabled.is_enabled = False
    lst = InstructionList(disabled, TestingAddOne(), TestingStop(), TestingAddOne())
    await lst.run(ctx)
    assert ctx.graph_variables.get("x") == 1


async def test_wait_and_cancel():
    ctx = make_ctx()

    @meta(title="Test Wait", category="Testing/Wait", hidden=True)
    class TestingWait(Instruction):
        async def run(self, inner_ctx):
            await self.wait_seconds(inner_ctx, 10.0)

    lst = InstructionList(TestingWait(), TestingAddOne())
    task = asyncio.ensure_future(lst.run(ctx))
    await asyncio.sleep(0.1)
    ctx.cancel()
    await asyncio.wait_for(task, timeout=2.0)
    assert ctx.graph_variables.get("x") is None   # never reached


# --------------------------------------------------------------------------- #
# conditions / branches
# --------------------------------------------------------------------------- #

@meta(title="Test Above", category="Testing/Above", hidden=True)
class TestingAbove(Condition):
    def __init__(self, name: str = "x", threshold: float = 0):
        super().__init__()
        self.name = name
        self.threshold = threshold

    def run(self, ctx):
        return (ctx.graph_variables.get(self.name) or 0) > self.threshold


def test_condition_sign_and_modes():
    ctx = make_ctx()
    ctx.graph_variables.set("x", 5)
    cond = TestingAbove("x", 3)
    assert cond.check(ctx) is True
    assert cond.title.startswith("If ")
    cond.sign = False
    assert cond.check(ctx) is False
    assert cond.title.startswith("Not ")

    clist = ConditionList(TestingAbove("x", 3), TestingAbove("x", 10))
    assert clist.check(ctx, CheckMode.AND) is False
    assert clist.check(ctx, CheckMode.OR) is True


async def test_branch_list_first_match_wins():
    ctx = make_ctx()
    ctx.graph_variables.set("x", 5)
    b1 = Branch("high", ConditionList(TestingAbove("x", 10)), InstructionList(TestingAddOne("hit1")))
    b2 = Branch("mid", ConditionList(TestingAbove("x", 3)), InstructionList(TestingAddOne("hit2")))
    b3 = Branch("else", ConditionList(), InstructionList(TestingAddOne("hit3")))
    index = await BranchList(b1, b2, b3).evaluate(ctx)
    assert index == 1
    assert ctx.graph_variables.get("hit2") == 1
    assert ctx.graph_variables.get("hit1") is None
    assert ctx.graph_variables.get("hit3") is None


# --------------------------------------------------------------------------- #
# signals / serialization
# --------------------------------------------------------------------------- #

def test_signals_pubsub():
    seen = []
    recv = lambda name, payload: seen.append((name, payload))
    signals.subscribe("done", recv)
    assert signals.emit("done", 42) == 1
    signals.unsubscribe("done", recv)
    assert signals.emit("done") == 0
    assert seen == [("done", 42)]


async def test_serialization_roundtrip():
    ctx = make_ctx()
    ctx.graph_variables.declare("name", "string", "rotor")
    lst = InstructionList(TestingAddOne("count"), TestingJump(1))
    lst.instructions[0].breakpoint = True
    data = to_data(lst)
    clone = from_data(data)
    assert isinstance(clone, InstructionList)
    assert clone.instructions[0].breakpoint is True
    assert clone.instructions[0].name == "count"
    await clone.run(ctx)
    assert ctx.graph_variables.get("count") == 1

    prop = PropertyGetString(GetGraphVariable("name"))
    clone_prop = from_data(to_data(prop))
    assert clone_prop.get(ctx) == "rotor"
    num = PropertyGetNumber(GetConstantNumber(4.5))
    assert from_data(to_data(num)).get(ctx) == 4.5
