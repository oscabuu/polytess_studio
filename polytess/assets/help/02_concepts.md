# Concepts — nodes, blocks, variables

polytess describes a computation process as a **flow**: a graph of
nodes, executed push-based from the entry points.

## Nodes

| Node | Purpose |
| --- | --- |
| **Start** | entry point, runs once per run |
| **Actions** | runs its list of instructions in order, then continues |
| **Conditions** | checks its conditions and continues on the **success** or **fail** port |
| **Branch** | if / else-if / else — the first matching case runs |
| **Trigger** | fires its children whenever its event occurs (timer, file change, …) |
| **Sub-Workflow** | calls another `.flow.json` with inputs/outputs, then continues |
| **Exit** | finishes the run |

Several outgoing connections run **concurrently**. A connection back to
an earlier node builds a retry/repeat loop.

## Sub-workflows

A Sub-Workflow node calls another flow like a function:

- **Inputs** bind a graph variable/list of the sub-flow to a value of
  the calling flow (constant, variable, list, table, template, loop
  target …). *None* keeps the sub-flow's own default.
- **Outputs** copy a graph variable/list of the sub-flow back into a
  variable of the calling flow after the call.
- **Load Interface from Sub-Workflow** adds a binding for every
  input/output variable of the sub-flow (its Viewer form modes) and
  pre-binds same-named variables of the calling flow.
- The sub-flow is loaded fresh for every call — its graph variables
  are private, parallel calls cannot interfere.
- *Share Global Variables* (default on): off gives the sub-flow a
  private **snapshot** of the globals taken at the call — it sees the
  caller's values as of that moment, later changes by the caller or by
  parallel branches are invisible, and its own global writes never leak
  back (outputs still reach the caller). *Fail If Sub-Workflow Fails*
  (default on): a failed node inside fails the calling node, outputs
  are not returned.
- Relative file paths resolve against the calling flow's folder (then
  the working directory). Nesting deeper than 32 levels is an error.
- A sub-flow with persistent triggers (timer, file, signal …) only
  returns when one of its Exit nodes runs — `polytess validate` warns.

## Building blocks

The payload of nodes: **Instructions** (do something), **Conditions**
(check something), **Events** (trigger something). polytess ships 100+
blocks — file/folder operations, templating, tables & CSV, loops,
waiting on results, solver calls, HPC job management, mesh morphing.
The searchable catalog opens with **Ctrl+Space** or *Add Instruction…*.

## Variables & properties

- **Graph variables** belong to one flow; **global variables** are
  shared across flows in one run. Both live in the Variables dock
  (values, lists and tables).
- Variables can be organized into **groups** (right-click → Move to
  Group, or drag a variable onto a group row; click a group header to
  collapse it; right-click a group header to rename or delete the
  group — deleting only dissolves it, the variables move out first).
  Groups are pure display metadata — moving a variable never touches
  references. **Renaming** a variable rewrites all its
  references in the current flow (sources, name fields and `{name}`
  templates), so renames don't break nodes either.
- Every variable and list carries a **status tag**: *unchecked* (the
  default), *checked* (you verified its content — click the Status cell
  or right-click → Mark as Checked; click again to reset) or *runtime*
  (some block of the flow writes it while running, so its content is a
  run result, not an input to review — derived automatically, never
  editable). Lists are checked as a whole. Click the Status header to
  sort by status, double-click it (or right-click → Hide Runtime
  Variables) to hide runtime ones. The checked mark is saved with the flow; the Flow
  Assistant sees it too and receives runtime variables without their
  contents.
- **Viewer Settings…** (right-click a variable or list) describe the
  field for the polytess Viewer — the run-only app in which non-expert
  users fill in a flow's inputs as a form without seeing the flow:
  label, help text, required, allowed choices, numeric bounds, path
  kind/existence, order inside the group, and the mode (*automatic*:
  input unless the flow writes it; *output*: shown read-only after the
  run; *hidden*). Headless: `polytess inputs flow.flow.json` prints
  the form, `--template values.json` writes a fillable preset, and
  `polytess run flow.flow.json --vars-file values.json` validates and
  applies it before the run.
- Every field of a block is a **property slot**: click the ▼ to switch
  its source — constant value, graph/global variable, formatted
  template (`MR_{deck}.inp`), split string, table cell, and more.
  Fields accept **drag & drop** from the Variables dock.
- Loops set a **target** (the current element); read it with the
  *Loop Target* source.
- **F4** (View → Show Current Values) toggles instruction previews
  between variable names (`graph:result_dir`) and the variables'
  current values (`/proj/runs`) — in node previews and the inspector
  alike. Unresolvable references keep showing their name.

## Files

Flows are saved as `*.flow.json` — plain, diff-friendly JSON that you
can inspect, version and share. Old files keep loading after upgrades.
