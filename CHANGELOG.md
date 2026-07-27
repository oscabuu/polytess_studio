# Changelog — polytess Studio

Semantic versioning (`polytess/__init__.py` is the single source; the
window title, `--version`, pyproject and tarball names derive from it).
Every commit bumps at least the patch version.

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
