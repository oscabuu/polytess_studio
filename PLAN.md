# Portierungsplan: Game Creator 2 + State Machine 2 → Python „Workflow Studio" für Maschinenbau

Stand: 2026-07-16 · Basis-Analyse: GC2 Core (`Assets/Plugins/GameCreator/Packages/Core`) und State Machine 2 (`Assets/Plugins/NinjutsuGames/Packages/StateMachine`)

> **Status: ALLE 9 PHASEN UMGESETZT** (2026-07-16). Paket `polytess/`, 38 Tests grün
> (Core, Graph, Library, GUI-Smoke offscreen), Demo unter `examples/demo.flow.json`,
> Plugin-Vorlage unter `plugins/simpack_template/`. Bedienung & Details: `README.md`.

---

## 1. Entscheidung: Native Python-GUI (PySide6/Qt) statt Webanwendung

**Empfehlung: PySide6 (Qt for Python), Desktop-Anwendung.**

Begründung:

| Kriterium | Native (PySide6) | Web (Browser + Server) |
|---|---|---|
| Node-Editor (Pan/Zoom, Bézier-Kanten, Drag&Drop) | `QGraphicsView/Scene` ist genau dafür gebaut; bewährte Vorbilder: NodeGraphQt, Ryven, QtNodes | Nur mit JS-Libs (ReactFlow/LiteGraph) → zweite Codebasis in JS/TS |
| Zugriff auf Simpack/Abaqus, Dateisystem, Lizenz-Umgebungen, `subprocess` | Direkt, ohne Umwege | Braucht zwingend einen lokalen Backend-Server; Browser-Sandbox blockiert Dateizugriff |
| Lange Rechenläufe / DOEs lokal starten und überwachen | Direkt (asyncio + subprocess) | Websocket-Infrastruktur nötig |
| Docking-Layout (Inspector, Log, Blackboard) | `QDockWidget` gratis | selbst bauen |
| Dunkles GC2-Theme | QSS (CSS-ähnlich) — die GC2-Farbtoken lassen sich 1:1 übernehmen | ebenfalls gut |
| Deployment | `pip install` / PyInstaller-EXE, kein Server | Server + Browser nötig |
| Ein Ingenieur, ein Rechner (typischer Anwendungsfall) | ✔ passt | Vorteil erst bei Multi-User/Remote |

**Absicherung:** Der Kern (Datenmodell + Ausführungs-Engine) wird strikt GUI-frei gebaut und Graphen als JSON gespeichert. Damit bleibt beides später möglich: ein **Headless-CLI-Runner** (Workflows auf Rechenservern/HPC ohne GUI ausführen — für DOEs wichtig!) und, falls je gewünscht, ein Web-Frontend auf denselben Kern.

Lizenz: PySide6 ist LGPL (kommerziell nutzbar ohne Lizenzkosten, im Gegensatz zu PyQt/GPL).

---

## 2. Architektur-Landkarte (Unity → Python)

Zentrale Idee von GC2, die wir übernehmen: **Polymorphe, typ-getaggte Objekte + Metadaten an der Klasse + „Property"-Felder, die transparent Konstante ODER Variablen-Verweis sind.**

