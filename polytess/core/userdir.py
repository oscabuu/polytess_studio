# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""User configuration directory (``~/.polytess``) with legacy migration.

polytess was previously named gcflow; existing installations keep their
settings, license and custom library: the first access copies ``~/.gcflow``
to ``~/.polytess`` (the old directory stays untouched as a backup).
Environment variables follow the same pattern — ``POLYTESS_*`` is
authoritative, the legacy ``GCFLOW_*`` name still works.
"""

from __future__ import annotations

import os
import shutil

# newest legacy first — polytess was previously named polyflow, and before
# that gcflow; the first existing directory wins the one-time migration
_LEGACY_DIRS = (".polyflow", ".gcflow")
_LEGACY_ENV_PREFIXES = ("POLYFLOW_", "GCFLOW_")


def user_dir() -> str:
    """``~/.polytess`` — created on demand, migrated from a legacy dir."""
    new = os.path.join(os.path.expanduser("~"), ".polytess")
    if not os.path.isdir(new):
        for legacy in _LEGACY_DIRS:
            old = os.path.join(os.path.expanduser("~"), legacy)
            if os.path.isdir(old):
                try:
                    shutil.copytree(old, new)
                except OSError:
                    pass
                break
    os.makedirs(new, exist_ok=True)
    return new


def install_roots() -> list[str]:
    """Directories that count as 'next to the installation' — the package
    parent, and for frozen executables (PyInstaller) additionally the
    folder containing the executable itself (license.lic, plugins/ and
    custom_library/ may live there)."""
    import sys
    import polytess
    roots = [os.path.dirname(os.path.dirname(
        os.path.abspath(polytess.__file__)))]
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if exe_dir not in roots:
            roots.append(exe_dir)
    return roots


def env(name: str, default: str = "") -> str:
    """``POLYTESS_<name>`` with fallback to the legacy prefixes."""
    value = os.environ.get(f"POLYTESS_{name}", "")
    for prefix in _LEGACY_ENV_PREFIXES:
        if value:
            break
        value = os.environ.get(f"{prefix}{name}", "")
    return value or default
