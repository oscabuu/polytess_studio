# Writing custom blocks

When the catalog has no block for your step, write one — it is a single
Python file, and the built-in code assistant writes most of it for you.

## The short version

- **Library → Code Editor → New** creates a skeleton. One class per
  file: `instruction_*.py`, `condition_*.py` or `event_*.py` in
  `~/.polytess/custom_library/`.
- Decorate with `@meta(title, category, icon, color, description)` —
  that's what the Add menu shows.
- Declare fields in `__init__` with property types
  (`PropertyGetString`, `PropertyGetPath`, `PropertyGetList`, …) —
  they appear in the inspector automatically, with variable binding
  and templates for free.
- Instructions implement `async def run(self, ctx)`; conditions
  `def run(self, ctx) -> bool`. `ctx` gives you logging, path
  resolution, variables and cancellation.
- **Save = live**: the block hot-reloads and appears in the menus
  immediately. Errors show up in the editor, not as crashes.

## Rules of thumb

- Raise an exception to fail the node — never swallow errors silently.
- Long work: `await asyncio.to_thread(...)`; console commands:
  `run_console(ctx, …)` (honors the command server) or
  `run_solver(ctx, "fem"|"mks", …)` (honors the solver profiles).
- Keep the class name stable — it is the `$type` tag in saved flows.

The full contract with templates lives in the code assistant's head:
open the chat and ask for a block — the generated file follows all
conventions.
