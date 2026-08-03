# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Headless CLI — run workflow files without the GUI (batch/HPC use).

    polytess run workflow.flow.json [--var name=value ...] [--workdir DIR]
    polytess validate workflow.flow.json
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


def _load_everything() -> None:
    """Import the standard library + plugins so all $types resolve.

    Plugins are found two ways:
    1. installed packages via the ``polytess.plugins`` entry-point group,
    2. fallback: package folders under ``<project>/plugins/*/`` (and
       ``$POLYTESS_PLUGINS_PATH``) — no pip install needed, which keeps the
       portable folder working on machines where editable installs fail
       (e.g. NFS homes)."""
    from polytess.core.app_settings import sync_python_include_paths
    sync_python_include_paths()
    import polytess.library  # noqa: F401  (registers built-in types)
    from importlib.metadata import entry_points
    for ep in (list(entry_points(group="polytess.plugins"))
               + list(entry_points(group="polyflow.plugins"))     # legacy
               + list(entry_points(group="gcflow.plugins"))):     # groups
        try:
            ep.load()
        except Exception as exc:   # a broken plugin must not kill the CLI
            print(f"[WARNING] plugin {ep.name!r} failed to load: {exc}", file=sys.stderr)
    _load_folder_plugins()
    from polytess.library.custom import load_custom_library
    load_custom_library()      # user files from the studio code editor


def _load_folder_plugins() -> None:
    import importlib
    from pathlib import Path

    from polytess.core.userdir import env as _env
    roots = []
    env = _env("PLUGINS_PATH")
    if env:
        roots += [Path(p) for p in env.split(os.pathsep) if p]
    from polytess.core.userdir import install_roots
    roots += [Path(r) / "plugins" for r in install_roots()]

    for root in roots:
        if not root.is_dir():
            continue
        for plugin_dir in sorted(root.iterdir()):
            if not plugin_dir.is_dir():
                continue
            for package in sorted(plugin_dir.iterdir()):
                if not (package.is_dir() and (package / "__init__.py").is_file()):
                    continue
                name = package.name
                if name in sys.modules:      # already loaded (entry point)
                    continue
                if str(plugin_dir) not in sys.path:
                    sys.path.insert(0, str(plugin_dir))
                try:
                    importlib.import_module(name)
                except Exception as exc:
                    print(f"[WARNING] folder plugin {name!r} failed to load: {exc}",
                          file=sys.stderr)


def _apply_vars(graph, pairs: list[str]) -> None:
    for pair in pairs:
        name, _, value = pair.partition("=")
        graph.variables.set(name.strip(), value)


def cmd_run(args: argparse.Namespace) -> int:
    from polytess.core.context import Context
    from polytess.graph.model import Graph
    from polytess.graph.processor import GraphProcessor

    graph = Graph.load(args.file)
    graph.ensure_endpoints()
    _apply_vars(graph, args.var or [])

    workdir = os.path.abspath(args.workdir or os.path.dirname(os.path.abspath(args.file)))
    ctx = Context(graph=graph, workdir=workdir)
    processor = GraphProcessor(graph)

    async def _main() -> None:
        try:
            await processor.run(ctx)
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\n[WARNING] interrupted", file=sys.stderr)
        return 130
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from polytess.graph.model import Graph
    graph = Graph.load(args.file)
    problems: list[str] = []
    guids = {n.guid for n in graph.nodes}
    for edge in graph.edges:
        if edge.src_node not in guids or edge.dst_node not in guids:
            problems.append(f"dangling edge {edge!r}")
    from polytess.graph.nodes import StartNode, TriggerNode
    if not any(isinstance(n, (StartNode, TriggerNode)) for n in graph.nodes):
        problems.append("no entry point (Start or Trigger node)")
    for problem in problems:
        print(f"[ERROR] {problem}")
    print(f"{args.file}: {len(graph.nodes)} nodes, {len(graph.edges)} edges — "
          f"{'INVALID' if problems else 'ok'}")
    return 1 if problems else 0


def cmd_doc(args: argparse.Namespace) -> int:
    from polytess.graph.flow_doc import generate_flow_doc
    from polytess.graph.model import Graph
    graph = Graph.load(args.file)
    out = args.out or (os.path.splitext(args.file)[0]
                       .replace(".flow", "") + "_doc.pdf")
    generate_flow_doc(graph, out, source_path=args.file)
    print(f"documentation written: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from polytess import __version__
    parser = argparse.ArgumentParser(prog="polytess",
                                     description="Run polytess workflows headless")
    parser.add_argument("--version", action="version",
                        version=f"polytess {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="execute a workflow file")
    p_run.add_argument("file")
    p_run.add_argument("--var", action="append", metavar="NAME=VALUE",
                       help="override a graph variable (repeatable)")
    p_run.add_argument("--workdir", default="", help="working directory (default: file's folder)")
    p_run.set_defaults(fn=cmd_run)

    p_val = sub.add_parser("validate", help="check a workflow file")
    p_val.add_argument("file")
    p_val.set_defaults(fn=cmd_validate)

    p_doc = sub.add_parser("doc", help="export flow documentation as PDF")
    p_doc.add_argument("file")
    p_doc.add_argument("-o", "--out", default="",
                       help="output PDF (default: <flow>_doc.pdf)")
    p_doc.set_defaults(fn=cmd_doc)

    args = parser.parse_args(argv)
    _load_everything()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
