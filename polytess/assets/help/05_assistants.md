# AI assistants

polytess has two built-in AI assistants. Configure the provider under
**Settings → Assistant**: Claude (Agent SDK, one-time `claude login`) or
GitHub Copilot (your Copilot subscription; GitHub Enterprise host
supported).

## Flow Assistant (Ctrl+Shift+F)

Describe your process in plain language — the assistant designs a
complete flow (nodes, connections, variables) and validates every
building block against the installed catalog:

> "Combine the loads from my three output folders, generate the
> reduction deck, check the syntax, and submit to HPC — otherwise
> email the team."

**Insert flow** opens the result as a new document. If a step needs a
block that does not exist yet, the assistant proposes a ready-to-use
prompt for the code assistant (pencil button).

The assistant also sees the **currently open flow** — ask it to extend
or modify it ("add a syntax check after the folder setup") and it
answers with the complete updated flow, which "Insert flow" opens as a
new document next to the original.

## Code assistant (in the Code Editor)

**Library → Code Editor**, chat icon: the assistant knows the full
contract for custom Instructions/Conditions/Events, everything already
installed, and the file currently open in the editor. Ask for a new
block or for changes to the open file — the answer contains a complete
file. The pencil button inserts it at the cursor; the apply button
replaces the whole editor content with it (Ctrl+Z undoes). Saving
hot-reloads the class into the menus instantly.

The assistant can also **read and edit the custom library directly**
(Claude provider): it works inside your custom-library folder and may
create or fix block files itself — polytess hot-reloads the library
right after each answer. The folder is configurable under
**Settings → Python → Custom Library** (empty =
`~/.polytess/custom_library`).

## What the assistants know

Both assistants receive the full shape of every installed building
block — title, category, description, and every parameter with its
type, tooltip text and choices. The flow assistant additionally reads
`~/.polytess/flow_best_practices.md`, a growing best-practices file:
edit it yourself, or let the assistant extend it — when a conversation
teaches a reusable lesson it appends the lesson automatically (watch
the status bar).

## Attachments

The **+** button next to either input attaches text files (input decks,
CSV samples, scripts) to your next message — great for "build a flow
that processes files like this one".
