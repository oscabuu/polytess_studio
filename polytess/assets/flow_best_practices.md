# Flow best practices

This file is read by the Flow Assistant on every conversation and grows
over time: edit it freely, and when the assistant proposes a new lesson
in a ```bestpractice block it is appended here automatically.

## Structure

- One actions node per logical phase (setup, solve, post-process) —
  don't scatter single instructions across many tiny nodes, and don't
  pile the whole process into one node either.
- Conditions nodes are gates: success/fail ports route the flow. Use
  them after every phase whose outcome later phases depend on.
- Branch nodes replace chains of conditions nodes when more than two
  outcomes exist (case A / case B / fallback).
- Loops: prefer LoopList/LoopRange/RepeatUntil body instructions over
  wiring an edge back to an earlier node — back-edges are for genuine
  retry semantics, not iteration.
- Triggers only for genuinely event-driven starts (file appears, date
  reached, variable changed); everything else starts from the start
  node.

## Variables

- Declare every value that appears twice as a graph variable; reference
  it with {"var": ...} or a {"template": "..."} instead of repeating
  literals.
- Global variables are for cross-flow state only (license servers,
  cluster hosts) — keep flow-local state in graph variables.
- Tables are the right shape for per-case parameter sets (one row per
  case, one column per parameter); loop them with Loop Table and read
  cells via the Table Cell source.

## Robustness

- After every external step (solver run, console command, file
  download) check the outcome with a conditions node — FileExists,
  CompareNumber on an exit code, or a dedicated check block.
- Fail early: a Fail instruction with a clear message beats a flow
  that continues with broken inputs.
- Paths: build them with Formatted Path templates from variables, never
  by string concatenation across several nodes; keep everything
  relative to the working directory where possible.

## Naming

- Node names describe the phase in the user's domain language
  ("Prepare decks", "Submit to HPC"), not the block names.
- Variable names are lower_snake_case and say what the value is
  (deck_name, result_dir), not where it came from.
