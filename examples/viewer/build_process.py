# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Builds the Viewer demo: a main process with five sub-workflows.

Run:  ../../.venv/bin/python build_process.py
Needs no solver — every step only waits a moment and writes small text
files into the chosen work folder, so the board, the form, presets and
the dashboard can be tried end to end:

    main_process.flow.json      Prepare Model → Mesh → Static Load Case
                                              ↘ Modal Analysis       → Report
    prepare.flow.json, mesh.flow.json, solve_static.flow.json,
    solve_modal.flow.json, report.flow.json

Open main_process.flow.json in the Viewer (polytess-viewer) for the
board, or in the Studio to see the sub-workflow nodes and bindings.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from polytess.cli import _load_everything          # noqa: E402

_load_everything()

from polytess.graph.flow_builder import build_flow  # noqa: E402


def save(name: str, spec: dict) -> None:
    result = build_flow(spec)
    assert result.ok, (name, result.errors, result.missing, result.warnings)
    result.graph.save(os.path.join(HERE, name))
    print("wrote", name)


def log(text):
    return {"type": "LogMessage", "params": {"message": {"template": text}}}


def wait(seconds):
    return {"type": "WaitSeconds", "params": {"seconds": seconds}}


# ---- sub-workflows --------------------------------------------------------- #

save("prepare.flow.json", {
    "name": "Prepare Model",
    "variables": [
        {"name": "project_name", "type": "string", "value": "demo",
         "form": {"label": "Project name", "required": True}},
        {"name": "work_folder", "type": "path", "value": "",
         "form": {"label": "Work folder", "path_kind": "folder", "required": True}},
        {"name": "model_file", "type": "path", "value": "",
         "form": {"mode": "output", "label": "Model file"}},
    ],
    "nodes": [
        {"id": "prep", "kind": "actions", "name": "Create model", "instructions": [
            log("Preparing model for {project_name}"),
            {"type": "CreateFolder", "params": {"path": {"var": "work_folder"}}},
            wait(1.5),
            {"type": "WriteTextFile", "params": {
                "path": {"template": "{work_folder}/{project_name}_model.txt"},
                "content": {"template": "MODEL {project_name}\nnodes 1200\n"}}},
            {"type": "SetString", "params": {
                "value": {"template": "{work_folder}/{project_name}_model.txt"},
                "target": "model_file"}},
            log("Model written: {model_file}"),
        ]},
    ],
    "edges": [{"from": "start", "to": "prep"}, {"from": "prep", "to": "exit"}],
})

save("mesh.flow.json", {
    "name": "Mesh",
    "variables": [
        {"name": "model_file", "type": "path", "value": "",
         "form": {"label": "Model file", "path_kind": "file", "must_exist": True,
                  "required": True}},
        {"name": "mesh_size", "type": "number", "value": 2.0,
         "form": {"label": "Element size [mm]", "minimum": 0.5, "maximum": 10,
                  "description": "Smaller elements = more accurate, slower."}},
        {"name": "mesh_file", "type": "path", "value": "",
         "form": {"mode": "output", "label": "Mesh file"}},
        {"name": "element_count", "type": "number", "value": 0,
         "form": {"mode": "output", "label": "Elements"}},
    ],
    "nodes": [
        {"id": "mesh", "kind": "actions", "name": "Generate mesh", "instructions": [
            log("Meshing {model_file} with {mesh_size} mm"),
            wait(2.5),
            {"type": "SetString", "params": {
                "value": {"template": "{model_file}.mesh"}, "target": "mesh_file"}},
            {"type": "WriteTextFile", "params": {
                "path": {"var": "mesh_file"},
                "content": {"template": "MESH size={mesh_size}\n"}}},
            {"type": "SetNumber", "params": {"value": 12000, "target": "element_count"}},
            log("Mesh done: {element_count} elements"),
        ]},
    ],
    "edges": [{"from": "start", "to": "mesh"}, {"from": "mesh", "to": "exit"}],
})

