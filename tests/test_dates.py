"""Date value type, Set Date instruction and On Date / On Variable Changed
trigger integration."""

import asyncio
from datetime import datetime, timedelta

import pytest

from polytess.core import Context, GlobalScope, Instruction, meta
from polytess.core.dates import format_date, parse_date
from polytess.core.values import ValueDate, create_value
from polytess.graph import ActionsNode, Graph, GraphProcessor, StartNode, TriggerNode


@pytest.fixture(autouse=True)
def fresh_globals():
    GlobalScope.reset()
    yield
    GlobalScope.reset()


# ---- helpers ---------------------------------------------------------------- #

def test_parse_and_format():
    assert parse_date("2026-07-17 08:30:00") == datetime(2026, 7, 17, 8, 30)
    assert parse_date("2026-07-17T08:30:00") == datetime(2026, 7, 17, 8, 30)
    assert parse_date("17.07.2026 08:30") == datetime(2026, 7, 17, 8, 30)
    assert parse_date("17.07.2026") == datetime(2026, 7, 17)
    assert parse_date("") is None
    assert parse_date("not a date") is None
    assert parse_date(True) is None
    stamp = datetime(2026, 1, 2, 3, 4, 5)
    assert parse_date(stamp) is stamp
    assert format_date(stamp) == "2026-01-02 03:04:05"


def test_value_date_coerce():
    value = create_value("date")
    assert value.get() == ""                      # default: unset
    value.set("17.07.2026 06:00")
    assert value.get() == "2026-07-17 06:00:00"   # normalized
    value.set(datetime(2026, 1, 1))
    assert value.get() == "2026-01-01 00:00:00"
    with pytest.raises(ValueError):
        value.set("garbage")
    assert isinstance(value, ValueDate)


# ---- Set Date ---------------------------------------------------------------- #

def _graph_ctx():
    graph = Graph("dates")
    graph.ensure_endpoints()
    ctx = Context(graph=graph, logger=lambda lvl, msg: None)
    return graph, ctx


async def test_set_date_modes():
    from polytess.library.instructions.instruction_set_date import SetDate

    graph, ctx = _graph_ctx()
    graph.variables.declare("when", "date")

    now_instr = SetDate("when", "now")
    await now_instr.run(ctx)
    written = parse_date(graph.variables.get("when"))
    assert abs((written - datetime.now()).total_seconds()) < 2

    offset = SetDate("when", "now + offset")
    offset.hours.source.value = 2.0
    offset.minutes.source.value = -30.0
    await offset.run(ctx)
    written = parse_date(graph.variables.get("when"))
    expected = datetime.now() + timedelta(hours=2, minutes=-30)
    assert abs((written - expected).total_seconds()) < 2

    specific = SetDate("when", "specific")
    specific.specific.source.value = "24.12.2026 18:00"
    await specific.run(ctx)
    assert graph.variables.get("when") == "2026-12-24 18:00:00"

    bad = SetDate("when", "specific")
    bad.specific.source.value = "gestern"
    with pytest.raises(ValueError):
        await bad.run(ctx)


# ---- On Date trigger --------------------------------------------------------- #

@meta(title="Test Date Push", category="Testing/DatePush", hidden=True)
class DatePush(Instruction):
    def __init__(self, tag: str = ""):
        super().__init__()
        self.tag = tag

    async def run(self, ctx):
        lst = ctx.graph_lists.require("trace")
        lst.push(self.tag)


async def test_on_date_fires_when_variable_reaches_time():
    from polytess.core.properties import GetGraphVariable
    from polytess.library.events.event_on_date import OnDate
    from polytess.library.instructions.instruction_set_date import SetDate

    graph, ctx = _graph_ctx()
    graph.variables.declare("deadline", "date")

    # Start flow arms the deadline 0.3 s in the future
    start = next(iter(graph.nodes_of_type(StartNode)))
    setter_node = graph.add_node(ActionsNode())
    setter = SetDate("deadline", "now + offset")
    setter.seconds.source.value = 1.5
    setter_node.instructions.instructions.append(setter)
    graph.connect(start, "out", setter_node, "in")

    trigger = graph.add_node(TriggerNode())
    event = OnDate()
    event.date.source = GetGraphVariable("deadline")
    event.poll_interval_s = 0.05
    trigger.event = event
    fired = graph.add_node(ActionsNode())
    fired.instructions.instructions.append(DatePush("on-date"))
    graph.connect(trigger, "out", fired, "trigger-in")

    processor = GraphProcessor(graph)
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(2.5)
    processor.stop()
    await asyncio.wait_for(task, timeout=2.0)

    trace = graph.lists.get("trace")
    assert trace is not None and trace.items == ["on-date"]


async def test_on_date_past_date_consumed_without_fire():
    from polytess.library.events.event_on_date import OnDate

    graph, ctx = _graph_ctx()
    graph.variables.declare(
        "deadline", "date", format_date(datetime.now() - timedelta(hours=1)))

    trigger = graph.add_node(TriggerNode())
    event = OnDate()
    from polytess.core.properties import GetGraphVariable
    event.date.source = GetGraphVariable("deadline")
    event.poll_interval_s = 0.05
    trigger.event = event
    fired = graph.add_node(ActionsNode())
    fired.instructions.instructions.append(DatePush("late"))
    graph.connect(trigger, "out", fired, "trigger-in")

    processor = GraphProcessor(graph)
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(0.3)
    processor.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert graph.lists.get("trace") is None      # never fired
