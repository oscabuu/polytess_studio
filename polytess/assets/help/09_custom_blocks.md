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

Need to `import` your own local packages from a custom block? Add their
folders under **Settings → Python → Include Paths** — no environment
variable needed, changes apply immediately without a restart, and the
paths do NOT have to be repeated anywhere in the instruction. A plain
`import` just works, because the paths are on `sys.path` for the whole
process before the custom library loads:

```python
# Settings → Python → Include Paths contains  /home/me/tools
# and /home/me/tools/loadtools/__init__.py defines combine(...)
from loadtools import combine          # plain import — nothing else needed

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetPath


@meta(title="Combine Loads", category="Custom/Combine Loads",
      icon="transform", color="teal",
      description="Combines load files via the local loadtools package")
class CombineLoads(Instruction):

    FIELD_HELP = {
        "folder": "Folder whose load files are combined.",
    }

    def __init__(self):
        super().__init__()
        self.folder = PropertyGetPath("")

    async def run(self, ctx):
        result = combine(ctx.resolve_path(self.folder.get(ctx)))
        ctx.info(f"combined: {result}")
```

## Rules of thumb

- Raise an exception to fail the node — never swallow errors silently.
- In a `title` property never call `.get(ctx)`/`.get(None)` on a
  field — titles render without an active run and crash on
  variable-bound fields. Use `str(self.field)` instead; `.get(ctx)`
  belongs only inside `run()`.
- Long work: `await asyncio.to_thread(...)`; console commands:
  `run_console(ctx, …)` (honors the command server) or
  `run_solver(ctx, "fem"|"mks", …)` (honors the solver profiles).
- Keep the class name stable — it is the `$type` tag in saved flows.

The full contract with templates lives in the code assistant's head:
open the chat and ask for a block — the generated file follows all
conventions.