save("solve_static.flow.json", {
    "name": "Static Load Case",
    "variables": [
        {"name": "mesh_file", "type": "path", "value": "",
         "form": {"label": "Mesh file", "path_kind": "file", "must_exist": True,
                  "required": True}},
        {"name": "load_kn", "type": "number", "value": 5.0,
         "form": {"label": "Load [kN]", "minimum": 0, "maximum": 100,
                  "required": True}},
        {"name": "max_stress", "type": "number", "value": 0,
         "form": {"mode": "output", "label": "Max. stress [MPa]"}},
    ],
    "nodes": [
        {"id": "solve", "kind": "actions", "name": "Solve", "instructions": [
            log("Static analysis of {mesh_file}, load {load_kn} kN"),
            wait(3.0),
            {"type": "SetNumber", "params": {"value": 184.6, "target": "max_stress"}},
            {"type": "WriteTextFile", "params": {
                "path": {"template": "{mesh_file}.static.txt"},
                "content": {"template": "load={load_kn} kN\nmax_stress={max_stress}\n"}}},
            log("Static done: max stress {max_stress} MPa"),
        ]},
    ],
    "edges": [{"from": "start", "to": "solve"}, {"from": "solve", "to": "exit"}],
})

save("solve_modal.flow.json", {
    "name": "Modal Analysis",
    "variables": [
        {"name": "mesh_file", "type": "path", "value": "",
         "form": {"label": "Mesh file", "path_kind": "file", "must_exist": True,
                  "required": True}},
        {"name": "modes", "type": "integer", "value": 10,
         "form": {"label": "Number of modes", "minimum": 1, "maximum": 50}},
        {"name": "first_freq", "type": "number", "value": 0,
         "form": {"mode": "output", "label": "1st eigenfrequency [Hz]"}},
    ],
    "nodes": [
        {"id": "solve", "kind": "actions", "name": "Solve modes", "instructions": [
            log("Modal analysis of {mesh_file}, {modes} modes"),
            wait(2.0),
            {"type": "SetNumber", "params": {"value": 142.3, "target": "first_freq"}},
            {"type": "WriteTextFile", "params": {
                "path": {"template": "{mesh_file}.modal.txt"},
                "content": {"template": "modes={modes}\nf1={first_freq} Hz\n"}}},
            log("Modal done: f1 = {first_freq} Hz"),
        ]},
    ],
    "edges": [{"from": "start", "to": "solve"}, {"from": "solve", "to": "exit"}],
})

save("report.flow.json", {
    "name": "Report",
    "variables": [
        {"name": "project_name", "type": "string", "value": "demo",
         "form": {"label": "Project name", "required": True}},
        {"name": "work_folder", "type": "path", "value": "",
         "form": {"label": "Work folder", "path_kind": "folder", "required": True}},
        {"name": "max_stress", "type": "number", "value": 0,
         "form": {"label": "Max. stress [MPa]"}},
        {"name": "report_format", "type": "string", "value": "txt",
         "form": {"label": "Format", "choices": ["txt", "md"]}},
        {"name": "report_file", "type": "path", "value": "",
         "form": {"mode": "output", "label": "Report"}},
        {"name": "summary", "type": "string", "value": "",
         "form": {"mode": "output", "label": "Summary"}},
    ],
    "nodes": [
        {"id": "rep", "kind": "actions", "name": "Write report", "instructions": [
            wait(1.0),
            {"type": "SetString", "params": {
                "value": {"template": "{work_folder}/{project_name}_report.{report_format}"},
                "target": "report_file"}},
            {"type": "SetString", "params": {
                "value": {"template": "{project_name}: max stress {max_stress} MPa"},
                "target": "summary"}},
            {"type": "WriteTextFile", "params": {
                "path": {"var": "report_file"},
                "content": {"template": "REPORT {project_name}\n{summary}\n"}}},
            log("Report written: {report_file}"),
        ]},
    ],
    "edges": [{"from": "start", "to": "rep"}, {"from": "rep", "to": "exit"}],
})

# ---- main process ------------------------------------------------------------ #

