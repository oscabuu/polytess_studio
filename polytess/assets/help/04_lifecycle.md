# Branches, history & flow documentation

polytess versions your flows without any external tooling — every flow
file carries its own identity (family id, branch name, revision).

## Automatic history

Every save bumps the revision and stores an immutable snapshot under
`.history/<flow-id>/` next to the file. **Graph → Flow History…** lists
all snapshots; double-click opens one.

## Branches

- **Graph → Create Branch…** (Ctrl+B) copies the flow as
  `<name>@<branch>.flow.json` — a full flow you can edit and run,
  which remembers where it came from.
- **Graph → Compare with Parent** (Ctrl+D) shows a structural diff:
  added/removed/changed nodes, connections and variables. Click an
  entry to jump to that node on the canvas.
- **Graph → Promote to Parent…** replaces the parent with the branch —
  the old parent state is kept as a history snapshot first.

Typical use: branch a proven flow, try different settings, compare,
promote the winner. Runs are tagged with `branch·revision` in the log,
so results stay attributable.

## PDF documentation

**File → Export Documentation…** renders the flow as a linked PDF:
clickable diagram (nodes jump to their chapter), table of contents, one
chapter per node with all parameters, and the variables appendix.
Headless: `polytess-cli doc flow.flow.json`.
