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
| **Sub-Workflow** | runs another `.flow.json`, then continues |
| **Exit** | finishes the run |

Several outgoing connections run **concurrently**. A connection back to
an earlier node builds a retry/repeat loop.

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
