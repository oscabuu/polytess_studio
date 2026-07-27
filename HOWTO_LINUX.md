# HowTo: polytess auf Linux einrichten und ausführen

Getestet mit Python 3.13 (macOS); benötigt wird **Python ≥ 3.11**.

## 1. Voraussetzungen

### Python + venv

```bash
python3 --version          # muss >= 3.11 sein
# falls zu alt (RHEL/alte Ubuntu): python3.11/3.12 aus den Repos oder als Modul laden
# Ubuntu/Debian:  sudo apt install python3.12 python3.12-venv
# RHEL/Alma:      sudo dnf install python3.12
```

### System-Bibliotheken für Qt (nur für die GUI, nicht für die CLI)

PySide6/Qt6 braucht auf Linux die xcb-Bibliotheken. Häufig fehlt nur eine:

```bash
# Ubuntu/Debian:
sudo apt install libxcb-cursor0 libxcb-xinerama0 libgl1 libegl1 \
                 libxkbcommon-x11-0 libdbus-1-3
# RHEL/Alma/Rocky:
sudo dnf install xcb-util-cursor libxkbcommon-x11 mesa-libGL
```

Ohne Adminrechte: die CLI (`polytess run`) läuft **ohne** diese Pakete;
für die GUI notfalls `QT_QPA_PLATFORM=offscreen` (nur Tests) oder die
Pakete vom Admin installieren lassen.

## 2. Installation (einmalig)

Portablen Ordner an beliebige Stelle kopieren (z. B. `~/tools/polytess`), dann:

```bash
cd ~/tools/polytess
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

**Das genügt bereits.** polytess und die Plugins müssen NICHT installiert
werden: Startest du `python -m polytess` / `python -m polytess.cli` **aus dem
Projektordner**, wird `polytess` von dort importiert, und alle Plugins unter
`plugins/` werden automatisch gefunden und geladen (Fallback-Suche; eigener
Plugin-Ort zusätzlich über `POLYTESS_PLUGINS_PATH` möglich).

Optional — nur wenn du `polytess` auch aus anderen Verzeichnissen heraus
importieren willst:

```bash
./.venv/bin/pip install -e .        # nur das Hauptpaket reicht
```

> **Fehler „Directory not empty" bei `pip install -e …`?**
> Das ist ein NFS-Problem (Home-Verzeichnis auf NFS): pip kann seine
> temporären Build-Ordner wegen `.nfs*`-Dateien nicht löschen. Abhilfe:
> ```bash
> TMPDIR=/tmp ./.venv/bin/pip install --no-cache-dir -e .
> ```
> (Temp auf lokale Platte legen; Pakete notfalls einzeln statt in einem
> Befehl installieren.) Oder einfach ganz ohne Install arbeiten — siehe oben.

**Proxy/Offline?** Auf einem Rechner mit Internet
`pip download -r requirements.txt -d wheels/` ausführen, den `wheels`-Ordner
mitkopieren und installieren mit
`pip install --no-index --find-links wheels -r requirements.txt`.

## 3. Eigene Domain-Plugins anbinden (optional)

Der portable Ordner bringt nur `plugins/simpack_template` mit (die
Vorlage, siehe 5.). Eigene Domain-Plugins — z. B. ein HPC-Cluster-Wrapper
oder Mesh-Werkzeuge — legst du daneben unter `plugins/<name>/` ab (oder an
einem beliebigen Ort über `POLYTESS_PLUGINS_PATH`); sie werden beim Start
automatisch gefunden und geladen. Solche Plugins bringen typischerweise
ihre eigenen Umgebungsvariablen/Voraussetzungen mit — siehe deren eigene
Dokumentation.

## 4. Ausführen

```bash
cd ~/tools/polytess

# GUI-Studio (X11/Wayland-Session nötig):
./.venv/bin/python -m polytess
./.venv/bin/python -m polytess examples/demo.flow.json

# Headless (Batch, Rechenserver, HPC-Loginknoten — keine GUI nötig):
./.venv/bin/python -m polytess.cli validate examples/demo.flow.json
./.venv/bin/python -m polytess.cli run examples/demo.flow.json --var case=run42
./.venv/bin/python -m polytess.cli run mein_workflow.flow.json --workdir /scratch/projekt

# Tests (GUI-Tests laufen offscreen, brauchen keinen Bildschirm):
QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest
```

## 5. Eigene Actions

Eine Datei pro Klasse: `instruction_<name>.py` / `condition_<name>.py` /
`event_<name>.py` in `plugins/simpack_template/polytess_simpack/` (oder eigenem
Plugin) ablegen — wird automatisch geladen, keine Import-Zeile nötig.
Kopiervorlage mit Anleitung: `plugins/simpack_template/polytess_simpack/_template.py`.

## 6. Troubleshooting

| Problem | Lösung |
|---|---|
| `pip install -e` → „Directory not empty" | NFS-Home: `TMPDIR=/tmp pip install --no-cache-dir -e .`, Pakete einzeln installieren — oder ohne Install aus dem Projektordner starten (siehe 2.) |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` | fehlende xcb-Pakete (siehe 1.); Detaildiagnose mit `QT_DEBUG_PLUGINS=1` |
| GUI über SSH | `ssh -X` (langsam) oder besser lokal/VNC; CLI bevorzugen |
| E-Mail kommt nicht | braucht System-`sendmail`; sonst wird nur gewarnt (Feld `strict`) |
| Wayland-Darstellungsprobleme | `QT_QPA_PLATFORM=xcb ./.venv/bin/python -m polytess` |

## 7. Doku im Ordner

- `README.md` — Bedienung des Studios, Konzepte, Projektstruktur
- `LICENSE.txt` — Business Source License 1.1
