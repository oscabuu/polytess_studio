# AI assistants

polytess has two built-in AI assistants. Configure the provider under
**Settings → Assistant**: Anthropic (Claude API key) or GitHub Copilot
(your Copilot subscription; GitHub Enterprise host supported).

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

## Code assistant (in the Code Editor)

**Library → Code Editor**, chat icon: the assistant knows the full
contract for custom Instructions/Conditions/Events and everything
already installed. Ask for a new block — the answer contains a complete
file you can insert with one click; saving hot-reloads it into the
menus instantly.

## Attachments

The **+** button next to either input attaches text files (input decks,
CSV samples, scripts) to your next message — great for "build a flow
that processes files like this one".
