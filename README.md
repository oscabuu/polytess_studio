# polytess — Workflow Studio für Maschinenbau-Berechnungen

Visual-Scripting-Studio (Variablen, Properties, Actions, Conditions,
Events) mit Node-Graph-Editor
Graph-Editors — als Desktop-Studio (PySide6) für Berechnungsworkflows:
Verzeichnisse anlegen, Inputfiles templaten, Simpack-/Abaqus-Läufe und DOEs
starten, Postprocessing, Loops.

Architektur- und Portierungsdetails: siehe [PLAN.md](PLAN.md).

## Installation & Start

```bash
cd Assets/Python
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"

# GUI-Studio
./.venv/bin/python -m polytess                      # leeres Studio
./.venv/bin/python -m polytess examples/demo.flow.json

# Headless (Batch / Rechenserver / HPC)
./.venv/bin/python -m polytess.cli run examples/demo.flow.json --var case=run42
./.venv/bin/python -m polytess.cli validate examples/demo.flow.json

# Tests
./.venv/bin/python -m pytest
```

## Bedienung (Studio)

| Aktion | Bedienung |
|---|---|
| Node erzeugen | Rechtsklick auf Canvas → *Add Node…* oder `Ctrl+Space` (durchsuchbares Menü) |
| Verbinden | Von einem Port (Kreis) zu einem anderen ziehen |
| Node bearbeiten | Node selektieren → **Inspector** (rechts): Actions/Conditions-Listen |
| Action hinzufügen | Inspector → *Add Instruction…* → Kategorie-Baum/Suche |
| Feld = Variable statt Wert | Dropdown-Button rechts neben dem Feld → z. B. *Graph Variable* |
| Reorder | Zeile am Drag-Handle ziehen (blauer Zielbalken) |
| Kontextmenü Zeile | Copy/Paste/Replace/Insert/Breakpoint/Disable/Help |
| Variablen | **Variables**-Dock (links): Graph- und Global-Scope, live während des Runs |
| Ausführen | `F5` / ▶ — laufende Nodes blau, Erfolg grün, Fehlschlag rot; Log unten |
| Stop | `Shift+F5` / ■ |
| Pan / Zoom / Fit | Mittlere Maustaste / Mausrad / `F` |
| Undo/Redo | `Ctrl+Z` / `Ctrl+Shift+Z` (Graph-Struktur) |
| Kopieren/Einfügen | `Ctrl+C` / `Ctrl+V` / `Ctrl+D` (Nodes inkl. interner Kanten) |
| Gruppen / Notizen | Rechtsklick → *Add Group* / *Add Sticky Note* (Doppelklick editiert) |
| Sub-Workflow | Sub-Workflow-Node, Doppelklick öffnet ihn als Tab |

## Konzepte

- **Instruction** (`async run(ctx)`): eine Action; Listen laufen sequentiell,
  mit relativem Programmzeiger (Skip/Restart/Stop).
- **Condition** (`run(ctx) -> bool`): mit If/Not-Vorzeichen; Listen mit AND/OR.
- **Branch**: Conditions + Instructions; BranchList = if/elif/else.
- **Event**: befeuert Trigger-Nodes (On Start, On Signal, On Timer, On File Changed).
- **PropertyGet/PropertySet**: jedes Feld ist Konstante ODER Variablen-Verweis
  (Graph/Global, List-Picks, Formatted String `{var}`, Env-Var, DateTime, …).
- **Graph**: Start/Exit/Actions/Conditions/Branch/Trigger/Sub-Workflow-Nodes;
  push-basierte Ausführung, mehrere Ausgangskanten laufen parallel;
  Conditions-Node verzweigt über *Success*/*Fail*-Ports.
- **Persistenz**: getaggtes JSON (`*.flow.json`), diff-freundlich, versionierbar.

## Eigene Domain-Actions (Simpack, Abaqus, …)

Vorlage: [plugins/simpack_template](plugins/simpack_template) — eigenes Paket
mit Entry-Point `polytess.plugins`; wird beim Start automatisch geladen.

**Ablage-Konvention: eine Klasse pro Datei:**
`instruction_<name>.py` / `condition_<name>.py` / `event_<name>.py`.
Alle so benannten Dateien im Plugin-Ordner (und in `polytess/library/…`)
werden beim Start **automatisch geladen** — neue Datei ablegen genügt,
keine Import-Zeile nötig. Dateien mit führendem `_` werden übersprungen
(z. B. die Kopiervorlage `_template.py`).

```python
@meta(title="Run Simpack Solver", category="Simpack/Run Simpack Solver",
      icon="terminal", color="red", description="…")
class RunSimpackSolver(Instruction):
    def __init__(self, model: str = ""):
        super().__init__()
        self.model = PropertyGetPath(model)      # Konstante ODER Variable

    @property
    def title(self):                             # dynamischer Listentitel
        return f"Simpack solve {self.model}"

    async def run(self, ctx):
        ...                                      # ctx.info/error, ctx.resolve_path,
                                                 # RunCommand-Muster für Subprozesse
```

```bash
./.venv/bin/pip install -e plugins/simpack_template
```

## Projektstruktur

```
polytess/
├── core/       # GUI-frei: Werte, Variablen, Properties, Instructions,
│               # Conditions, Events, Signals, Serialisierung
├── graph/      # GUI-frei: Graph-Modell, Node-Typen, asyncio-Processor
├── library/    # generische Actions/Conditions/Events (Files, Process, …)
├── gui/        # PySide6-Studio (Theme, Graph-Editor, Inspector, Log, …)
├── cli.py      # Headless-Runner
└── __main__.py # Studio-Start
plugins/        # Domain-Plugin-Vorlagen (Simpack/Abaqus)
examples/       # Beispiel-Workflows
tests/          # pytest (Core, Graph, Library, GUI-Smoke offscreen)
```

## Hinweise

- Undo/Redo deckt die Graph-Struktur ab (Nodes/Kanten/Positionen);
  Feld-Änderungen im Inspector sind direkt (kein Undo).
- Der Node-Body zeigt eine Live-Vorschau der Actions/Conditions;
  editiert wird im Inspector (Selektion genügt).
- `ValueNumber` ist `float` (double).

## Lizenz

[Business Source License 1.1](LICENSE.txt) — frei nutzbar, auch
kommerziell/intern, nur kein Weiterverkauf/Hosting als eigenes Produkt.
Wandelt sich am 2030-07-27 automatisch in Apache License 2.0.
