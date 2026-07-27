# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Context — the execution context threaded through the whole system."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

LogFn = Callable[[str, str], None]   # (level, message)


def _default_log(level: str, message: str) -> None:
    print(f"[{level.upper():7s}] {message}")


class Context:

    def __init__(self, graph=None, globals_scope=None, logger: LogFn | None = None,
                 target: Any = None, workdir: str = "", runner=None):
        from polytess.core.variables import GlobalScope
        self.graph = graph                       # owning Graph (graph variables)
        self.globals = globals_scope if globals_scope is not None else GlobalScope.instance()
        self.logger: LogFn = logger or _default_log
        self.target: Any = target                # loop element / current subject
        self.workdir = workdir or os.getcwd()
        self.runner = runner                     # GraphProcessor while running
        self._cancelled = False
        self._parent: Context | None = None

    # ---- cancellation ----------------------------------------------------- #

    @property
    def is_cancelled(self) -> bool:
        if self._cancelled:
            return True
        return self._parent.is_cancelled if self._parent is not None else False

    def cancel(self) -> None:
        self._cancelled = True

    # ---- logging ----------------------------------------------------------- #

    def log(self, level: str, message: str) -> None:
        self.logger(level, message)

    def debug(self, message: str) -> None: self.log("debug", message)
    def info(self, message: str) -> None: self.log("info", message)
    def warning(self, message: str) -> None: self.log("warning", message)
    def error(self, message: str) -> None: self.log("error", message)

    # ---- variables --------------------------------------------------------- #

    @property
    def graph_variables(self):
        return self.graph.variables if self.graph is not None else None

    @property
    def graph_lists(self):
        return self.graph.lists if self.graph is not None else None

    def resolve_path(self, path: str) -> str:
        """Make relative paths relative to the workflow working directory."""
        path = os.path.expandvars(os.path.expanduser(str(path)))
        if not os.path.isabs(path):
            path = os.path.join(self.workdir, path)
        return os.path.normpath(path)

    # ---- derived contexts) --------------------- #

    def child(self, target: Any = ...) -> "Context":
        ctx = Context(graph=self.graph, globals_scope=self.globals, logger=self.logger,
                      target=self.target if target is ... else target,
                      workdir=self.workdir, runner=self.runner)
        ctx._parent = self
        return ctx

    # ---- misc ---------------------------------------------------------------- #

    @staticmethod
    def timestamp() -> float:
        return time.time()
