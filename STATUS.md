# polytess Studio — Projektstand

Produktname: **polytess Studio** (Winthir Studios). Frühere Namen:
gcflow → polyflow → polytess. Alte Installationen migrieren automatisch
(`~/.polyflow`/`~/.gcflow` → `~/.polytess`, `POLYFLOW_*`/`GCFLOW_*`-
Umgebungsvariablen und `import gcflow.*`/`polyflow.*` in User-Custom-
Dateien funktionieren über Aliase weiter).

Stand: 2026-07-16 · ~14.200 Zeilen Python · **71 pytest-Tests, alle grün**

## Was ist polytess?

Visual-Scripting-System (Variablen, Properties, Actions/Instructions,
Conditions, Events) mit Node-Graph-Editor — als Desktop-Studio (PySide6) und Headless-Runner
für Maschinenbau-Berechnungsworkflows: Verzeichnisse anlegen, Inputfiles
templaten, Simpack-/Abaqus-/FEMFAT-Läufe und DOEs auf HPC oder lokal,
Postprocessing, Loops.

Architektur-Grundsatz: **Kern strikt GUI-frei** (`polytess/core`, `polytess/graph`)
— Workflows laufen identisch im Studio und per CLI auf Rechenservern.
Persistenz als getaggtes JSON (`*.flow.json`, diff-freundlich).

## Registry (automatisch aus `@meta`-Dekoratoren)

| Baustein | Anzahl | Beispiele |
|---|---|---|
| Instructions | 65 | Create Folder, Render Template File, Run Command, Wait For File(s), Repeat Until, Loop List/Range/Table, Read CSV To Table, **Set Date** (now / now + Offset / spezifisch), **Set Vector3**, **Set Transform**, Submit HPC Job, **Run Job Pool**, Generate DOE Table (LHS), Convert Flex Body … |
| Conditions | 17 | Compare Number/String/Bool, File(s) Exist, File Contains Text, Table Row Count, HPC Token Valid … |
| Events | 7 | On Start, On Signal, On Timer, On File Changed, On File Appeared, **On Variable Changed** (beobachtet Graph-/Global-Variable oder -Liste, optional nur echte Wertänderungen; leerer Name = jede Variable), **On Date** (feuert bei Erreichen eines Zeitpunkts — fest oder aus Date-Variable, per Set Date verschiebbar) |
| Value-Typen | bool, number (double), integer, string, path, **date** (`YYYY-MM-DD HH:MM:SS`, Eingabe auch ISO/`TT.MM.JJJJ`), **vector3** (`x, y, z`), **transform** (pos + rot, `px,py,pz \| rx,ry,rz`), **table**, list | |

## Paket-Layout

```
polytess/
├── core/        # Werte, Variablen (Graph/Global), Property-System
│                # (Konstante ODER Variable pro Feld), InstructionList mit
│                # relativem Programmzeiger, Conditions/Branches, Events,
│                # Signals, Tabellen (tables.py), Referenzsuche (refs.py),
│                # Serialisierung ($type-JSON)
├── graph/       # Node-Typen (Start/Exit/Actions/Conditions/Branch/Trigger/
│                # Sub-Workflow), push-basierter asyncio-Processor mit
│                # Pause/Step/Breakpoint-Gate und Status-Events
├── library/     # generische Bausteine — EINE Klasse pro Datei
│                # (instruction_*.py / condition_*.py / event_*.py),
│                # Auto-Loader: Datei ablegen genügt
├── gui/         # PySide6-Studio: Graph-Editor (Bézier, Ports, Minimap,
│                # Groups, Sticky Notes, Undo/Redo, Copy/Paste), Inspector
│                # (Reorderable-Listen, Type-Selector mit Fuzzy-Suche, Property-
│                # Dropdowns, Template-Editor mit Variable-Insert+Preview),
│                # Blackboard (Variablen/Listen/Tabellen, Suche/Sort/Filter,
│                # Referenz-Dialog), Log-Dock, App-Icon
├── cli.py       # polytess run/validate — Headless (Batch/HPC)
└── __main__.py  # Studio-Start
plugins/
└── simpack_template/ # das einzige Plugin in git: Kopiervorlage für eigene
                     # Domain-Plugins (_template.py, RunSimpackSolver,
                     # RunAbaqusJob, SetSubvar, OdbExists). Eigene
                     # Domain-Plugins (HPC-Anbindung, Mesh-Werkzeuge, …)
                     # bleiben bewusst lokal — siehe .gitignore
examples/
└── demo.flow.json   # Mini-Demo
tests/               # pytest: Core, Graph, Library, Debugging,
                     # GUI-Smoke (offscreen); Plugin-abhängige Tests
                     # skippen automatisch, wenn das Plugin lokal fehlt
```