| Game Creator 2 / SM2 | Python-Umsetzung |
|---|---|
| `TPolymorphicItem` (Basis von allem: enabled, breakpoint, Title) | `PolymorphicItem`-Basisklasse (`is_enabled`, `breakpoint`, `title`-Property) |
| Attribute `[Title] [Category("A/B/C")] [Description] [Keywords] [Parameter] [Image(Icon, Farbe)] [Version]` | Klassen-Dekorator `@meta(title=..., category="A/B/C", icon=..., color=..., keywords=[...], description=...)` → speist Registry, Auswahlmenü & Suchindex |
| `[SerializeReference]` (polymorphe Serialisierung) | Getaggtes JSON: `{"$type": "modul.Klasse", ...felder}` + Typ-Registry |
| `Args` (Self/Target + Cache) | `Context` (self/target-Objekt, Variablen-Zugriff, Logger, Abbruch-Token, Arbeitsverzeichnis) |
| `TValue` (`ValueString`, `ValueNumber`=double, `ValueBool`, …) + TypeID-Registry | `Value`-Klassen mit `type_id`-Registry; zusätzlich maschinenbau-relevant: `ValuePath`, `ValueStringList`, `ValueTable/DataFrame` |
| `NameVariable` / `IndexVariable`; `LocalNameVariables` (am Objekt) / `GlobalNameVariables` (Asset + Singleton-Manager) | `NameVariable`/`IndexVariable`; **Graph-Variablen** (lokal pro Graph, wie SM2s `StateMachineAsset : TGlobalVariables`) + **globale Variablen** (App-weit, Projekt-Datei); Change-Events fürs Blackboard-Panel |
| Property-System: `PropertyGetString` → `source: PropertyTypeGetString` (Subklassen: `GetStringString` Konstante, `GetStringGlobalName` Variable, …); `PropertySet*` symmetrisch | `PropertyGet[T]` / `PropertySet[T]` mit austauschbarem `source`-Objekt; Sources: Konstante, Graph-Variable, globale Variable, List-Pick (First/Last/Index/Random), berechnet (DateTime, Env-Var, Pfad-Join, …) |
| `Instruction` (`async Run(args)`, `NextInstruction`-Zeiger, Helfer `Time/While/Until/NextFrame`) | `Instruction` mit `async def run(ctx)`; `InstructionResult` (Default/+n/Stop) für Sprünge; Wait = `await asyncio.sleep` mit Cancel-Check |
| `InstructionList.Run` (while-Schleife, relativer Programmzeiger, `RunningIndex`, Cancel-Kette, Events Start/End/RunInstruction) | identisch als `async def run(ctx)`; Events für Live-Highlighting im GUI |
| `Condition` (`m_Sign` If/Not, `Check`), `ConditionList` (And/Or, Kurzschluss), `Branch`/`BranchList` (if/elif/else) | 1:1 übernehmen |
| `Event` (Hook-Methoden) + `Trigger` (Host reicht Lifecycle durch) + `Signals` (globales Pub/Sub) | `Event`-Basisklasse (`on_start`, `on_signal`, `on_timer`, `on_file_changed`, …) + `Signals`-Pub/Sub `{name: [receiver]}` |
| **SM2** `StateMachineAsset` (nodes[SerializeReference], edges per GUID, groups, stickyNotes, pan/zoom persistiert) | `Graph`-Dataclass → JSON-Datei (`.flow.json`); GUIDs als `uuid4`-Strings |
| `BaseNode` (GUID, custom_name, position+size, enabled, expanded; Ports per Deklaration) | `Node`-Basis + deklarative Port-Liste pro Typ `(name, direction, vertical, allow_multiple)` |
| Node-Typen: Start (violett), Exit (violett), Actions (blau), Conditions (grün, 2 Outputs success/fail), Branch (grün), Trigger (rot), Sub-StateMachine (blau), Group, StickyNote | identisch, gleiche Farbcodierung |
| Ports = reine Flow-Anschlüsse (kein Datenfluss durch Kanten!) | genauso — das PushData/TypeAdapter-System von NodeGraphProcessor wird bewusst NICHT portiert |
| `StateMachineGraphProcessor`: push-basiert, kein compute-order; Start-/Trigger-Nodes stoßen an, jeder Node ruft nach Abschluss seiner Payload `RunChildNodes` (→ implizite Parallelität bei mehreren Ausgangskanten); Conditions leiten nur an success- ODER fail-Port weiter | `GraphProcessor` auf asyncio: pro Node ein Task; mehrere Ausgangskanten = `asyncio.gather` der Nachfolger; Running-Status pro Node für Live-Highlighting (laufend=blau, success=grün, fail=rot) |
| Running-Status `IsContextRunning` + Events → Editor-Highlight | Node-Status-Events → GUI-Highlight über Qt-Signals |

---

## 3. GUI-Konzept (Nachbau von GC2/SM2-Look&Feel)

