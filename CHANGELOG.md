# Changelog — polytess Studio

Semantic versioning (`polytess/__init__.py` is the single source; the
window title, `--version`, pyproject and tarball names derive from it).
Every commit bumps at least the patch version.

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

## 0.11.0 — 2026-07-25
- License management dialog (Help -> Manage License…): view licensee,
  expiry, machines and license file, import a new .lic file, open the
  license folder. Shown automatically at startup instead of a dead-end
  error when no valid license is found.
- View -> Restore Default Layout: puts the Inspector/Variables/Log
  docks and toolbar back to their startup positions and sizes.

## 0.10.2 — 2026-07-25
- Manual redesigned in the website look: dark card layout, accent
  headings, styled tables/code/quotes, bundled Outfit/Bricolage fonts,
  refreshed chapter sidebar.

## 0.10.1 — 2026-07-25
- CI: tests depending on company-only content (custom instructions,
  otools examples) now skip cleanly on checkouts without it — the
  public pipeline runs 164 tests, dev machines all 181.

## 0.10.0 — 2026-07-25
- In-app manual (Help -> Manual, F1): nine chapters from a 5-minute
  getting-started tutorial to custom-block development.
- Example gallery (File -> New from Example…): tutorial flows and
  engineering demos open as unsaved copies.
- Three bundled tutorial flows (hello, loops & conditions, watch
  folder) shipping with every build including executables.

## 0.9.0 — 2026-07-25
- CI/CD: GitHub Actions test workflow (Linux, every push, pip cache,
  concurrency cancel) and release workflow (tag push -> Windows desktop
  executable + Linux server tarball, published as GitHub release).
  Release artifacts never contain company blocks or license files.
- Standalone executables (build_exe.py): PyInstaller one-dir bundle
  with the Cython-compiled core, GUI executable + headless CLI
  executable, versioned zip. License/plugins/custom_library are also
  found next to the executable (frozen mode).

## 0.8.0 — 2026-07-25
- Prompt attachments: a "+" button in both assistants (flow assistant
  and the code editor's Claude assistant) attaches text files to the
  next message (shown as chips, sent as tagged blocks; binary and
  oversized files are rejected).

## 0.7.1 — 2026-07-25
- Help → About dialog showing version, license status and website
  (support ticket #7).

## 0.7.0 — 2026-07-25
- Version infrastructure: single-source semver, `--version`, version in
  window title and tarball names, this changelog.
- Assistant provider abstraction: both assistants run on Anthropic
  (Claude API) or GitHub Copilot (official SDK, GitHub Enterprise host
  configurable, `copilot login --host …`).

## 0.6.0 — 2026-07-24
- meshvary plugin: manufacturing scatter on Abaqus FE meshes — bearing
  seat morphing (cylinder fit, RBF), correlated wall-thickness noise,
  porosity fields (raycast wall thickness, trend × lognormal noise,
  GTN/FIELD includes), quality checks, VTU previews, roundtrip .inp
  parser; demo flows.

## 0.5.0 — 2026-07-23
- Solver profiles (Settings → Solvers): MKS/FEM calls with per-target
  SSH, remote shell dialect (tcsh/bash/cmd) and shared-storage path
  mapping; Run Solver block.
- Flow documentation export: linked PDF (clickable diagram, chapters,
  blackboard) in the winthirstudios.com style; `polytess doc` CLI.

## 0.4.0 — 2026-07-22
- Flow lifecycle: branches, revisions, automatic history snapshots,
  structural diff (click-to-node navigation), promote to parent.
- Git repository established; client-specific content excluded.

## 0.3.0 — 2026-07-21
- Rename to polytess Studio (from polyflow/gcflow) with two-generation
  compatibility (user-dir migration, env fallbacks, import aliases).
- All Game Creator/SM2/Unity references removed; assistants and UI
  fully in English.

## 0.2.0 — 2026-07-20
- polyflow rename; flow assistant (AI builds workflows from a prompt);
  code assistant chat styling; homepage assets.

## 0.1.0 — 2026-07-17
- Initial polytess core: node graph editor, 90+ blocks, HPC/SSH
  integration, licensing (Ed25519), Cython build pipeline, code editor
  with AI assistant.
