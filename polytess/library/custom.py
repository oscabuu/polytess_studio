# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""User library — python files written in the studio code editor.

Lives in ``~/.polytess/custom_library`` (override: ``POLYTESS_CUSTOM_LIBRARY``).
Every non-underscore ``*.py`` file is loaded at startup like the built-in
library; saving a file in the editor re-executes it and REPLACES its types
in the registry (hot reload — the type selector picks it up immediately,
no duplicates)."""

from __future__ import annotations

import os
import sys
import types

from polytess.core.metadata import unregister_module

_PREFIX = "polytess_custom"


def custom_library_dir() -> str:
    from polytess.core.userdir import env, user_dir
    folder = env("CUSTOM_LIBRARY") or os.path.join(user_dir(),
                                                   "custom_library")
    os.makedirs(folder, exist_ok=True)
    return folder


def install_custom_dir() -> str | None:
    """``custom_library/`` next to the installation (bundled blocks), or
    None — for frozen executables also next to the .exe/.app."""
    from polytess.core.userdir import install_roots
    for root in install_roots():
        folder = os.path.join(root, "custom_library")
        if os.path.isdir(folder):
            return folder
    return None


def load_custom_module(path: str):
    """(Re)load one custom-library file; its registered types replace any
    previous version. Raises on syntax/registration errors."""
    stem = os.path.splitext(os.path.basename(path))[0]
    module_name = f"{_PREFIX}.{stem}"
    unregister_module(module_name)
    sys.modules.pop(module_name, None)
    # compile the source directly — the import machinery's bytecode cache
    # can serve stale code right after an editor save (same size + mtime)
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    code = compile(source, path, "exec")
    module = types.ModuleType(module_name)
    module.__file__ = path
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        unregister_module(module_name)     # drop half-registered types
        raise
    return module


def load_custom_library(folder: str | None = None) -> list[tuple[str, str]]:
    """Load every custom file; returns [(filename, error)] for files that
    failed — a broken user file must not prevent startup.

    Without an explicit *folder*, the bundled install-local
    ``custom_library/`` loads first and the user's folder second, so
    user copies of a block override bundled ones."""
    if folder:
        folders = [folder]
    else:
        folders = [f for f in (install_custom_dir(), custom_library_dir()) if f]
    errors: list[tuple[str, str]] = []
    for current in folders:
        try:
            names = sorted(os.listdir(current))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".py") or name.startswith("_"):
                continue
            try:
                load_custom_module(os.path.join(current, name))
            except Exception as exc:
                errors.append((name, f"{exc.__class__.__name__}: {exc}"))
                print(f"[WARNING] custom library {name!r} failed to load: {exc}",
                      file=sys.stderr)
    return errors