### 3.1 Hauptfenster
- **Menüleiste** (File: New/Open/Save/Recent · Edit: Undo/Redo/Copy/Paste · Graph: Run/Stop/Validate · View: Panels · Help)
- **Toolbar**: Run ▶ / Stop ■ / Save / Zoom-Fit / Minimap-Toggle (wie SM2s `CustomToolbarView`)
- **Zentral**: Graph-Editor (Tabs für mehrere geöffnete Graphen)
- **Rechts (Dock)**: **Inspector** — zeigt den selektierten Node
- **Links (Dock)**: **Blackboard/Variablen** (Graph- + globale Variablen, wie SM2s Blackboard) und Projekt-/Dateibaum
- **Unten (Dock)**: **Log-Panel** (Level-Filter Debug/Info/Warn/Error, pro Workflow-Lauf, klickbare Node-Referenzen)
- **Statusleiste**: Ausführungsstatus, aktueller Graph-Pfad

### 3.2 Graph-Editor (QGraphicsScene/View)
- Grid-Hintergrund, Pan (mittlere/rechte Maus), Zoom (Mausrad, Grenzen wie SM2 `SetupZoom`), Rubber-Band-Selektion
- **Nodes**: Titelzeile mit Icon + Name (umbenennbar) + Zähler (Anzahl Actions/Conditions) + Expand-Chevron; aufgeklappt zeigt der Node seine Instruction-/Condition-Liste inline (wie SM2 `controlsContainer`); Akzentfarbe pro Typ
- **Ports**: horizontal (In links/Out rechts) und vertikal (Trigger-Fluss oben/unten) — wie SM2
- **Kanten**: Bézier; Conditions-Node mit zwei Ausgängen „Success"/„Fail"
- **Node-Erzeugung**: Rechtsklick/Space → durchsuchbares Menü (wie SM2 `CreateNodeMenuWindow`)
- Start- und Exit-Node automatisch vorhanden, nicht löschbar
- Minimap, Groups (farbige Rahmen), Sticky Notes
- Live-Highlighting laufender Nodes im Run-Modus

