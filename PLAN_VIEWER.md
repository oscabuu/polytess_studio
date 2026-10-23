# Plan: polytess Viewer — Flows ausführen ohne den Flow zu sehen

Stand: 2026-09-23 · Basis: polytess Studio v1.15.0 (Blackboard mit Status-Tags,
`runtime_written_names`, `GraphProcessor`, CLI `polytess run --var`)

> **Status: Phase 1 UMGESETZT** (2026-09-23, v1.16.0): `form`-Metadaten an
> Variablen/Listen, Blackboard-Dialog *Viewer Settings…*,
> `polytess/graph/inputs.py` (InputSpec, Validierung, apply, Vars-Datei),
> CLI `polytess inputs` und `run --vars-file`, Assistant-Schema. Metadaten
> liegen in einem `form`-Dict statt in Einzelfeldern (Abschnitt 3).
> **2026-10-23, v1.18.0: Phasen 2–5 UMGESETZT** — `polytess/viewer/`
> (Start, Formular, Board, Dashboard, Celebrations), `graph/board.py`,
> CLI `board`, Demo `examples/viewer/`, Handbuchkapitel 10. Offen aus
> Phase 5/6: Fertig-Prüfung (ConditionList) im Studio, Board-Vorschau im
> Studio, kritischer Pfad im Dashboard, CSV/PDF-Export der Statistik,
> "Problem melden", Viewer-Lizenz-Edition, Dateityp-Zuordnung der Exe.

---

## 1. Zielbild in einem Satz

Ein Experte baut im Studio einen Flow; ein Anwender ohne Flow-Kenntnisse
öffnet ihn im **Viewer**, sieht nur ein Formular mit den Eingabewerten,
füllt sie aus, drückt *Start*, verfolgt den Fortschritt und bekommt am
Ende Ergebnis und Protokoll — ohne Canvas, ohne Knoten, ohne
Laufzeitvariablen.

## 2. Wer arbeitet wie damit

**Anwender (Zielgruppe des Viewers)**
- Bekommt vom Experten eine `.flow.json` (oder einen Ordner mit Flow +
  Vorlagen) und startet den Viewer per Doppelklick auf die Datei bzw. über
  *Zuletzt verwendet*.
- Sieht ein Formular: nur die Eingabewerte, in der Gruppierung und
  Reihenfolge, die der Experte im Blackboard angelegt hat, mit Klartext-
  Beschreibung pro Feld. Pflichtfelder sind markiert, Pfade haben einen
  Auswahl-Button, Zahlen ihre Grenzen.
- Typischer Ablauf: Formular ausfüllen (oft nur 2–3 Werte ändern, der
  Rest bleibt vom letzten Lauf) → *Prüfen* zeigt fehlende/ungültige Felder
  → *Start* → Fortschrittsansicht mit Phasen und Log → Ergebnis-Seite
  (Erfolg/Fehler, Ausgabewerte, Arbeitsordner öffnen, Protokoll sichern).
- Führt denselben Flow oft mit leicht anderen Werten aus → braucht
  **gespeicherte Eingabesätze** ("Presets") und *Letzte Werte übernehmen*.
- Läuft manchmal lange (HPC-Warten) → Fenster darf minimiert werden,
  Abbrechen muss sauber funktionieren, Status bleibt sichtbar.
- Darf den Flow nie verändern und sieht auch keine Möglichkeit dazu.

**Experte (arbeitet weiter im Studio)**
- Entscheidet pro Variable, ob sie im Viewer erscheint, und hinterlegt
  Beschriftung, Beschreibung, Pflicht, Grenzen, Auswahllisten.
- Nutzt Gruppen für die Formular-Abschnitte und die Reihenfolge.
- Prüft mit **Vorschau im Viewer** direkt aus dem Studio, wie das Formular
  aussieht, und markiert die Variablen als *checked*, wenn Beschriftung
  und Standardwert stimmen.

## 3. Welche Variablen der Viewer zeigt

Grundregel (automatisch, ohne Zutun des Experten):
- **Eingabe** = Graph-Variable oder -Liste, die kein Baustein des Flows
  schreibt (`runtime_written_names`, Status ≠ *runtime*).
- **Laufzeit** = wird vom Flow geschrieben → nie im Formular; nach dem
  Lauf optional als *Ergebnis* (nur lesen) anzeigbar, wenn der Experte
  sie als Ausgabe markiert.
- Globale Variablen erscheinen nicht (sie gehören der Umgebung, nicht
  dem Auftrag); Ausnahme später über explizites Freischalten.

