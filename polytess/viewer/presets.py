# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Saved input sets ("presets") per flow family.

``~/.polytess/viewer/presets/<flow_id>/<name>.json`` — the same
``{name: value}`` format as ``polytess run --vars-file``. ``_last``
holds the values of the most recent run automatically."""

from __future__ import annotations

import os
import re

from polytess.graph.inputs import load_vars_file, save_vars_file

LAST = "_last"


def presets_dir(flow_id: str) -> str:
    from polytess.core.userdir import user_dir
    folder = os.path.join(user_dir(), "viewer", "presets", flow_id or "no-id")
    os.makedirs(folder, exist_ok=True)
    return folder


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-. ]+", "_", name).strip() or "preset"


def list_presets(flow_id: str) -> list[str]:
    names = []
    for entry in sorted(os.listdir(presets_dir(flow_id))):
        if entry.endswith(".json") and not entry.startswith("_"):
            names.append(entry[:-5])
    return names


def save_preset(flow_id: str, name: str, values: dict) -> str:
    path = os.path.join(presets_dir(flow_id), _safe(name) + ".json")
    save_vars_file(path, values)
    return path


def load_preset(flow_id: str, name: str) -> dict:
    path = os.path.join(presets_dir(flow_id), _safe(name) + ".json")
    return load_vars_file(path) if os.path.isfile(path) else {}


def delete_preset(flow_id: str, name: str) -> None:
    path = os.path.join(presets_dir(flow_id), _safe(name) + ".json")
    if os.path.isfile(path):
        os.remove(path)


def save_last(flow_id: str, values: dict) -> None:
    save_vars_file(os.path.join(presets_dir(flow_id), LAST + ".json"), values)


def load_last(flow_id: str) -> dict:
    path = os.path.join(presets_dir(flow_id), LAST + ".json")
    return load_vars_file(path) if os.path.isfile(path) else {}
