# HowTo: Set Up and Run polytess on Linux

Tested with Python 3.13 (macOS); requires **Python ≥ 3.11**.

## 1. Prerequisites

### Python + venv

```bash
python3 --version          # must be >= 3.11
# if too old (RHEL/old Ubuntu): install python3.11/3.12 from the repos or as a module
# Ubuntu/Debian:  sudo apt install python3.12 python3.12-venv
# RHEL/Alma:      sudo dnf install python3.12
```

### System Libraries for Qt (GUI only, not needed for the CLI)

PySide6/Qt6 needs the xcb libraries on Linux. Usually only one is missing:

```bash
# Ubuntu/Debian:
sudo apt install libxcb-cursor0 libxcb-xinerama0 libgl1 libegl1 \
                 libxkbcommon-x11-0 libdbus-1-3
# RHEL/Alma/Rocky:
sudo dnf install xcb-util-cursor libxkbcommon-x11 mesa-libGL
```

Without admin rights: the CLI (`polytess run`) works **without** these
packages; for the GUI, fall back to `QT_QPA_PLATFORM=offscreen` (tests
only) or have an admin install the packages.

## 2. Installation (one-time)

Copy the portable folder anywhere (e.g. `~/tools/polytess`), then:

```bash
cd ~/tools/polytess
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

**That's already enough.** polytess and its plugins do NOT need to be
installed: if you start `python -m polytess` / `python -m polytess.cli`
**from the project folder**, `polytess` is imported from there, and
every plugin under `plugins/` is found and loaded automatically
(fallback search; an additional plugin location is also possible via
`POLYTESS_PLUGINS_PATH`).

Optional — only if you also want to import `polytess` from other
directories:

```bash
./.venv/bin/pip install -e .        # the main package alone is enough
```

> **"Directory not empty" error on `pip install -e …`?**
> That's an NFS problem (home directory on NFS): pip can't delete its
> temporary build folders because of `.nfs*` files. Workaround:
> ```bash
> TMPDIR=/tmp ./.venv/bin/pip install --no-cache-dir -e .
> ```
> (Put temp files on local disk; install packages one at a time instead
> of in one command if needed.) Or just work without installing at all
> — see above.

**Proxy/offline?** On a machine with internet access, run
`pip download -r requirements.txt -d wheels/`, copy the `wheels` folder
over too, and install with
`pip install --no-index --find-links wheels -r requirements.txt`.

## 3. Connecting Your Own Domain Plugins (optional)

The portable folder only ships `plugins/simpack_template` (the
template, see 5.). Your own domain plugins — e.g. an HPC cluster
wrapper or mesh tools — go alongside it under `plugins/<name>/` (or
anywhere, via `POLYTESS_PLUGINS_PATH`); they're found and loaded
automatically at startup. Such plugins typically bring their own
environment variables/prerequisites — see their own documentation.

## 4. Running

```bash
cd ~/tools/polytess

# GUI studio (needs an X11/Wayland session):
./.venv/bin/python -m polytess
./.venv/bin/python -m polytess examples/demo.flow.json

# Headless (batch, compute server, HPC login node — no GUI needed):
./.venv/bin/python -m polytess.cli validate examples/demo.flow.json
./.venv/bin/python -m polytess.cli run examples/demo.flow.json --var case=run42
./.venv/bin/python -m polytess.cli run my_workflow.flow.json --workdir /scratch/project

# Tests (GUI tests run offscreen, no display needed):
QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest
```

## 5. Your Own Actions

Drop one file per class — `instruction_<name>.py` / `condition_<name>.py`
/ `event_<name>.py` — into `plugins/simpack_template/polytess_simpack/`
(or your own plugin); it's loaded automatically, no import line needed.
Copy template with instructions:
`plugins/simpack_template/polytess_simpack/_template.py`.

## 6. Troubleshooting

| Problem | Solution |
|---|---|
| `pip install -e` → "Directory not empty" | NFS home: `TMPDIR=/tmp pip install --no-cache-dir -e .`, install packages one at a time — or run without installing, straight from the project folder (see 2.) |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` | missing xcb packages (see 1.); detailed diagnostics with `QT_DEBUG_PLUGINS=1` |
| GUI over SSH | `ssh -X` (slow) or better local/VNC; prefer the CLI |
| E-mail doesn't arrive | needs system `sendmail`; otherwise only a warning is logged (field `strict`) |
| Wayland rendering issues | `QT_QPA_PLATFORM=xcb ./.venv/bin/python -m polytess` |

## 7. Docs in This Folder

- `README.md` — using the studio, concepts, project structure
- `LICENSE.txt` — Business Source License 1.1