Der Experte kann die Automatik pro Variable übersteuern (neue
Metadaten an `NameVariable` / `ListVariable`, analog zu `group`/`status`,
werden generisch mitserialisiert):

| Feld | Bedeutung | Standard |
|---|---|---|
| `viewer` | `"input"` · `"output"` · `"hidden"` | `input` für Nicht-Laufzeit, `hidden` für Laufzeit |
| `label` | Beschriftung im Formular | Variablenname |
| `description` | Hilfetext unter dem Feld (auch Tooltip) | leer |
| `required` | darf nicht leer sein | `false` |
| `choices` | feste Auswahlliste (string/number) | keine |
| `minimum` / `maximum` | Zahlengrenzen | keine |
| `path_kind` | `file` · `folder` · `any`, plus `must_exist`, Dateifilter | `any` |
| `order` | Reihenfolge innerhalb der Gruppe | Anlage-Reihenfolge |

Gruppen (vorhanden) werden zu Formular-Abschnitten; Gruppenname =
Überschrift. Ungruppierte Eingaben bilden den ersten Abschnitt.

## 4. Was der Viewer aus dem Flow ableitet (ohne ihn zu zeigen)

- **Phasen**: Die Sectioning-Konvention des Flow Assistant
  (`section_N_completed`-Bools + OnVariableChanged-Trigger) wird erkannt
  und als Fortschrittsleiste "Phase 1/3 · Vorbereitung" dargestellt.
  Ohne Sections: Anzahl abgeschlossener Knoten / Gesamt.
- **Schrittname**: der aktuell laufende Knoten (Custom-Name oder Titel
  der ersten Instruction) als "Aktueller Schritt". Keine Kanten, keine
  Positionen.
- **Fehlerort**: bei Abbruch der Name des fehlgeschlagenen Schritts und
  die letzte Fehlermeldung; Rest im Protokoll.
- **Dokumentation**: Button "Beschreibung des Ablaufs" öffnet die
  PDF-Doku (`flow_doc`), falls der Experte sie neben den Flow gelegt hat.

## 5. Bildschirme des Viewers

1. **Start** — zuletzt verwendete Flows, *Flow öffnen…*, Drag & Drop.
   Zeigt Name, Branch·Revision, Autor/Beschreibung des Flows (neu:
   `graph.description`, im Studio unter Graph → Eigenschaften).
2. **Eingaben** (Hauptbildschirm) — Formular nach Abschnitt 3. Kopfzeile:
   Flow-Name, Preset-Auswahl (Dropdown + *Speichern als…*),
   *Letzte Werte*, *Zurücksetzen auf Standard*. Fußzeile: Arbeitsordner
   (Vorgabe: Ordner des Flows, änderbar), *Prüfen*, **Start**.
   Validierung live: Pflicht leer, Pfad fehlt, Zahl außerhalb → rotes
   Feld + Meldung, Start gesperrt.
   Optional pro Feld ein Häkchen "geprüft" (nutzt den vorhandenen
   *checked*-Status auf einer Kopie der Variablen) — der Experte kann per
   Flow-Option verlangen, dass alle Pflichtfelder abgehakt sind.
3. **Lauf** — Fortschrittsleiste (Phasen), aktueller Schritt, Laufzeit,
   Log (Filter Info/Warnung/Fehler, wie `LogPanel`), Buttons *Pause*,
   *Abbrechen*. Eingaben sind in dieser Zeit gesperrt, aber sichtbar
   (eingeklappt).
4. **Ergebnis** — Erfolg/Fehler groß, Dauer, Ausgabe-Variablen
   (`viewer: "output"`) als Tabelle, *Arbeitsordner öffnen*, *Protokoll
   speichern…*, *Erneut mit diesen Werten*, *Zurück zu Eingaben*.

## 6. Technik

**Paketstruktur** (im selben Repo, gleiche Kernbibliothek):
```
polytess/viewer/
  __main__.py      Einstieg `polytess-viewer [flow] [--preset NAME]`
  app.py           Fenster, Navigation Start → Eingaben → Lauf → Ergebnis
  form.py          Formular aus InputSpec bauen (Widgets je Typ)
  inputs.py        InputSpec aus Graph ableiten (Regeln aus Abschnitt 3)
  presets.py       Eingabesätze laden/speichern
  run_view.py      Fortschritt/Log, Bridge zu GraphProcessor
  results.py       Ergebnisbildschirm
polytess/graph/inputs.py   reine Ableitungslogik (testbar ohne Qt),
                           auch vom Studio für "Vorschau" genutzt
```
- **Ausführung**: exakt wie Studio und CLI — `Graph.load`, Werte setzen,
  `Context(graph, workdir)`, `GraphProcessor(graph).run(ctx)` unter
  qasync. `on_state`/`on_status` liefern Knotenstatus für Phasen und
  Schrittanzeige; `stop()`/`pause()` vorhanden.
