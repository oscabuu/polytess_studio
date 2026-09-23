# Plan: polytess Viewer — Flows ausführen ohne den Flow zu sehen

Stand: 2026-09-23 · Basis: polytess Studio v1.15.0 (Blackboard mit Status-Tags,
`runtime_written_names`, `GraphProcessor`, CLI `polytess run --var`)

> **Status: Phase 1 UMGESETZT** (2026-09-23, v1.16.0): `form`-Metadaten an
> Variablen/Listen, Blackboard-Dialog *Viewer Settings…*,
> `polytess/graph/inputs.py` (InputSpec, Validierung, apply, Vars-Datei),
> CLI `polytess inputs` und `run --vars-file`, Assistant-Schema. Metadaten
> liegen in einem `form`-Dict statt in Einzelfeldern (Abschnitt 3).
> Phase 2 (Viewer-App) offen.

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

## 8. Phasen

| Phase | Inhalt | Ergebnis |
|---|---|---|
| **1 · Kern** | `graph/inputs.py` (InputSpec, Validierung), Variablen-Metadaten (`viewer`, `label`, `description`, `required`, `minimum/maximum`, `choices`, `path_kind`), Blackboard-Dialog dafür, `polytess run --vars-file` | testbar ohne GUI; Studio kann Metadaten pflegen |
| **2 · Viewer-App** | Start-, Eingabe-, Lauf-, Ergebnisbildschirm; Presets; Phasen-Erkennung; Exe-Launcher | Anwender kann Flows ausführen |
| **3 · Komfort** | Vorschau im Studio, Flow-Beschreibung, Ausgabe-Variablen, "Problem melden", Viewer-Lizenz-Edition, Handbuchkapitel | rund für den Alltag |

Aufwandsschätzung: Phase 1 ≈ 1–2 Sessions, Phase 2 ≈ 3–4, Phase 3 ≈ 2.
Tests: `inputs.py` und Presets rein per pytest; Formular und Lauf per
offscreen-Smoke-Tests wie `test_gui_smoke.py`; ein End-to-End-Test
"Beispielflow im Viewer starten, Ergebnis-Variable prüfen".
