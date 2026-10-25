# polytess Viewer

The Viewer is the run-only companion of the Studio: non-expert users
open a flow, fill in its inputs and start it — without seeing nodes,
connections or runtime variables. It never edits a flow.

Start it with `polytess-viewer [flow.flow.json]` (in a Python
environment `python -m polytess.viewer …`); the executable bundle
ships it next to the Studio. Dropping a `.flow.json` on the window
opens it; the start page lists recent flows.

## Single flow: the form

A flow without sub-workflow nodes opens as a **form**:

- One field per input variable, grouped like the Blackboard groups,
  with the label, help text, required mark, choices, bounds and path
  browser you set in the Studio (right-click a variable → *Viewer
  Settings…*). Runtime-written variables never appear; variables with
  mode *output* are shown on the result page.
- **Presets** save input sets per flow family (`Save as…`, the
  dropdown, `Last values`, `Defaults`). The format is the one of
  `polytess-cli run --vars-file`.
- `Check` validates (required, bounds, choices, path existence);
  `Start` runs the flow in the chosen work folder with progress,
  phase (sectioning convention), elapsed time and log; `Stop` and
  `Pause` are available while running.
- The **result page** shows success/failure, duration, the output
  variables, and offers *Open work folder*, *Save log*, *Run again*.

## Main process: the board

A flow whose nodes are **Sub-Workflow nodes** (see *Sub-workflows* in
Concepts) opens as a **Kanban board**: every sub-workflow node is a
card, the connections are the dependencies.

| Backlog | In Progress | Done |
|---|---|---|
| not run yet, outdated, failed | queued or running (progress bar) | finished (duration) |

- **Drag a card to In Progress** (or double-click it, or *Start* in the
  detail panel) to run it. If predecessors are unfinished, a dialog
  offers *Run in order* (they are queued and run first), *Only this
  step* or *Cancel*.
- **Results are remembered** in `<flow>.board.json` next to the main
  flow: reopening shows finished cards in Done. A card whose inputs
  changed since (or whose predecessor was re-run) turns *outdated*;
  *Process inputs…* edits the main flow's own inputs and marks
  affected cards. Drag a Done card back to Backlog (or *Forget
  result*) to clear it together with its successors.
- **Auto-advance** (toggle, default on) starts every card whose
  predecessors are Done — parallel branches run at the same time;
  failed cards are never retried automatically. *Run all* does the
  whole process; *Reset* forgets everything.
- The **detail panel** shows the selected card's description,
  dependencies, bindings, the current step and the log; *Open log*
  opens the saved file under `<work folder>/.runs/`.
- The **dashboard** shows progress, counters per status, time spent,
  estimated remaining time (from earlier durations of the same
  cards), success rate, the most failing card and the runs of
  the last 30 days.

Card titles come from the node name, the text on the card from the
node's *Card description* (Inspector of the Sub-Workflow node). The
main process must be acyclic; `polytess-cli board` reports problems.

## Celebrations

*Celebrations* in the toolbar: `off` (plain), `subtle` (default:
cards slide and bounce when they land in a column, a short glow and a
toast when a card finishes) or `full`
(additionally confetti when the whole process is done). Feedback
rewards progress of the process, never click counts, and never blocks.

## Follow on phone

*Phone…* in the toolbar (or *Follow on phone…* on the board) shows a
**QR code**. Scan it with the phone's camera: the phone opens a page
served by the Viewer itself and mirrors the board live — columns,
progress of the running card, dashboard numbers, a card's description
and its last log lines (tap a card). When a card finishes or fails
the phone shows a banner and vibrates while the page is open.

- The phone must reach this computer: same Wi-Fi or VPN. Windows asks
  once to allow the Viewer through the firewall; the port (default
  8765) is a setting (`mobile_port`). Pick the right address in the
  dialog if the computer has several (Wi-Fi vs. VPN adapter).
- The link contains a random **token** valid while the Viewer runs;
  *New code* invalidates every earlier link. Without the token the
  server answers nothing.
- **Allow start / stop from the phone** (off by default) lets the
  phone start cards (with the same predecessor choice), stop them and
  run all; every phone action is written to the Viewer's log.
- The phone follows whichever board is open in the Viewer; the form
  page is not mirrored. The page is plain HTTP inside your network —
  do not use it over an open guest Wi-Fi. Needs
  `pip install polytess[mobile]` (aiohttp, qrcode); the executable
  bundle includes both.

## Headless twin

`polytess-cli board main.flow.json --run "Mesh"` runs a card with its
predecessors from a terminal or scheduler and updates the same board
state, so the Viewer shows the result afterwards.
