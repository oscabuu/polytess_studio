# Changelog — polytess Studio

Semantic versioning (`polytess/__init__.py` is the single source; the
window title, `--version`, pyproject and tarball names derive from it).
Every commit bumps at least the patch version.

## 1.11.0 — 2026-08-11
- Docks are closable again (the theme had hidden the title-bar close
  icon): every panel — Flow Assistant included — closes via its × and
  reopens from the View menu (the Flow Assistant now has a toggle
  there too).
- Docks can be stacked as tabs and arranged side by side: drag one
  panel onto another to tabify, or next to it to split (tabbed +
  nested dock options, dock nesting enabled). The Flow Assistant
  opens as a tab next to the Inspector by default.

## 1.10.2 — 2026-08-11
- Settings → Reports gains an **Email** field (`report_email`): the
  default notification recipient, readable from any instruction via
  AppSettings. Send Email uses it automatically whenever its "to"
  field is left empty.

## 1.10.1 — 2026-08-11
- Manual: worked example showing that Settings → Python → Include
  Paths work directly inside custom blocks — a plain `import` suffices,
  the paths never need to be repeated in the instruction (verified by
  an end-to-end test).

## 1.10.0 — 2026-08-11
- The Code Assistant (Claude provider) can now read and edit the
  custom library directly: its session runs inside the custom-library
  folder with Read/Write/Edit/Glob/Grep and auto-accepted edits, and
  polytess hot-reloads the whole library right after each answer. For
  the file open in the editor it still answers with a code block
  (insert/apply) to avoid conflicts with unsaved changes. The Flow
  Assistant stays plain chat.
- New setting **Settings → Python → Custom Library**: the folder for
  custom blocks (empty = `~/.polytess/custom_library`; the
  POLYTESS_CUSTOM_LIBRARY env var still wins). Code editor, loader and
  assistant all follow it.

## 1.9.0 — 2026-08-11
- The Flow Assistant now receives and preserves the COMPLETE flow:
  variable groups, node positions (x/y), canvas groups and sticky
  notes are part of the simplified schema, exported with the open flow
  and rebuilt on insert. Its instructions explicitly demand keeping
  everything untouched that the user didn't ask to change, so
  modification answers no longer destroy layout and organization.
  Flows round-tripped with explicit positions keep them (the
  auto-layout only runs for flows built from scratch).

## 1.8.2 — 2026-08-11
- Fixed the assistant chat scroll regression from 1.7.4: while an
  answer streamed in, the view could jump to the top and refuse to
  scroll until the answer finished. Attach/detach now reacts only to
  real user input (wheel, scrollbar drag, arrow/page clicks, keys) —
  never to programmatic scroll changes — and while detached the
  reading position is restored after every re-render.

## 1.8.1 — 2026-08-05
- Right-click on a variable-group header now offers **Rename Group…**
  (moves every member, keeps the collapse state) and **Delete Group**
  (dissolves the group — all variables move out first and survive).

## 1.8.0 — 2026-08-05
- Variables can be organized into **groups** in the Blackboard:
  collapsible group header rows, right-click → Move to Group (existing
  group, new group, or none), and drag & drop of a variable onto a
  group row. Group membership is pure display metadata on the variable
  — references always go by name, so moving between groups can never
  break a node.
- **Renaming a variable now rewrites all references** in the current
  flow (property sources, plain name fields and `{name}` template
  placeholders — new `rename_references` in core.refs), so renames
  don't break nodes either. This covers the rename-safety goal without
  an id-based reference scheme, which text templates could never
  support anyway.

