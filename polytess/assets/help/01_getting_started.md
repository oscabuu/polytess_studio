# Getting started — your first flow in 5 minutes

Welcome to polytess Studio! In this short tutorial you build, run and
debug your first workflow. No programming needed.

## 1. Create a flow

- **File → New** gives you an empty flow with a **Start** and an **Exit**
  node. Every run begins at Start and finishes at Exit.
- Press **Ctrl+Space** (or right-click the canvas) to open the node
  menu. Add an **Actions** node.
- Drag a connection from the Start node's **out** port to the Actions
  node's **in** port, and from its **out** port to Exit.

## 2. Give it something to do

- Select the Actions node — the **Inspector** (right) shows its payload.
- Click **Add Instruction…** and pick **Log Message** (just start
  typing "log" — the menu has fuzzy search).
- In the instruction's *Message* field type: `Hello polytess!`
- Add a second instruction: **Create Folder** with path `results`.

## 3. Run it

- Press **F5** (or the green play button). Nodes light up while they
  run: blue = running, green = done, red = failed.
- The **Log** dock (bottom) shows your message and every step.

## 4. Use a variable

- Open the **Variables** dock (left), add a variable `name`, type
  *string*, value `world`.
- Back in your Log Message instruction, click the small **▼** next to
  the message field and switch the source to **Formatted String**.
  Enter: `Hello {name}!`
- Run again — the log now says `Hello world!`. Every field in polytess
  can be a constant, a variable or a template like this.

## 5. Debug like a pro

- Select the Actions node and press **B** — a red dot appears
  (breakpoint). Run again: the flow pauses before the node.
- **F7** steps one node forward, **F6** resumes, the Variables dock
  shows live values while paused.

## Arrange your workspace

All panels (Inspector, Variables, Log, Flow Assistant) are dockable:
close them with the **×** in their title bar, reopen them via the
**View** menu, drag one panel onto another to stack them as **tabs**
(the Flow Assistant opens tabbed next to the Inspector by default), or
drop it beside another panel to place them side by side. **View →
Restore Default Layout** puts everything back.

## Where to go next

- **File → New from Example…** opens ready-made flows to explore —
  start with *Tutorial 2 (loops & conditions)*.
- The **Flow Assistant** (Ctrl+Shift+F) builds complete flows from a
  plain-language description — see the *AI assistants* chapter.
- Save your flow (**Ctrl+S**) — every save keeps a history snapshot,
  see the *Branches & history* chapter.