## Studio-Features (Auswahl)

- Graph-Editor: Node-Erstellung per durchsuchbarem Menü
  (Kategorien + Levenshtein-Suche + Favoriten), Success/Fail-Ports am
  Conditions-Node, Sub-Workflows als Tabs, Live-Highlighting beim Run
  (blau=läuft, grün=ok, rot=Fehler, **gelb=pausiert**).
- **Debugging**: Breakpoints an Nodes (Taste `B`, roter Punkt), Pause (F6) /
  Step Forward (F7) / Stop; Variablen im Blackboard live inspizierbar.
- **Blackboard**: Variablen mit Typ-Icons, Sortierung, Suche, Typ-Filter;
  Pfade mit Datei-Dialog; Listen inline aufklappbar (+/−, Inline-Edit);
  Tabellen mit Spreadsheet-Editor; Rechtsklick → **Find References**
  (read/write-Klassifizierung, Doppelklick springt zum Node).
- Inspector: Reorderable-Listen (Drag, Breakpoint, Disable,
  Duplicate, Kontextmenü), dynamische Titel („Set counter = 5"),
  Property-Dropdowns (Value | Graph Variable | Global Variable | Formatted …).
- Feld-Konventionen: Labels sind reiner Text (Unterfelder
  rücken nur das Label ein, Editoren bleiben in einer Spalte), Auswahlmenüs
  sind helle Felder mit ▼, Eingaben dunkle Felder; Variablen-/Listen-/
  Tabellen-Referenzen sind Objekt-Felder mit ⊙-Picker (Liste aller
  Kandidaten) und akzeptieren Drag & Drop aus dem Blackboard.
- Listen-/Tabellen-Felder sind Property-Slots: Quelle wählbar als
  direkte Listen-Eingabe (Inline-Editor) | Graph List/Table Variable |
  Global List/Table Variable — kein separates Scope-Feld mehr; darunter die
  eingerückte „Variable“-Zeile mit Name/Picker/Drag&Drop. Alte Graphen
  (scope + name als Strings) werden beim Laden automatisch migriert
  (`LEGACY_ALIASES` + String→Source-Migration in der Serialisierung).
- Instruction-/Condition-Titel sind neutral (weiß/hellgrau) — die thematische
  Farbe trägt nur das Icon; Nodes zeigen die farbigen Item-Icons auch in der
  Inline-Vorschau und das Node-Icon akzentgetönt in der Titelleiste.
- Dunkles Theme mit einheitlichen Farbtoken.
- Icons kommen aus einer Vector-Icon-Engine (werden für jede Zielgröße und
  jeden Bildschirm-DPR frisch gezeichnet — scharf statt skaliert); Blackboard-
  Tabelle und -Baum nutzen dieselbe Icongröße; Einzel-Kategorien im
  Type-Selector (z. B. „Nodes“) werden automatisch flach gezogen.

## Code-Editor & User-Library

Menü **Library → Code Editor** (Ctrl+E, Stift-Icon in der Toolbar) öffnet
einen Editor-Tab neben den Graphen: Python-Syntax-Highlighting,
Zeilennummern, Tab = 4 Spaces. Dateien liegen in
`~/.polytess/custom_library/` (Override `POLYTESS_CUSTOM_LIBRARY`) und werden
beim Start automatisch geladen — auch headless. „New ▾" erzeugt
Skeleton-Dateien für Instruction/Condition/Event; **Speichern (Ctrl+S)
prüft die Syntax** (Fehler mit Zeilennummer, Cursor springt hin),
**hot-reloadet das Modul und ersetzt die Registry-Einträge** — der neue
Baustein steht sofort ohne Neustart in den Add-Menüs (keine Duplikate;
kaputte Dateien blockieren den Start nicht). Bei Instruction-Fehlern
landet jetzt zusätzlich der volle Python-Traceback als Debug-Eintrag im
Log-Dock. Code-Zeilen-Haltepunkte: bewusst noch nicht (siehe Diskussion —
debugpy-Attach bzw. Worker-Thread-Debugger als Ausbaustufe).

## Assistant-Provider (Anthropic | GitHub Copilot)

Beide Assistenten (Code-Editor-Chat + Flow-Assistent) laufen wahlweise
über die **Claude API** (Default, API-Key) oder über **GitHub Copilot**
(`assistant_provider` in den Settings): Copilot nutzt das offizielle
`github-copilot-sdk` (bündelt die Copilot-CLI) und das Copilot-Abo des
Users — Login einmalig per `copilot login`, auf **GitHub Enterprise**
per `copilot login --host https://<tenant>.ghe.com`; der in den
Settings hinterlegte GitHub-Host wird als `COPILOT_GH_HOST`/`GH_HOST`
exportiert und routet alle Anfragen auf den Tenant. Optional GitHub-
Token statt Login, Copilot-Modell wählbar. System-Prompts werden per
`system_message: replace` gesetzt, Streaming über
`AssistantMessageDeltaData`, Tool-Ausführung wird verweigert (reiner
Chat). Bridge: `polytess/gui/copilot_provider.py`; Install-Extra
`polytess[ai-copilot]`.

## Claude-Coding-Assistent im Code-Editor

Chat-Panel neben dem Editor (Sprechblasen-Icon in der Editor-Toolbar;
`pip install polytess[ai]`). Nutzt die Claude API mit dem eigenen API-Key
(Settings → Assistant oder `ANTHROPIC_API_KEY`; Modell einstellbar,
Default `claude-opus-4-8`). Der System-Prompt enthält den **kompletten
Baustein-Contract** (@meta, Property-System, Context-API, async run,
Events/persistent, Templates) und eine **live erzeugte Registry-Übersicht
aller vorhandenen Instructions/Conditions/Events/Sources** — der Assistent
weiß also genau, wie man Bausteine schreibt und was es schon gibt (und
rät zur Wiederverwendung). Die aktuell geöffnete Datei geht als Kontext
mit. Antworten streamen (QThread, GUI bleibt bedienbar, Stop-Button);
Prompt-Caching für den System-Prompt; „Insert" übernimmt den letzten
```python-Block direkt in den Editor.

## Flow-Assistent (Claude baut Workflows)

`Library → Flow Assistant` (Ctrl+Shift+F, Dock rechts): Prozess
beschreiben → der Agent entwirft den Flow in einem vereinfachten
JSON-Schema (`polytess/graph/flow_builder.py`, Doku im Modul). „Insert
flow“ validiert gegen die echte Registry und öffnet den gebauten
Graphen als neues Dokument (Auto-Layout per BFS, zyklenfest).
Fehlende Bausteine werden gemeldet; ein fertiger Prompt für den
Code-Assistenten liegt dann auf dem Stift-Knopf (Zwischenablage) —
gleiche Klassennamen ⇒ der Flow findet die Bausteine nach dem
Erstellen sofort. Param-Bindungen im Schema: Konstanten,
{"var"/"global": name} (auch Listen/Tabellen), {"template": "…"},
{"target": true}; set:-Felder nehmen den Variablennamen.

Beide Assistenten-Chats rendern über `polytess/gui/chat_view.py`:
Frage/Antwort als farblich getrennte Bubbles, Code in dunklen Boxen
mit Python-/JSON-Highlighting, 14px/großzügige Abstände.

## Flow-Lifecycle (Branches & Revisionen)

Jeder Flow trägt einen `lineage`-Block (flow_id der Familie, branch,
revision, parent) — der Bezug steckt in der Datei selbst, kein Git
nötig (`polytess/graph/lineage.py`). Studio-Menü Graph:
**Create Branch…** (Ctrl+B, legt `<name>@<branch>.flow.json` an),
**Compare with Parent** (Ctrl+D, struktureller Diff: Nodes/Parameter/
Kanten/Variablen — GUID-basiert, da Branches die Node-GUIDs behalten),
**Promote to Parent…** (ersetzt den Parent, alter Stand wandert als
Snapshot in `.history/<flow_id>/`), **Flow History…** (alle Snapshots,
Doppelklick öffnet). Jeder Studio-Save erhöht die Revision und legt
einen Snapshot ab; Runs werden im Log mit `branch·rev` getaggt.
Alte Dateien ohne lineage laden unverändert (frische Identität).

## Flow-Dokumentation (PDF-Export)

`File → Export Documentation…` (Studio) bzw. `polytess.cli doc
flow.json` erzeugt eine verlinkte PDF-Doku im Stil von
winthirstudios.com/polytess.html (`polytess/graph/flow_doc.py`,
reportlab): klickbares Vektor-Diagramm (Node → Kapitel), verlinktes
Inhaltsverzeichnis, nummerierte Node-Kapitel mit Payload, Parametern
und quer-verlinkten Verbindungen, Blackboard-Anhang. Schriften Outfit/
Bricolage Grotesque liegen gebündelt unter `polytess/assets/fonts`
(SIL OFL; Helvetica-Fallback).

## Mesh-Streuungen (Plugin polytess_meshvary — lokal, nicht in git)

Fertigungsstreuungen auf Abaqus-Volumennetze — reines Mesh-Morphing für
Monte-Carlo-Studien. Eigenes, eigenständig entwickeltes Werkzeug
(Zylinderfit, RBF-Morphing, Porositätsfelder, Netzqualitätsprüfung);
bleibt wie alle Domain-Plugins außer `simpack_template` lokal (siehe
`.gitignore`) und wird daher hier nicht im Detail beschrieben — Details
lokal in `plugins/polytess_meshvary/` selbst.

## Solver-Profile (Settings → Solvers)

MKS (Simpack) und FEM (Abaqus) sind als Profile konfigurierbar:
Solver-Kommando, „Run via SSH" + Host, **Remote-Shell-Dialekt**
(tcsh | bash | cmd für Windows-Remotes — die Login-Shell des Ziels
bestimmt die Kapselung: setenv/export/set + cd bzw. cd /d) und ein
**Pfad-Mapping** (lokales ↔ remotes Prefix des gemeinsamen Storage,
inkl. Separator-Konvertierung) für Cross-OS-Rechnen (Windows→Linux,
Windows→Windows, …). API: `run_solver(ctx, "fem"|"mks", …)` in
`polytess/core/shell.py`; Baustein **Run Solver** (Process/…) nutzt
die Profile, Solver-Felder mit leerem Kommando (Abaqus Syntax Check,
Generate FBI File) fallen auf das Profil zurück. Hostname-Kurzschluss
wie beim Command-Server; dieser bleibt Fallback für alle übrigen
Konsolenbefehle.

## Globale Einstellungen & Command-Server (SSH)

`~/.polytess/settings.json` (Singleton `polytess/core/app_settings.py`, auch
headless), editierbar über das Zahnrad in der Toolbar (Settings-Dialog).
Konsolen-Kommandos (Run Command, Abaqus Syntax Check, Generate FBI File)
laufen als `ssh <command_server> 'setenv … ; cd "…" && kommando'` —
tcsh-sicher, damit von Windows aus (mitgelieferter OpenSSH-Client) alle
Linux-Tools nutzbar sind. Default: aus/leer (lokale Ausführung); läuft
polytess auf dem Server selbst (Hostname-Erkennung), wird lokal ausgeführt;
Run Command hat zusätzlich „Force Local". SSH-Optionen (BatchMode,
ConnectTimeout) einstellbar. Voraussetzung: SSH-Key-Authentifizierung.
Der Settings-Dialog hat drei Tabs: **Command Server**, **Assistant**
(API-Key, Modell) und **Reports** — Firmen-Defaults für spätere Reports/
Plots: Schriftart + Größe (QFontComboBox) und drei Farben (Primary/
Secondary/Accent, Farbwähler); Instructions lesen sie über
`AppSettings.instance().get("report_font" / "report_color_primary" / …)`.

## otools-Anbindung (lokal, nicht in git)

Analyse + Umsetzungsplan lokal in `PLAN_OTOOLS.md` (Status: umgesetzt,
im HPC-Plugin `plugins/polytess_hpc/`). Vendor-Pakete werden **per Import
gewrappt**, Suchpfade über Env-Variablen (`POLYTESS_OTOOLS_PATH`,
`POLYTESS_SUBMIT_JOB_PATH`, `POLYTESS_HPC_COMMAND`). Alle Cluster-
Bausteine haben einen **Dry-Run-Modus** (Fake-Ergebnisdateien) — die
kompletten Workflows sind ohne Cluster/Lizenzen testbar.

## CI/CD & Executables

GitHub Actions: `tests.yml` (Linux-Suite bei jedem Push, pip-Cache,
Concurrency-Abbruch — bleibt im Free Tier) und `release.yml`
(Tag `v*` → Tests → **Windows-/Linux-Desktop-Executable** (PyInstaller,
plain-source Bundle, GUI `polytess` + Headless `polytess-cli`, Zip) +
**Source-Tarball** (reines Python, für Server/CLI-Einsatz ohne Build-
Schritt) → GitHub-Release. Release-Artefakte enthalten nie
custom_instructions oder Lizenzen (`--no-custom-library`). Lokal:
`python build_exe.py` baut das Executable der eigenen Plattform;
Lizenz/`plugins/`/`custom_library/` werden im Frozen-Modus auch neben
der EXE gefunden (install_roots).

## Lizenzierung (Business Source License 1.1)

polytess steht unter der **Business Source License 1.1** (`LICENSE.txt`):
jede Nutzung erlaubt, auch intern-kommerziell — nur Weiterverkauf/
Vertrieb/Hosting als eigenes Produkt braucht eine gesonderte Vereinbarung
mit Winthir Studios. Wandelt sich automatisch am 2030-07-27 in Apache
License 2.0. Header in allen polytess-/Plugin-Dateien verweisen darauf.

**Optionale kommerzielle Lizenz** (`polytess/core/licensing.py`):
Ed25519-signierte Lizenzdateien, offline verifiziert gegen den
eingebetteten Public Key — für Kunden, die Rechte über die BUSL hinaus
brauchen (z. B. Vertrieb/Hosting). **Blockiert nicht den Start** — die
Software läuft vollständig ohne jede Lizenzdatei (BUSL-Grundsatz „jeder
soll sie nutzen können"); `Help → Commercial License…` zeigt den Status
und importiert eine `.lic`-Datei. Payload: Lizenznehmer, Ablaufdatum
(leer = unbefristet), Hostname-Muster (fnmatch, leer = jeder Rechner).
Suchreihenfolge: `$POLYTESS_LICENSE` → `~/.polytess/license.lic` →
`license.lic` neben der Installation. Lizenzen ausstellen:
`tools/generate_license.py` mit dem **privaten** Signierschlüssel
(`~/.polytess/license_signing.key` — NICHT im Repo; Verlust = neue Keys
in licensing.py einbetten). Tests nutzen ein ephemeres Schlüsselpaar
aus `conftest.py`.

Distribution ist reiner Python-Quelltext (kein Kompilierschritt) —
PyInstaller bündelt ihn für die Desktop-Executables, der Source-Tarball
enthält ihn direkt.

## Vendor-Trennung: Custom Instructions

Alle von einem Kunden-/Vendor-Toolset abgeleiteten Bausteine bleiben aus
dem auslieferbaren Paket draußen und leben in der **User-Custom-Library**
(Additional Use Grant in `LICENSE.txt`: eigene Custom-Bausteine gehören
dem Nutzer). Versionierter Master lokal in `custom_instructions/`
(nicht in git — siehe `.gitignore`); geladene Kopien:
`~/.polytess/custom_library/` (dorthin synchronisieren nach Änderungen).

Das Plugin `polytess_doe` (lokal, nicht in git) enthält nur die
nativen, generischen DOE-Bausteine (Generate DOE Table, Generate Full
Factorial) — keine Vendor-spezifischen Wrapper. Tests laden die
Custom-Bausteine über `POLYTESS_CUSTOM_LIBRARY` → `custom_instructions/`
(conftest) und skippen automatisch, wenn diese lokal fehlen; gespeicherte
Graphen laden unverändert, da die `$type`-Namen gleich bleiben.

## Bekannte Grenzen

- Undo/Redo deckt die Graph-Struktur ab (Nodes/Kanten/Positionen), nicht
  einzelne Inspector-Feldänderungen.
- Node-Body ist Live-Vorschau; editiert wird im Inspector.
- `RunJobPool` im hpc-Modus nutzt Ergebnisdatei-Polling; der CLI-
  qstat-Status fließt noch nicht in die Zustände ein.
- E-Mail nur über System-`sendmail` (Linux/Unix).
- Pause wirkt zwischen Nodes (laufende Actions laufen zu Ende).
