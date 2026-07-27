# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""GUI-free core framework: values, variables, properties, instructions,
conditions, events, signals, serialization. Mirrors 's
runtime architecture (TPolymorphicItem / TValue / PropertyGet / Instruction)."""

from polytess.core.metadata import meta, get_meta, Meta, humanize
from polytess.core.polymorphic import PolymorphicItem
from polytess.core.context import Context
from polytess.core.values import (
    Value, ValueNull, ValueBool, ValueNumber, ValueString, ValuePath, ValueList,
    create_value, value_from_python, value_types,
)
from polytess.core.variables import (
    NameVariable, NameVariables, ListVariable, ListVariables, GlobalScope,
)
from polytess.core.properties import (
    PropertySource, SetSource,
    PropertyGet, PropertyGetString, PropertyGetNumber, PropertyGetBool,
    PropertyGetPath, PropertyGetAny,
    PropertySet, PropertySetString, PropertySetNumber, PropertySetBool,
    PropertySetPath, PropertySetAny,
)
from polytess.core.instructions import Instruction, InstructionList, InstructionResult
from polytess.core.conditions import Condition, ConditionList, CheckMode, Branch, BranchList
from polytess.core.events import Event
from polytess.core.signals import SignalHub, signals
from polytess.core.serialization import to_data, from_data, dumps, loads
