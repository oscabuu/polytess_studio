# Changelog — polytess Studio

Semantic versioning (`polytess/__init__.py` is the single source; the
window title, `--version`, pyproject and tarball names derive from it).
Every commit bumps at least the patch version.

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
