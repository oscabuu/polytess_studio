"""Vector3 and Transform value types."""

import pytest

from polytess.core import GlobalScope
from polytess.core.serialization import dumps, loads
from polytess.core.values import create_value, format_vector3, value_types
from polytess.graph.model import Graph


@pytest.fixture(autouse=True)
def fresh_globals():
    GlobalScope.reset()
    yield
    GlobalScope.reset()


def test_vector3_coerce():
    value = create_value("vector3")
    assert value.get() == [0.0, 0.0, 0.0]
    value.set("1, 2.5, 3")
    assert value.get() == [1.0, 2.5, 3.0]
    value.set("(4; 5; 6)")
    assert value.get() == [4.0, 5.0, 6.0]
    value.set({"x": 7, "y": 8, "z": 9})
    assert value.get() == [7.0, 8.0, 9.0]
    value.set((1, 2, 3))
    assert value.get() == [1.0, 2.0, 3.0]
    with pytest.raises(ValueError):
        value.set("1, 2")
    with pytest.raises(ValueError):
        value.set("a, b, c")
    assert format_vector3([1.0, 2.5, 3.0]) == "1, 2.5, 3"


def test_transform_coerce():
    value = create_value("transform")
    assert value.get() == {"pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0]}
    value.set("1,2,3 | 10, 20, 30")
    assert value.get() == {"pos": [1.0, 2.0, 3.0], "rot": [10.0, 20.0, 30.0]}
    value.set("4,5,6")                     # rot defaults to zero
    assert value.get()["rot"] == [0.0, 0.0, 0.0]
    value.set({"pos": [1, 1, 1], "rot": [0, 90, 0]})
    assert value.get() == {"pos": [1.0, 1.0, 1.0], "rot": [0.0, 90.0, 0.0]}
    with pytest.raises(ValueError):
        value.set("nope | 1,2,3")


async def test_set_vector3_and_transform_instructions():
    from polytess.core import Context
    from polytess.core.properties import (GetGraphVariable, PropertySetVector3,
                                        SetGraphVariable)
    from polytess.library.instructions.instruction_set_transform import SetTransform
    from polytess.library.instructions.instruction_set_vector3 import SetVector3

    graph = Graph("v")
    graph.ensure_endpoints()
    ctx = Context(graph=graph, logger=lambda lvl, msg: None)
    graph.variables.declare("offset", "vector3")
    graph.variables.declare("mount", "transform")

    setter = SetVector3(value=[1, 2, 3])
    setter.target.source.name = "offset"
    await setter.run(ctx)
    assert graph.variables.get("offset") == [1.0, 2.0, 3.0]
    assert "(1, 2, 3)" in setter.title

    # value from another variable
    copy_instr = SetVector3(target=PropertySetVector3(SetGraphVariable("offset2")))
    copy_instr.value.source = GetGraphVariable("offset")
    await copy_instr.run(ctx)
    assert graph.variables.get("offset2") == [1.0, 2.0, 3.0]

    trans = SetTransform(value={"pos": [1, 2, 3], "rot": [0, 90, 0]})
    trans.target.source.name = "mount"
    await trans.run(ctx)
    assert graph.variables.get("mount") == {"pos": [1.0, 2.0, 3.0],
                                            "rot": [0.0, 90.0, 0.0]}


def test_registry_and_graph_roundtrip():
    assert "vector3" in value_types() and "transform" in value_types()
    graph = Graph("vectors")
    graph.ensure_endpoints()
    graph.variables.declare("offset", "vector3", "1, 2, 3")
    graph.variables.declare("mount", "transform", "1,2,3 | 0,90,0")
    restored = loads(dumps(graph))
    assert restored.variables.get("offset") == [1.0, 2.0, 3.0]
    assert restored.variables.get("mount") == {"pos": [1.0, 2.0, 3.0],
                                               "rot": [0.0, 90.0, 0.0]}
    assert restored.variables.variable("offset").type_id == "vector3"
    assert restored.variables.variable("mount").type_id == "transform"