## 1.7.6 — 2026-08-05
- Inspector tooltips moved onto the parameter NAMES: labels of block
  parameters are now bold and carry the FIELD_HELP text; value editors
  no longer show tooltips. Sub-rows of a bound source (Variable /
  Value / Template) explain the actual parameter ("which file this is
  and what it is for") instead of the generic source mechanics.

## 1.7.5 — 2026-08-05
- Table variables in the Blackboard are back to ONE compact row: a
  summary ("2 columns × 5 rows") plus an edit icon that opens the
  spreadsheet editor (MATLAB-style: column headers on top, each
  column's values below). The inline mini-grid from 1.5.0 made the
  variables list unwieldy and is gone.

## 1.7.4 — 2026-08-05
- Assistant chat views now follow the end of the text while an answer
  streams in (previously the view drifted to the top on re-renders).
  Scrolling up detaches the view so earlier parts can be read;
  scrolling back to the bottom re-attaches it.

## 1.7.3 — 2026-08-05
- Custom-block contract: `title` properties must never call
  `.get(ctx)`/`.get(None)` on fields — titles render without an active
  run and crashed on variable-bound fields. The code assistant's
  contract and the manual now state the rule (`str(self.field)` is the
  safe form), and a regression test binds every library block's fields
  to variables and renders all titles without a ctx.

## 1.7.2 — 2026-08-03
- .gitignore: `externe_Instructions/` added to the local-only section
  (external client-specific instruction drafts and their test data
  never get committed).

## 1.7.1 — 2026-08-03
- Flow Assistant: two standing rules added to its instructions — name
  missing building blocks openly and hand them to the code assistant
  instead of forcing a workaround, and split long flows into sections
  via bool milestone variables (e.g. `section_1_completed`, set by
  SetBool, next section started by an OnVariableChanged trigger).
  The sectioning pattern is also part of the seeded best-practices
  file.

## 1.7.0 — 2026-08-03
- Both assistants now receive the complete shape of every building
  block: per class the title, category and description, plus every
  field with its kind, choices and the new tooltip help text — the
  code assistant also generates FIELD_HELP for new custom blocks.
- The Flow Assistant follows a growing best-practices file
  (`~/.polytess/flow_best_practices.md`, seeded on first use): the
  user can edit it, and the assistant appends reusable lessons it
  proposes in a ```bestpractice block automatically.

## 1.6.0 — 2026-08-03
- Every parameter of every built-in Instruction, Condition, Event and
  property source now has a tooltip in the inspector explaining what
  the value provides and how it is used (229 texts). New mechanism:
  a class-level `FIELD_HELP` dict (merged along the inheritance chain,
  like `FIELD_CHOICES`); the right-click Help popup lists the texts
  too, and custom blocks can declare their own `FIELD_HELP`.

## 1.5.0 — 2026-08-03
- Table variables in the Blackboard now render as a real inline table —
  column headers on top, the rows' values below, cells editable in
  place, with +/− row/column buttons — instead of a summary line that
  needed a double-click into the editor dialog. The full-size editor
  dialog stays available via the pencil button on the inline table.

## 1.4.0 — 2026-08-03
- The Flow Assistant now sees the currently open flow: modification
  requests ("add a check after X") get the full existing workflow as
  context (new exporter `flow_to_data`, the inverse of `build_flow`)
  and answer with the complete updated flow.
- The Code Assistant can now effectively edit the open file: a new
  apply button replaces the whole editor content with the proposed
  code block (undoable with Ctrl+Z), alongside the existing
  insert-at-cursor button.

## 1.3.1 — 2026-08-03
- While an assistant request is running, the status line now cycles
  through playful messages ("Reticulating splines…", "Herding tokens…")
  instead of a static "Claude is answering…" — Claude-Code style.

## 1.3.0 — 2026-08-01
- Replaced the direct Anthropic Messages API integration with the
  **Claude Agent SDK** as the default assistant provider for the Flow
  Assistant and Code Assistant. Authentication is now a one-time
  `claude login` (Claude Code CLI, bundled with the SDK) instead of an
  API key — the "Anthropic API Key" setting is gone. Both assistants
  stay plain chat: every built-in SDK tool is disabled, so behavior is
  otherwise unchanged. GitHub Copilot remains available as an
  alternative provider.

## 1.2.0 — 2026-07-27
- Flow Assistant and Code Assistant chat inputs: Enter now sends the
  message; Shift+Enter inserts a newline (was Ctrl+Enter to send).
- Settings → Python: configurable list of extra `sys.path` directories
  ("Include Paths") so custom_library modules and in-studio Python code
  can import your own local packages without an environment variable.
  Applies immediately on save, no restart needed.

## 1.1.0 — 2026-07-27
- Undo/Redo now covers node **content**, not just graph structure: field
  edits (header fields, Property source values, source-type swaps, the
  trigger event type) and Instructions/Conditions/Branches list edits
  (insert/replace/duplicate/delete/reorder) are all undoable.
  Consecutive edits to the same field (e.g. typing) merge into a single
  undo step.

## 1.0.3 — 2026-07-27
- Translated the remaining German text to English throughout the repo
  (README, HOWTO_LINUX, LICENSE.txt's non-legal notes, requirements.txt
  comments, a leftover docstring shared by ~47 files, and one UI string)
  so the whole project is fully English.

## 1.0.2 — 2026-07-27
- Removed `PLAN.md` and `STATUS.md` (internal planning/status notes) and
  their references — this changelog now starts at the 1.0.0 relicense
  instead of carrying pre-public development history.

## 1.0.1 — 2026-07-27
- In-app manual: removed the dangling "Engineering demos (meshvary)"
  example-gallery entry — that plugin isn't shipped in this repository.
- Genericized two more incidental part-name-shaped test fixture values
  (`MR_GEH`/`MR_LAG` -> `MR_A`/`MR_B`) found by a follow-up audit.

## 1.0.0 — 2026-07-27
- **Relicensed to the Business Source License 1.1** (`LICENSE.txt`):
  any use permitted, including internal commercial use — only resale,
  redistribution or hosting as a competing product needs a separate
  commercial agreement. Converts automatically to Apache License 2.0 on
  2030-07-27. Starting the app, the CLI and running a flow no longer
  require any license file (BUSL doesn't gate usage); the commercial
  Ed25519 license file is now an opt-in for extended rights (Help ->
  Commercial License…).
- Dropped the Cython-compiled distribution: the app now ships and runs
  as plain Python source everywhere (desktop executables, source
  tarball); `build_compiled.py` and the Colima-based Linux cross-build
  script are gone.
- Only `plugins/simpack_template` (the "how to write a plugin"
  reference) ships in this repository — other domain plugins are
  local-only add-ons (see `.gitignore`) with no bearing on the base
  product's license or distribution.
- Removed leftover client-specific identifiers from the codebase
  (an internal default hostname, a department code, a client name and
  vendor tool names in docstrings and CI) and untracked further client-specific
  planning notes and example content from git history going forward.