save("main_process.flow.json", {
    "name": "Bracket Study",
    "variables": [
        {"name": "project_name", "type": "string", "value": "bracket_v1",
         "group": "Project",
         "form": {"label": "Project name", "required": True,
                  "description": "Used as prefix for every result file."}},
        {"name": "work_folder", "type": "path", "value": "",
         "group": "Project",
         "form": {"label": "Work folder", "path_kind": "folder", "required": True,
                  "description": "All results are written here."}},
        {"name": "mesh_size", "type": "number", "value": 2.0, "group": "Settings",
         "form": {"label": "Element size [mm]", "minimum": 0.5, "maximum": 10}},
        {"name": "load_kn", "type": "number", "value": 5.0, "group": "Settings",
         "form": {"label": "Load [kN]", "minimum": 0, "maximum": 100, "required": True}},
        {"name": "report_format", "type": "string", "value": "txt", "group": "Settings",
         "form": {"label": "Report format", "choices": ["txt", "md"]}},
        {"name": "model_file", "type": "path", "value": ""},
        {"name": "mesh_file", "type": "path", "value": ""},
        {"name": "element_count", "type": "number", "value": 0,
         "form": {"mode": "output", "label": "Elements"}},
        {"name": "max_stress", "type": "number", "value": 0,
         "form": {"mode": "output", "label": "Max. stress [MPa]"}},
        {"name": "first_freq", "type": "number", "value": 0,
         "form": {"mode": "output", "label": "1st eigenfrequency [Hz]"}},
        {"name": "summary", "type": "string", "value": "",
         "form": {"mode": "output", "label": "Summary"}},
    ],
    "groups": [
        {"title": "Pre-processing", "x": -120, "y": -80, "width": 760, "height": 230,
         "color": "#3d7ad9"},
        {"title": "Solving", "x": 680, "y": -80, "width": 420, "height": 420,
         "color": "#519932"},
    ],
    "nodes": [
        {"id": "prep", "kind": "subworkflow", "file": "prepare.flow.json",
         "name": "Prepare Model", "x": 0, "y": 0,
         "description": "Creates the work folder and the model file.",
         "inputs": {"project_name": {"var": "project_name"},
                    "work_folder": {"var": "work_folder"}},
         "outputs": {"model_file": "model_file"}},
        {"id": "mesh", "kind": "subworkflow", "file": "mesh.flow.json",
         "name": "Mesh", "x": 340, "y": 0,
         "description": "Meshes the model with the chosen element size.",
         "inputs": {"model_file": {"var": "model_file"},
                    "mesh_size": {"var": "mesh_size"}},
         "outputs": {"mesh_file": "mesh_file", "element_count": "element_count"}},
        {"id": "static", "kind": "subworkflow", "file": "solve_static.flow.json",
         "name": "Static Load Case", "x": 720, "y": 0,
         "description": "Linear static analysis with the given load.",
         "inputs": {"mesh_file": {"var": "mesh_file"}, "load_kn": {"var": "load_kn"}},
         "outputs": {"max_stress": "max_stress"}},
        {"id": "modal", "kind": "subworkflow", "file": "solve_modal.flow.json",
         "name": "Modal Analysis", "x": 720, "y": 200,
         "description": "Eigenfrequencies — independent of the static case.",
         "inputs": {"mesh_file": {"var": "mesh_file"}},
         "outputs": {"first_freq": "first_freq"}},
        {"id": "report", "kind": "subworkflow", "file": "report.flow.json",
         "name": "Report", "x": 1100, "y": 0,
         "description": "Collects the static result into a report file.",
         "inputs": {"project_name": {"var": "project_name"},
                    "work_folder": {"var": "work_folder"},
                    "max_stress": {"var": "max_stress"},
                    "report_format": {"var": "report_format"}},
         "outputs": {"report_file": "report_file", "summary": "summary"}},
    ],
    "edges": [
        {"from": "start", "to": "prep"}, {"from": "prep", "to": "mesh"},
        {"from": "mesh", "to": "static"}, {"from": "mesh", "to": "modal"},
        {"from": "static", "to": "report"}, {"from": "report", "to": "exit"},
    ],
})