- **Presets**: `~/.polytess/viewer/presets/<flow-family-id>/<name>.json`
  mit `{name: value}`; zusätzlich *Letzte Werte* automatisch. Bindung an
  die Flow-Familie (Lineage-ID), damit Branches dieselben Presets sehen;
  fehlende/neue Variablen werden beim Laden gemeldet, nicht stumm
  ignoriert. Format identisch zu `polytess run --vars-file` (neu, kleine
  CLI-Erweiterung), damit Presets auch headless laufen.
- **Kein Schreiben in den Flow**: Viewer arbeitet auf einer geladenen
  Kopie; Datei, `.history`, Lineage bleiben unangetastet. Protokolle
  landen unter `<workdir>/.runs/<zeitstempel>.log`.
- **Custom Library / Plugins**: dieselben Ladepfade wie Studio/CLI
  (`_load_everything`), sonst fehlen Bausteine. Fehlende Bausteine
  werden vor dem Start gemeldet ("Flow benötigt Baustein X, bitte
  Experten kontaktieren"), nicht erst im Lauf.
- **Packaging**: zweiter PyInstaller-Launcher in `build_exe.py`
  (`polytess-viewer.exe` neben `polytess.exe`, gleiches one-dir-Bundle,
  Dateityp-Zuordnung `.flow.json`). Release-Pipeline liefert ihn mit.
- **Lizenz**: Viewer prüft dieselbe Lizenzdatei; Vorschlag: eigenes
  Feld `edition: "viewer"` im Payload, damit Anwender-Lizenzen ohne
  Studio-Rechte ausgestellt werden können (Signatur/Prüfung unverändert).
- **Theme**: Studio-Theme, aber ruhiger — größere Schrift, ein Akzent,
  kein Dock-Layout.

**Ergänzungen im Studio**
- Blackboard: Kontextmenü *Viewer…* öffnet einen kleinen Dialog für die
  Felder aus Abschnitt 3 (oder Inspector-Panel bei Auswahl einer
  Variablen). Spalte/Marker "im Viewer sichtbar".
- Menü *Graph → Vorschau im Viewer* baut das Formular aus dem offenen
  Flow (gleiche `inputs.py`) in einem Dialog — kein Lauf.
- Graph-Eigenschaften: `description`, optional `viewer_requires_check`.
- Flow Assistant: Schema um `label`/`description`/`required` erweitern,
  damit erzeugte Flows sofort viewer-tauglich sind.

## 7. Offene Entscheidungen

- **Listen und Tabellen im Formular**: Listen als editierbare Zeilen
  (Plus/Minus) sind einfach; Tabellen eher als "CSV auswählen" statt
  Zellen-Editor. Vorschlag: Phase 1 nur Skalare + Pfade + Listen, Tabellen
  über Pfad-Variable.
- **Globale Variablen**: erst einmal ausblenden; später `viewer: "input"`
  auch für Globals zulassen.
- **Mehrere Läufe parallel** im selben Viewer: nein, ein Lauf pro
  Fenster; zweites Fenster möglich.
- **Rückkanal zum Experten**: "Problem melden" packt Flow-ID, Preset und
  Log in eine ZIP — Phase 3.

## 8. Hauptprozess als Kanban-Board (Ergänzung 2026-10-23)

### 8.1 Idee
Ein **Hauptprozess** ist ein gewöhnlicher polytess-Flow, dessen Knoten
überwiegend Sub-Workflow-Knoten sind (seit v1.17.0 mit expliziten
Inputs/Outputs). Jeder Sub-Workflow-Knoten ist im Viewer eine **Karte**,
die Kanten des Hauptflows sind die **Abhängigkeiten**. Der Viewer zeigt
den Hauptprozess nicht als Graph, sondern als Board mit drei Spalten:

| Backlog | Active | Done |
|---|---|---|
| noch nicht gerechnet | läuft gerade (Fortschritt, aktueller Schritt, Laufzeit) | fertig (Dauer, Ergebnisse, Protokoll) — fehlgeschlagene Karten bleiben rot in Active mit *Erneut starten* |

Kein neues Dateiformat: der Experte baut den Hauptprozess im Studio,
der Viewer projiziert ihn. Einzel-Flows ohne Sub-Workflow-Knoten
bekommen weiterhin das Formular aus Abschnitt 5.

### 8.2 Wie Anwender damit arbeiten
- **Karte nach Active ziehen** (oder ▶ auf der Karte) startet den
  Sub-Flow. Fehlen Eingaben, öffnet sich zuerst das Formular der Karte
  (Viewer-Form des Sub-Flows, minus alles, was der Hauptflow über
  Bindings liefert).
- **Vorgänger nicht fertig** → Dialog: *"Vorher müssen A und B
  gerechnet werden. Jetzt der Reihe nach starten / Trotzdem nur diese
  Karte / Abbrechen."* "Der Reihe nach" stellt die Vorgänger in eine
  Warteschlange und startet sie automatisch nacheinander.
- **Daten aus alten Läufen vorhanden** → Karte ist beim Öffnen bereits
  in Done (siehe Lauf-Zustand in 8.3); ein Hinweis "Ergebnis vom
  <Datum>" und *Neu rechnen* auf der Karte. Ändern sich die Eingaben
  einer Done-Karte, wird sie als *veraltet* markiert und ihre Nachfolger
  ebenfalls.
- **Nachfolger automatisch starten**: Schalter *Auto-Weiterlauf* (pro
  Board, Standard an). Wird eine Karte Done, wandern alle Nachfolger,
  deren Vorgänger komplett sind, nach Active. Parallele Zweige des
  Hauptflows laufen dann gleichzeitig — genau wie im Studio.
- **Pause / Abbrechen** pro Karte; *Alles starten* für den kompletten
  Prozess; Board-Zustand überlebt Schließen und Neustart.

### 8.3 Technik
- **Projektion**: `graph/board.py` (ohne Qt) liest den Hauptflow und
  liefert `BoardSpec`: Karten (= Sub-Workflow-Knoten mit Label,
  Beschreibung, Form-Eingaben, Outputs), Abhängigkeiten (transitive
  Vorgänger aus den Kanten; Conditions/Branch-Knoten dazwischen werden
  als "bedingt" markiert), Reihenfolge-Ebenen für die Spaltenanordnung.
  Voraussetzung: der Hauptflow ist azyklisch — Rückkanten meldet
  `polytess validate --board` als Problem.
- **Karte ausführen** = genau das, was `SubGraphNode._call` tut, nur
  ohne den Prozessor des Hauptflows: Bindings gegen den gespeicherten
  Variablenstand des Hauptflows auswerten, Sub-Flow frisch laden,
  `GraphProcessor.run`, Outputs in den Variablenstand zurückschreiben.
  Dafür wird `_call` in eine wiederverwendbare Funktion
  `run_subflow(node, state, workdir, on_status)` herausgezogen.
- **Lauf-Zustand**: `<hauptflow>.board.json` neben dem Flow (plus
  Kopie unter `~/.polytess/viewer/`): pro Karte Status
  (`pending|queued|active|done|failed|stale`), Start/Ende/Dauer,
  Hash der wirksamen Eingaben, Pfad des Protokolls; dazu die Werte
  der Hauptflow-Variablen nach jeder Karte. "Alte Läufe vorhanden" =
  Status done mit gleichem Eingabe-Hash. Optional kann der Experte pro
  Sub-Workflow-Knoten eine **Fertig-Prüfung** hinterlegen (ConditionList,
  z.B. FileExists auf die Ergebnisdatei) — dann gilt die Karte auch
  ohne Board-Historie als Done, wenn die Prüfung besteht.
- **Protokolle** je Karte unter `<workdir>/.runs/<karte>_<zeit>.log`.

### 8.4 Dashboard
Rechts neben dem Board (einklappbar) eine Statistik-Leiste:
- Fortschrittsring *fertig / gesamt*, Zähler Done · Active · Backlog ·
  Fehlgeschlagen · Veraltet.
- Laufzeiten: bisher verbrauchte Zeit, **geschätzte Restzeit** (aus den
  Dauern früherer Läufe derselben Karten), längste Karte.
- Verlauf: Läufe der letzten 30 Tage als kleine Balken, Erfolgsquote,
  Karte mit den meisten Fehlschlägen (zeigt, wo der Experte nachbessern
  sollte).
- Kritischer Pfad: welche Kette bestimmt die Gesamtdauer; Karten darauf
  sind dezent markiert.
- Export der Statistik als CSV/PDF (reportlab ist vorhanden).

### 8.5 Design und Gamification
Das Board soll Spaß machen, ohne albern zu werden — die Zielgruppe sind
Ingenieure, die Ergebnisse erwarten. Vorschlag in drei Stufen, alle in
den Einstellungen abschaltbar (*Celebrations: off / subtle / full*):
- **Immer an (keine Gamification, nur gute Gestaltung)**: Karten mit
  Akzentfarbe des Sub-Flows, weiches Gleiten beim Spaltenwechsel
  (QPropertyAnimation), pulsierender Rand bei Active, Fortschrittsring
  auf der Karte, klare Typografie, Dunkel-Theme wie im Studio.
- **Subtle (Standard, vom User bestätigt 2026-10-23)**: kurzes
  Aufleuchten und Häkchen-Animation beim Wechsel nach Done; **playful
  bounce** beim Ablegen einer Karte in einer Spalte — egal ob der
  Anwender sie zieht oder der Auto-Weiterlauf sie verschiebt (kurzes
  Überschwingen mit QEasingCurve.OutBack, ≈ 250 ms, nie länger als die
  Interaktion selbst); Toast "Meshing fertig · 4 min 12 s", dezenter
  Klang optional, Streak-Anzeige "7 Läufe in Folge ohne Fehler".
- **Full**: Konfetti-Partikel (QGraphicsScene) wenn der ganze
  Hauptprozess Done ist, Tagesziel-Ring ("3 von 3 geplanten Flows"),
  Abzeichen pro Projekt (erster vollständiger Durchlauf, fehlerfreie
  Woche, schnellster Lauf) — sichtbar nur im Dashboard, ohne
  Ranglisten oder Punkte zwischen Personen.
Grundsatz: Feedback belohnt Fortschritt des Prozesses, nie Klickzahlen;
nichts davon blockiert oder verlangsamt die Arbeit.

### 8.6 Studio-Seite
- Sub-Workflow-Knoten bekommt im Inspector *Board-Karte*: Titel,
  Beschreibung, Farbe, optionale Fertig-Prüfung.
- *Graph → Vorschau als Board* zeigt die Projektion des offenen
  Hauptflows (ohne Lauf), damit der Experte Ebenen und Beschriftung
  prüfen kann.

## 9. Phasen

| Phase | Inhalt | Ergebnis |
|---|---|---|
| **1 · Kern** ✅ | `graph/inputs.py`, Variablen-Metadaten (`form`), Blackboard-Dialog, `polytess inputs`, `run --vars-file` | umgesetzt in v1.16.0 |
| **2 · Viewer-App (Formular)** | Start-, Eingabe-, Lauf-, Ergebnisbildschirm; Presets; Phasen-Erkennung; Exe-Launcher | Anwender kann Einzel-Flows ausführen |
| **3 · Board-Kern** | `graph/board.py` (BoardSpec, Abhängigkeiten, Zyklus-Check), `run_subflow` aus `SubGraphNode._call`, Lauf-Zustand `.board.json` mit Eingabe-Hash, `polytess validate --board`, `polytess board <flow>` (Status als Text) | Board-Logik testbar ohne GUI |
| **4 · Board-UI** | drei Spalten mit Drag & Drop, Karten mit Fortschritt, Vorgänger-Dialog, Auto-Weiterlauf, Pause/Abbrechen, Karten-Formular | Hauptprozess bedienbar |
| **5 · Dashboard + Erlebnis** | Statistik-Leiste, Restzeit-Schätzung, Verlauf, Celebrations-Stufen, Fertig-Prüfung im Studio, Board-Vorschau im Studio | rund und angenehm |
| **6 · Komfort** | Flow-Beschreibung, "Problem melden", Viewer-Lizenz-Edition, Handbuchkapitel | Alltag |

Aufwandsschätzung: Phase 2 ≈ 3–4 Sessions, Phase 3 ≈ 2, Phase 4 ≈ 3–4,
Phase 5 ≈ 2–3, Phase 6 ≈ 2. Phase 3 kann vor Phase 2 begonnen werden,
weil sie keine GUI braucht; die Board-UI (4) setzt den Lauf-Bildschirm
aus Phase 2 wieder ein (Karte aufklappen = Lauf-Ansicht).
Tests: `inputs.py` und Presets rein per pytest; Formular und Lauf per
offscreen-Smoke-Tests wie `test_gui_smoke.py`; ein End-to-End-Test
"Beispielflow im Viewer starten, Ergebnis-Variable prüfen".
