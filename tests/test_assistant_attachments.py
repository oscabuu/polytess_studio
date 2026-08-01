# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Prompt attachments (+ button) for both assistant panels."""

import pytest

from polytess.gui.code_assistant import (MAX_ATTACHMENT_BYTES,
                                         format_attachments, read_attachment)


def test_read_attachment_text(tmp_path):
    path = tmp_path / "deck.inp"
    path.write_text("*NODE\n1, 0, 0, 0\n", encoding="utf-8")
    name, text = read_attachment(str(path))
    assert name == "deck.inp" and "*NODE" in text


def test_read_attachment_rejects_binary(tmp_path):
    path = tmp_path / "model.odb"
    path.write_bytes(b"\x00\x01\x02binary")
    with pytest.raises(ValueError, match="binary"):
        read_attachment(str(path))


def test_read_attachment_rejects_oversize(tmp_path):
    path = tmp_path / "big.txt"
    path.write_bytes(b"x" * (MAX_ATTACHMENT_BYTES + 1))
    with pytest.raises(ValueError, match="too large"):
        read_attachment(str(path))


def test_format_attachments():
    blocks = format_attachments([("a.inp", "AAA"), ("b.py", "BBB")])
    assert '<attached_file name="a.inp">' in blocks
    assert "AAA" in blocks and "BBB" in blocks
    assert blocks.index("a.inp") < blocks.index("b.py")


def test_attachment_bar_take_clears(tmp_path, qt_app):
    from polytess.gui.code_assistant import AttachmentBar
    bar = AttachmentBar()
    path = tmp_path / "x.py"
    path.write_text("print(1)\n", encoding="utf-8")
    bar.add_path(str(path))
    bar.add_path(str(path))          # same name replaces, no duplicate
    assert bar.names == ["x.py"]
    assert bar.clear_button.isVisibleTo(bar)
    taken = bar.take()
    assert [name for name, _ in taken] == ["x.py"]
    assert bar.names == [] and not bar.clear_button.isVisibleTo(bar)


@pytest.fixture(scope="module")
def qt_app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])
