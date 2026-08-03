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

## Attachments

The **+** button next to either input attaches text files (input decks,
CSV samples, scripts) to your next message — great for "build a flow
that processes files like this one".
