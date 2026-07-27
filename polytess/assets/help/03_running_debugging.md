# Running & debugging

## Run control

- **F5** runs the current flow, **Shift+F5** stops it. Nodes highlight
  live: blue = running, green = success, red = failed, yellow = paused.
- The **Log** dock records every step; each run starts with a header
  line including the flow's branch and revision (`main·r4`).
- A failing instruction raises an error: its node turns red, the branch
  of the flow stops, the message lands in the log.

## Breakpoints, pause, step

- Select a node and press **B** to toggle a breakpoint (red dot) — the
  run pauses right before that node.
- **F6** pauses/resumes the whole run, **F7** executes exactly one node
  and stays paused.
- While paused, inspect live variable values in the Variables dock.

## Triggers

Flows with **Trigger** nodes stay alive after the initial pass and
react to their events (timer, file appeared/changed, date, variable
changed, signal) until you stop the run.

## Validation

**Graph → Validate** checks the flow structure (dangling connections,
missing entry points) without running it. The headless CLI has the
same: `polytess-cli validate flow.flow.json`.
