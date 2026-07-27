# polytess — Workflow Studio for Mechanical-Engineering Computations

Visual-scripting studio (variables, properties, actions, conditions,
events) with a node graph editor — a desktop studio (PySide6) for
computation workflows: setting up directories, templating input files,
running Simpack/Abaqus jobs and DOEs, post-processing, loops.

## Installation & Start

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"

# GUI studio
./.venv/bin/python -m polytess                      # empty studio
./.venv/bin/python -m polytess examples/demo.flow.json

# Headless (batch / compute server / HPC)
./.venv/bin/python -m polytess.cli run examples/demo.flow.json --var case=run42
./.venv/bin/python -m polytess.cli validate examples/demo.flow.json

# Tests
./.venv/bin/python -m pytest
```

## Using the Studio

| Action | How |
|---|---|
| Create a node | Right-click the canvas → *Add Node…* or `Ctrl+Space` (searchable menu) |
| Connect | Drag from one port (circle) to another |
| Edit a node | Select the node → **Inspector** (right): Actions/Conditions lists |
| Add an action | Inspector → *Add Instruction…* → category tree/search |
| Field = variable instead of value | Dropdown button right of the field → e.g. *Graph Variable* |
| Reorder | Drag a row by its handle (blue drop indicator) |
| Row context menu | Copy/Paste/Replace/Insert/Breakpoint/Disable/Help |
| Variables | **Variables** dock (left): graph and global scope, live during a run |
| Run | `F5` / ▶ — running nodes blue, success green, failure red; log below |
| Stop | `Shift+F5` / ■ |
| Pan / zoom / fit | Middle mouse button / wheel / `F` |
| Undo/Redo | `Ctrl+Z` / `Ctrl+Shift+Z` (graph structure and node content) |
| Copy/Paste | `Ctrl+C` / `Ctrl+V` / `Ctrl+D` (nodes incl. internal edges) |
| Groups / notes | Right-click → *Add Group* / *Add Sticky Note* (double-click to edit) |
| Sub-workflow | Sub-Workflow node, double-click opens it as a tab |

## Concepts

- **Instruction** (`async run(ctx)`): an action; lists run sequentially,
  with a relative program counter (Skip/Restart/Stop).
- **Condition** (`run(ctx) -> bool`): with an If/Not sign; lists combine
  with AND/OR.
- **Branch**: conditions + instructions; BranchList = if/elif/else.
- **Event**: fires trigger nodes (On Start, On Signal, On Timer, On File
  Changed).
- **PropertyGet/PropertySet**: every field is a constant OR a variable
  reference (graph/global, list picks, formatted string `{var}`, env
  var, date/time, …).
- **Graph**: Start/Exit/Actions/Conditions/Branch/Trigger/Sub-Workflow
  nodes; push-based execution, multiple outgoing edges run in parallel;
  the Conditions node branches via *Success*/*Fail* ports.
- **Persistence**: tagged JSON (`*.flow.json`), diff-friendly, version
  control-friendly.

## Your Own Domain Actions (Simpack, Abaqus, …)

Template: [plugins/simpack_template](plugins/simpack_template) — its
own package with the `polytess.plugins` entry point; loaded
automatically at startup.

**File convention: one class per file:**
`instruction_<name>.py` / `condition_<name>.py` / `event_<name>.py`.
Every file named this way in the plugin folder (and in
`polytess/library/…`) is **loaded automatically** at startup — dropping
in a new file is enough, no import line needed. Files with a leading
`_` are skipped (e.g. the copy template `_template.py`).

```python
@meta(title="Run Simpack Solver", category="Simpack/Run Simpack Solver",
      icon="terminal", color="red", description="…")
class RunSimpackSolver(Instruction):
    def __init__(self, model: str = ""):
        super().__init__()
        self.model = PropertyGetPath(model)      # constant OR variable

    @property
    def title(self):                             # dynamic list title
        return f"Simpack solve {self.model}"

    async def run(self, ctx):
        ...                                      # ctx.info/error, ctx.resolve_path,
                                                 # RunCommand pattern for subprocesses
```

```bash
./.venv/bin/pip install -e plugins/simpack_template
```

## Project Structure

```
polytess/
├── core/       # GUI-free: values, variables, properties, instructions,
│               # conditions, events, signals, serialization
├── graph/      # GUI-free: graph model, node types, asyncio processor
├── library/    # generic actions/conditions/events (files, process, …)
├── gui/        # PySide6 studio (theme, graph editor, inspector, log, …)
├── cli.py      # headless runner
└── __main__.py # studio entry point
plugins/        # domain-plugin templates (Simpack/Abaqus)
examples/       # example workflows
tests/          # pytest (core, graph, library, GUI smoke offscreen)
```

## Notes

- Undo/Redo covers the graph structure (nodes/edges/positions) and node
  content (field values, Instructions/Conditions/Branches list edits);
  rapid edits to the same field (e.g. typing) merge into one undo step.
- The node body shows a live preview of its actions/conditions; editing
  happens in the Inspector (selecting the node is enough).
- `ValueNumber` is `float` (double).

## License

[Business Source License 1.1](LICENSE.txt) — free to use, including
commercially/internally, just no resale/hosting as your own product.
Automatically converts to Apache License 2.0 on 2030-07-27.
