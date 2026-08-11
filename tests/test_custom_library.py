"""Custom user library: loading, hot reload (no selector duplicates),
error handling and the in-studio code editor."""

import os

import pytest

from polytess.core import GlobalScope
from polytess.core.instructions import Instruction
from polytess.core.metadata import iter_subclasses, registered_types, resolve_type
from polytess.library.custom import load_custom_library, load_custom_module

SOURCE_V1 = '''
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta

@meta(title="My Step", category="Custom/My Step", icon="terminal", color="teal",
      description="v1")
class MyStep(Instruction):
    async def run(self, ctx):
        ctx.info("v1")
'''

SOURCE_V2 = SOURCE_V1.replace('description="v1"', 'description="v2"') \
                     .replace('ctx.info("v1")', 'ctx.info("v2")')


@pytest.fixture(autouse=True)
def fresh_globals():
    GlobalScope.reset()
    yield
    from polytess.core.metadata import unregister_module
    unregister_module("polytess_custom.instruction_my_step")
    GlobalScope.reset()


def test_load_and_hot_reload(tmp_path):
    path = tmp_path / "instruction_my_step.py"
    path.write_text(SOURCE_V1)
    load_custom_module(str(path))

    cls = resolve_type("MyStep")
    assert issubclass(cls, Instruction)
    from polytess.core.metadata import get_meta
    assert get_meta(cls).description == "v1"

    # hot reload: registry entry REPLACED, exactly one selector candidate
    path.write_text(SOURCE_V2)
    load_custom_module(str(path))
    cls2 = resolve_type("MyStep")
    assert get_meta(cls2).description == "v2"
    candidates = [c for c in iter_subclasses(Instruction)
                  if c.__name__ == "MyStep"]
    assert candidates == [cls2]


def test_broken_file_does_not_break_startup(tmp_path):
    (tmp_path / "instruction_my_step.py").write_text(SOURCE_V1)
    (tmp_path / "instruction_broken.py").write_text("def nope(:\n")
    errors = load_custom_library(str(tmp_path))
    assert len(errors) == 1 and errors[0][0] == "instruction_broken.py"
    assert "MyStep" in registered_types()
    # a broken reload keeps NO half-registered types
    assert not any(c.__module__ == "polytess_custom.instruction_broken"
                   for c in registered_types().values())


def test_code_editor_panel(tmp_path, monkeypatch):
    import os as _os
    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from polytess.gui.code_editor import CodeEditorPanel

    panel = CodeEditorPanel(folder=str(tmp_path))
    assert panel.files.count() == 0

    # simulate the New wizard result: write a template-based file directly
    path = tmp_path / "instruction_my_step.py"
    path.write_text(SOURCE_V1)
    panel.refresh_files(select="instruction_my_step.py")
    assert panel.files.currentText() == "instruction_my_step.py"
    assert "My Step" in panel.edit.toPlainText()

    # edit + save -> registry updated
    panel.edit.setPlainText(SOURCE_V2)
    assert panel.save() is True
    from polytess.core.metadata import get_meta
    assert get_meta(resolve_type("MyStep")).description == "v2"

    # syntax error: file saved, nothing registered, status shows the line
    panel.edit.setPlainText("def nope(:\n")
    assert panel.save() is False
    assert "SYNTAX ERROR" in panel.status.text()
    assert path.read_text() == "def nope(:\n"
    assert get_meta(resolve_type("MyStep")).description == "v2"  # old kept


def test_include_path_import_works_inside_custom_block(tmp_path, monkeypatch):
    """A package folder from Settings -> Python -> Include Paths is
    importable in a custom-library block with a plain `import` — no
    re-declaration inside the instruction needed."""
    import asyncio
    import sys

    from polytess.core import Context, GlobalScope
    from polytess.core.app_settings import AppSettings, \
        sync_python_include_paths
    from polytess.library.custom import load_custom_module

    package_dir = tmp_path / "tools"
    (package_dir / "loadtools").mkdir(parents=True)
    (package_dir / "loadtools" / "__init__.py").write_text(
        "def combine(folder):\n    return f'combined:{folder}'\n",
        encoding="utf-8")

    AppSettings.reset(path="", python_include_paths=[str(package_dir)])
    sync_python_include_paths()
    try:
        block_file = tmp_path / "instruction_combine_loads_demo.py"
        block_file.write_text(
            "from loadtools import combine\n"
            "from polytess.core.instructions import Instruction\n"
            "from polytess.core.metadata import meta\n\n\n"
            "@meta(title='Combine Loads Demo',"
            " category='Custom/Combine Loads Demo')\n"
            "class CombineLoadsDemo(Instruction):\n"
            "    FIELD_HELP = {}\n\n"
            "    async def run(self, ctx):\n"
            "        ctx.info(combine('x'))\n", encoding="utf-8")
        module = load_custom_module(str(block_file))

        GlobalScope.reset()
        messages = []
        graph_stub = type("G", (), {"variables": None, "lists": None})()
        ctx = Context(graph=graph_stub,
                      logger=lambda level, m: messages.append(m))
        asyncio.run(module.CombineLoadsDemo().run(ctx))
        assert messages == ["combined:x"]
    finally:
        AppSettings.reset(path="", python_include_paths=[])
        sync_python_include_paths()
        sys.modules.pop("loadtools", None)
