# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
# =============================================================================
# COPY TEMPLATE for your own Actions / Conditions / Events
# =============================================================================
# File convention: ONE class per file:
#     instruction_<name>.py   ->  an Action    (e.g. instruction_run_simpack_solver.py)
#     condition_<name>.py     ->  a Condition
#     event_<name>.py         ->  an Event
#
# How to use it:
#   1. Copy this file, e.g. to  polytess_simpack/instruction_my_action.py
#      (the underscore name "_template.py" is deliberately NOT loaded, so
#      the template never shows up in the menus) and reduce it to ONE class.
#   2. Rename and adapt the class.
#   3. Restart the studio — done. Every instruction_*/condition_*/event_*
#      file in the folder loads AUTOMATICALLY (no import line needed);
#      the block appears in the "Add …" menu under the category from
#      @meta(category=...).
#
# IMPORTANT: the class name is the "$type" tag in saved workflows.
# Renaming it later breaks old files (then set meta(type_name="OldName")
# as an alias).
# =============================================================================

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.events import Event
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool,     # field: boolean        (constant OR variable)
    PropertyGetNumber,   # field: number (float)
    PropertyGetPath,     # field: file/folder path
    PropertyGetString,   # field: text
    PropertySetNumber,   # target: write a number into a variable
    PropertySetString,   # target: write text into a variable
)


# -----------------------------------------------------------------------------
# 1) ACTION (Instruction) — one step in an actions list
# -----------------------------------------------------------------------------
@meta(
    title="My Action",                       # display name
    category="MyCompany/My Action",          # menu path ("/" = submenu)
    icon="terminal",                         # see polytess/gui/icons.py (e.g.
                                             # folder, file, terminal, clock,
                                             # search, edit, list, number)
    color="teal",                            # red green blue yellow purple
                                             # pink teal
    description="What does this action do? (shown in the picker below)",
    parameters=(("Input File", "description of the parameter"),
                ("Factor", "…")),            # optional, for the help dialog
    keywords=("keyword", "alias"),           # optional, for the search
)
class MyAction(Instruction):

    def __init__(self):
        super().__init__()
        # Every property field shows up in the inspector automatically,
        # each with the dropdown "Value | Graph Variable | Global Variable |
        # Formatted String | …". Order here = order in the inspector.
        self.input_file = PropertyGetPath("")
        self.factor = PropertyGetNumber(1.0)
        self.verbose = PropertyGetBool(False)
        self.result_to = PropertySetNumber()          # result -> variable
        # Plain fields work too (str/float/int/bool without Property):
        self.mode = "fast"
        # Optional: fixed choice list instead of free text for a str field:
        # (class attribute, not per instance)
    FIELD_CHOICES = {"mode": ["fast", "accurate"]}

    @property
    def title(self) -> str:
        # Dynamic title in the list, like ("Set counter = 5").
        return f"My Action {self.input_file} × {self.factor}"

    async def run(self, ctx) -> None:
        # ctx offers:
        #   ctx.resolve_path(p)      relative paths -> working directory
        #   ctx.info/debug/warning/error("…")        -> log panel
        #   ctx.graph_variables / ctx.globals.variables   variable access
        #   ctx.target               current element in Loop List/Range
        #   ctx.is_cancelled         check regularly in long loops!
        #   await self.wait_seconds(ctx, 2.0)         cancellable waiting
        path = ctx.resolve_path(self.input_file.get(ctx))
        factor = self.factor.get(ctx)
        if self.verbose.get(ctx):
            ctx.info(f"MyAction: processing {path}")

        value = 123.0 * factor        # ... your actual logic goes here ...
        # External programs: easiest is to reuse the RunCommand pattern
        # (see simpack.py / abaqus.py in this folder).

        self.result_to.set(value, ctx)
        # Failure: simply raise an exception -> the node turns red, the
        # list stops, the message lands in the log:
        # raise RuntimeError("input file unusable")


# -----------------------------------------------------------------------------
# 2) CONDITION — returns True/False (for Conditions nodes / branches)
# -----------------------------------------------------------------------------
@meta(title="My Check", category="MyCompany/My Check", icon="check",
      color="green", description="When is this condition met?")
class MyCheck(Condition):

    def __init__(self):
        super().__init__()
        self.threshold = PropertyGetNumber(100.0)

    @property
    def summary(self) -> str:
        # Title WITHOUT the "If/Not" prefix — polytess prepends that itself.
        return f"value below {self.threshold}"

    def run(self, ctx) -> bool:          # synchronous, no async!
        return 42.0 < self.threshold.get(ctx)


# -----------------------------------------------------------------------------
# 3) EVENT — fires a trigger node (only needed for your own triggers)
# -----------------------------------------------------------------------------
@meta(title="On My Event", category="MyCompany/On My Event", icon="bolt",
      color="yellow", description="Fires when …")
class OnMyEvent(Event):

    persistent = True   # True = keeps listening (workflow stays alive),
                        # False = fires once at start (like On Start)

    def __init__(self):
        super().__init__()
        self.some_setting = ""

    def start(self, fire, ctx) -> None:
        super().start(fire, ctx)
        # Arm the trigger here: subscribe to a signal, start an asyncio
        # task, poll a file … (examples: polytess/library/events/basic.py).
        # Fire with  self.fire(payload)  — the payload becomes ctx.target
        # of the downstream nodes.

    def stop(self) -> None:
        # Clean up (cancel tasks, unsubscribe) — called when the run ends.
        super().stop()
