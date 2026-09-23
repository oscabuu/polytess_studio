# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Input form derived from a flow — the data model behind the polytess
Viewer (PLAN_VIEWER.md) and the Studio's form preview.

A non-expert user never sees the flow; they see a form with the INPUT
variables, grouped like the Blackboard, fill it in and start the run.
This module decides, without any Qt, which variables are inputs, which
are outputs and which stay hidden, validates entered values against
the expert's metadata (``var.form``) and applies them to a graph.

Rules (each overridable per variable via ``form["mode"]``):
- a variable/list some block WRITES during the run is a *runtime*
  variable → hidden (mode "output" shows it read-only after the run)
- every other graph variable/list is an input
- global variables are never part of the form
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from polytess.core.variables import FORM_MODES, effective_status


@dataclass
class InputField:
    name: str
    kind: str                       # "variable" | "list"
    type_id: str
    label: str
    description: str = ""
    required: bool = False
    choices: list | None = None
    minimum: float | None = None
    maximum: float | None = None
    path_kind: str = "any"          # "file" | "folder" | "any"
    must_exist: bool = False
    group: str = ""
    order: float = 0.0
    status: str = "unchecked"       # effective review status
    value: Any = None               # current (default) value / items

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()
                if v not in (None, "", False, [], 0.0) or k in ("name", "value")}


@dataclass
class Section:
    title: str                      # "" = ungrouped
    fields: list[InputField] = field(default_factory=list)


@dataclass
class InputSpec:
    flow_name: str
    sections: list[Section] = field(default_factory=list)
    outputs: list[InputField] = field(default_factory=list)

    @property
    def fields(self) -> list[InputField]:
        return [f for section in self.sections for f in section.fields]

    def field_named(self, name: str) -> InputField | None:
        return next((f for f in self.fields if f.name == name), None)

    def to_dict(self) -> dict:
        return {"flow": self.flow_name,
                "sections": [{"title": s.title,
                              "fields": [f.to_dict() for f in s.fields]}
                             for s in self.sections],
                "outputs": [f.to_dict() for f in self.outputs]}


# ---- derivation ------------------------------------------------------------------ #

def _field_from(var, kind: str, index: int, written: set[str]) -> InputField:
    form = getattr(var, "form", None) or {}
    type_id = var.type_id
    value = list(var.items) if kind == "list" else var.value.get()
    return InputField(
        name=var.name, kind=kind, type_id=type_id,
        label=str(form.get("label") or var.name),
        description=str(form.get("description") or ""),
        required=bool(form.get("required", False)),
        choices=list(form["choices"]) if form.get("choices") else None,
        minimum=form.get("minimum"), maximum=form.get("maximum"),
        path_kind=str(form.get("path_kind") or "any"),
        must_exist=bool(form.get("must_exist", False)),
        group=getattr(var, "group", "") or "",
        order=float(form.get("order", index)),
        status=effective_status(var, written),
        value=value)


def _mode_of(var, written: set[str]) -> str:
    mode = (getattr(var, "form", None) or {}).get("mode")
    if mode in FORM_MODES:
        return mode
    return "hidden" if var.name in written else "input"


def input_spec(graph) -> InputSpec:
    """The Viewer form of *graph*: inputs grouped by variable group (in
    Blackboard order: ungrouped first, then groups alphabetically) and
    the outputs to present after a run."""
    from polytess.graph.flow_builder import runtime_written_names
    written = runtime_written_names(graph)
    spec = InputSpec(flow_name=graph.name)
    inputs: list[InputField] = []
    index = 0
    for var in graph.variables:
        mode = _mode_of(var, written)
        if mode == "hidden":
            continue
        fld = _field_from(var, "variable", index, written)
        index += 1
        (inputs if mode == "input" else spec.outputs).append(fld)
    for lst in graph.lists:
        mode = _mode_of(lst, written)
        if mode == "hidden":
            continue
        fld = _field_from(lst, "list", index, written)
        index += 1
        (inputs if mode == "input" else spec.outputs).append(fld)

    ungrouped = sorted((f for f in inputs if not f.group),
                       key=lambda f: f.order)
    if ungrouped:
        spec.sections.append(Section("", ungrouped))
    for group in sorted({f.group for f in inputs if f.group}):
        members = sorted((f for f in inputs if f.group == group),
                         key=lambda f: f.order)
        spec.sections.append(Section(group, members))
    return spec


# ---- validation ------------------------------------------------------------------- #

def _is_empty(value) -> bool:
    return value is None or value == "" or value == []


def validate_values(spec: InputSpec, values: dict) -> list[str]:
    """Problems with *values* (name -> entered value; missing names keep
    the field's current value). Empty list = ready to run."""
    errors: list[str] = []
    for fld in spec.fields:
        value = values.get(fld.name, fld.value)
        if _is_empty(value):
            if fld.required:
                errors.append(f"{fld.label}: required")
            continue
        if fld.kind == "list":
            if not isinstance(value, list):
                errors.append(f"{fld.label}: expected a list")
            continue
        if fld.type_id in ("number", "integer"):
            try:
                number = float(value)
                if fld.type_id == "integer" and int(number) != number:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{fld.label}: not a "
                              f"{'whole ' if fld.type_id == 'integer' else ''}number")
                continue
            if fld.minimum is not None and number < fld.minimum:
                errors.append(f"{fld.label}: below minimum {fld.minimum:g}")
            if fld.maximum is not None and number > fld.maximum:
                errors.append(f"{fld.label}: above maximum {fld.maximum:g}")
        if fld.choices and value not in fld.choices \
                and str(value) not in [str(c) for c in fld.choices]:
            errors.append(f"{fld.label}: not one of "
                          + ", ".join(str(c) for c in fld.choices))
        if fld.type_id == "path" and fld.must_exist:
            path = os.path.expanduser(str(value))
            if fld.path_kind == "file" and not os.path.isfile(path):
                errors.append(f"{fld.label}: file not found: {value}")
            elif fld.path_kind == "folder" and not os.path.isdir(path):
                errors.append(f"{fld.label}: folder not found: {value}")
            elif fld.path_kind == "any" and not os.path.exists(path):
                errors.append(f"{fld.label}: path not found: {value}")
        if fld.type_id == "date" and value:
            from polytess.core.dates import parse_date
            if parse_date(value) is None:
                errors.append(f"{fld.label}: not a date: {value}")
    return errors


# ---- applying / files ------------------------------------------------------------- #

def apply_values(graph, values: dict) -> list[str]:
    """Write *values* (name -> value or list items) into the graph's
    variables/lists. Returns the names that don't exist in the graph."""
    unknown: list[str] = []
    for name, value in values.items():
        var = graph.variables.variable(name)
        if var is not None:
            var.value.set(value)
            graph.variables._emit(name)
            continue
        lst = graph.lists.get(name)
        if lst is not None:
            lst.clear()
            for item in list(value or []):
                lst.push(item)
            continue
        unknown.append(name)
    return unknown


def load_vars_file(path: str) -> dict:
    """A JSON object {name: value} — the preset format shared by the
    Viewer and ``polytess run --vars-file``."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object of name: value")
    return data


def save_vars_file(path: str, values: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(values, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