### 3.3 Inspector (Kern-Nachbau der GC2-Listen)
- Header: Icon + Node-Name + Enable/Lock/Play-Buttons
- **Reorderable InstructionList/ConditionList** exakt nach GC2 (`TPolymorphicItemTool`):
  - 22px-Zeilen: Drag-Handle · Icon · **dynamischer Titel** (Format-String aus Feldwerten, z. B. „Set counter = 5") · Breakpoint · Disable · Duplicate · Delete
  - Klick auf Titel = Expand/Collapse des Body mit den Feldern; disabled = 25 % Opacity
  - Drag&Drop-Reorder mit blauem Zielbalken; Rechtsklick-Menü (Copy/Paste/Replace/Insert Above/Below/Breakpoint/Disable/Collapse/Help)
  - Fuß: „Add Instruction…"-Button
- **Type-Selector-Popup** (GC2 `TypeSelectorFancyPopup`): Suchfeld oben (Fuzzy/Levenshtein über Title+Category+Keywords), Kategorie-Baum als seitlich gleitende Seiten (24px-Zeilen, Icon+Label+Chevron), Beschreibungs-Footer aus `description`
- **Property-Felder**: Label links + Dropdown-Button rechts (zeigt gewählten Source-Typ: „Value" / „Graph Variable" / „Global Variable" / …), öffnet denselben Type-Selector; darunter die Unterfelder des gewählten Source (eingerückt 10px)
- **Transitions-Liste**: ausgehende Verbindungen des Nodes, umsortier-/löschbar (wie SM2 `NodeInspectorEditor`)

### 3.4 Theme (Token 1:1 aus `CommonColors_Dark.uss` / `ColorTheme.cs`)
```
bg-default #383838 · bg-dark #333333 · bg-darker #2a2a2a · bg-darkest #191919
bg-light #3f3f3f · border-default #1a1a1a · border-hover #656565
Akzent/Fokus #3d7ad9 · Accept #519932 · Warning #b0963a · Error #b03a3a
List-Head #404040 (hover #545454, expanded #2a2a2a, running #191919)
Akzentfarben: Rot #e9754c · Grün #c2f771 · Blau #87d8f6 · Gelb #f1c437
              Violett #a692e9 · Pink #d790d4 · Teal #a2f7e4
Maße: Zeile 22px · Icon 16px · Border 1px · Radius 3px (nur außen) · Indent 10px
```
Icons: monochrome SVGs (Qt einfärbbar), Zuordnung per `@meta(icon=..., color=...)`.

---

## 4. Projektstruktur

```
Assets/Python/
├── pyproject.toml               # Paket „polytess", Python ≥3.11, deps: PySide6, qasync
├── PLAN.md                      # dieses Dokument
├── polytess/
│   ├── core/                    # GUI-FREI — auch headless nutzbar
│   │   ├── metadata.py          # @meta-Dekorator, Kategorie-Baum, Suchindex (Fuzzy)
│   │   ├── registry.py          # Typ-Registry (Serialisierung + Auswahlmenüs)
│   │   ├── polymorphic.py       # PolymorphicItem
│   │   ├── context.py           # Context (≙ Args)
│   │   ├── values.py            # Value-Typen + type_id-Registry
│   │   ├── variables.py         # Name-/Index-Variablen, Graph-/Global-Scope
│   │   ├── properties.py        # PropertyGet/Set + Sources (Konstante/Variable/…)
│   │   ├── instructions.py      # Instruction, InstructionList, InstructionResult
│   │   ├── conditions.py        # Condition, ConditionList, Branch, BranchList
│   │   ├── events.py            # Event-Basisklasse + Trigger-Hooks
│   │   ├── signals.py           # Pub/Sub
│   │   └── serialization.py     # getaggtes JSON (dump/load über Registry)
│   ├── graph/                   # GUI-FREI
│   │   ├── model.py             # Graph, Node, Edge, PortSpec, Group, StickyNote
│   │   ├── nodes.py             # Start, Exit, Actions, Conditions, Branch, Trigger, SubGraph
│   │   └── processor.py         # asyncio-Ausführung (push-basiert), Node-Status-Events
│   ├── library/                 # generische Instructions/Conditions/Events
│   │   ├── instructions/        # debug, flow, variables, files, process
│   │   ├── conditions/          # compare, files
│   │   └── events/              # on_start, on_signal, on_timer, on_file_changed
│   ├── gui/
│   │   ├── theme.py             # Farb-/Maß-Token + QSS
│   │   ├── icons.py             # SVG-Icons, einfärbbar
│   │   ├── main_window.py       # Menü, Toolbar, Docks, Tabs
│   │   ├── graph/               # Scene, View, NodeItem, EdgeItem, Minimap, CreateNodeMenu
│   │   ├── inspector/           # NodeInspector, PolymorphicListWidget, PropertyField
│   │   ├── type_selector/       # Such-Popup mit Kategorie-Seiten
│   │   ├── blackboard/          # Variablen-Panel
│   │   └── log/                 # Log-Dock
│   ├── cli.py                   # headless: `polytess run workflow.flow.json`
│   └── __main__.py              # GUI-Start
├── plugins/                     # später: polytess_simpack/, polytess_abaqus/ (Entry-Points)
└── tests/
```

**Plugin-Mechanismus für Simpack/Abaqus:** eigene Pakete registrieren ihre Instruction-/Condition-Klassen über Python-Entry-Points (`polytess.plugins`); der @meta-Dekorator sortiert sie automatisch in Kategorie-Baum + Suchindex ein (z. B. `category="Simpack/Run Simulation"`). Kein Kern-Code muss angefasst werden.

---

## 5. Generische Start-Bibliothek (wird mitgeliefert)

**Instructions** (Kategorie → Klasse):
- `Debug/Log Message`, `Debug/Log Variable`
- `Flow/Wait Seconds`, `Flow/Emit Signal`, `Flow/Stop`, `Flow/Run Sub-Workflow`
- `Variables/Set Number`, `Set String`, `Set Bool`, `Set Path`, `Add To List`, `Clear List`, `Loop List` (ruft pro Element eine Instruction-Liste mit Element als Target)
- `Files/Create Folder (if missing)`, `Delete Folder/File`, `Copy File(s)`, `Move File`, `Write Text File`, `Read Text File → Variable`, `Find Files (glob) → List`, `Replace In File` (Templating für Inputfiles!)
- `Process/Run Command` (Programm + Argumente + Arbeitsverzeichnis + Env; wartet optional, Exit-Code → Variable, stdout → Log) — **die Basis für Simpack-/Abaqus-Aufrufe**
- `Process/Run Python Script`

**Conditions**:
- `Math/Compare Number` (=, ≠, <, ≤, >, ≥), `Compare String`, `Compare Bool`
- `Files/File Exists`, `Folder Exists`, `File Is Newer Than`
- `Lists/List Is Empty`, `List Count Compare`
- `Logic/Always True/False`

**Events**: `On Start` (Run-Button), `On Signal`, `On Timer/Schedule`, `On File Changed` (watchdog)

---

## 6. Umsetzungsphasen

| Phase | Inhalt | Ergebnis/Test |
|---|---|---|
| **1. Core-Framework** | polymorphic, metadata/@meta, registry, values, variables, properties, instructions, conditions, events, signals, serialization; pytest-Suite | Instruction-Listen headless per Skript ausführbar; JSON round-trip |
| **2. Graph + Processor** | Graph-Modell, Node-Typen, Edges, asyncio-Processor mit Status-Events; `cli.py` | `polytess run beispiel.flow.json` führt einen handgeschriebenen Workflow aus |
| **3. Basis-Bibliothek** | generische Instructions/Conditions/Events aus Kap. 5 | Demo-Workflow: Ordner anlegen → Datei templaten → Prozess starten → Bedingung prüfen |
| **4. GUI-Shell** | Theme/QSS, MainWindow mit Menü/Toolbar/Docks, Log-Panel | leeres, dunkles Studio startet |
| **5. Graph-Editor** | Scene/View (Grid, Pan, Zoom), NodeItems mit Ports/Farben, Bézier-Edges, Create-Node-Menü, Selektion, Speichern/Laden, Undo/Redo (QUndoStack) | Graphen visuell bauen und speichern |
| **6. Inspector** | PolymorphicListWidget (Reorder/Expand/Disable/Breakpoint/Kontextmenü), Type-Selector-Popup mit Fuzzy-Suche, PropertyField-Widgets, dynamische Titel, Transitions-Liste | Nodes vollständig im Inspector editierbar; Liste auch inline im Node |
| **7. Run-Integration** | qasync-Loop, Run/Stop aus GUI, Live-Node-Highlighting (blau/grün/rot), Log-Streaming, Blackboard mit Live-Variablenwerten | Workflow im Studio starten und beobachten |
| **8. Komfort** | Minimap, Groups, Sticky Notes, Copy/Paste von Nodes, Sub-Workflow-Nodes (Doppelklick öffnet Tab), Favoriten im Type-Selector | Feature-Parität mit SM2-Editor |
| **9. Domain-Plugins** | (durch dich) Simpack/Abaqus/DOE-Instructions nach Vorlage der generischen Klassen; Plugin-Doku + Template | eigene Berechnungsworkflows |

Phasen 1–3 sind bewusst GUI-frei → früh testbar, und der Headless-Runner für Rechenserver fällt gratis ab.

---

## 7. Bewusste Abweichungen von der Unity-Vorlage

1. **Kein PushData/TypeAdapter durch Kanten** — SM2 nutzt Ports nur als Flow-Anschlüsse; wir auch.
2. **asyncio statt Unity-Frames** — `Time()/NextFrame()` werden `asyncio.sleep`; Cancel über Task-Cancellation statt `ICancellable`-Kette (Verhalten identisch).
3. **„Local Variables" heißen „Graph Variables"** — ohne GameObjects ist der natürliche lokale Scope der Graph (SM2 macht das genauso: `StateMachineAsset : TGlobalVariables`).
4. **`Context.self/target` bleiben** (für Loop-List u. Ä. nützlich), zeigen aber auf beliebige Python-Objekte/Variablen-Container statt GameObjects.
5. **Zusätzliche Value-Typen** für Maschinenbau: `ValuePath`, `ValueStringList`, später `ValueTable`.
6. **Node-Doppelklick öffnet Sub-Workflow als Tab** (statt Unity-Asset-Ping).
