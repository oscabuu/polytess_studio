# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""polytess — node-based workflow studio for engineering computations.

Visual scripting for mechanical-engineering workflows: folder setup,
input-file templating, solver runs (Simpack, Abaqus, FEMFAT), DOEs on
HPC or locally, post-processing — built from reusable blocks on a
node graph, runnable in the desktop studio (PySide6) or headless.
"""

__version__ = "1.6.0"

# ---- legacy import alias ---------------------------------------------------- #
# polytess was previously named polyflow, and before that gcflow. User
# custom-library files written back then import ``gcflow.*``/``polyflow.*``;
# this finder serves lightweight proxy modules that forward every attribute
# to the real polytess module — the real code never runs twice, so class
# identity and the registry stay intact. Proxy packages get an EMPTY
# __path__ so the normal PathFinder cannot re-execute submodules under a
# legacy name.

import importlib
import importlib.abc
import importlib.util
import sys as _sys
import types as _types

_LEGACY_NAMES = ("gcflow", "polyflow")


class _LegacyAliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):

    def find_spec(self, fullname, path=None, target=None):
        for legacy in _LEGACY_NAMES:
            if fullname == legacy or fullname.startswith(legacy + "."):
                return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        legacy = next(l for l in _LEGACY_NAMES
                      if spec.name == l or spec.name.startswith(l + "."))
        real = importlib.import_module(
            __name__ + spec.name[len(legacy):])
        module = _types.ModuleType(spec.name)
        module.__getattr__ = lambda name: getattr(real, name)   # PEP 562
        if hasattr(real, "__path__"):
            module.__path__ = []     # package marker; submodules come here
        return module

    def exec_module(self, module):
        pass


if not any(isinstance(f, _LegacyAliasFinder) for f in _sys.meta_path):
    _sys.meta_path.append(_LegacyAliasFinder())
