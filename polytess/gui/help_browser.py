# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""In-app manual (Help → Manual, F1) — chapters rendered in the
winthirstudios.com design language: deep dark pages, card panels,
accent colors and the site's fonts (Outfit / Bricolage Grotesque,
bundled under assets/fonts)."""

from __future__ import annotations

import html
import os
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QLabel, QListWidget, QListWidgetItem,
                               QSplitter, QTextBrowser, QVBoxLayout, QWidget)

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "assets")
_HELP_DIR = os.path.join(_ASSETS, "help")

# website design tokens (winthirstudios.com/polytess.html)
_BG_DEEP = "#0a0d14"
_BG_MID = "#11151f"
_BG_CARD = "#161b27"
_LINE = "#232938"
_TEXT = "#dfe4ef"
_MUTED = "#8b94a8"
_DIM = "#525a6e"
_TEAL = "#4dd6c5"
_SKY = "#6cc7ff"
_VIOLET = "#8b7dff"
_MONO = "font-family: Menlo, Consolas, 'DejaVu Sans Mono', monospace;"

_BODY_FONT = "'Outfit', 'Segoe UI', sans-serif"
_HEAD_FONT = "'Bricolage Grotesque', 'Outfit', 'Segoe UI', sans-serif"
_fonts_loaded = False


def _load_fonts() -> None:
    """Register the bundled website fonts with Qt (once per process)."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    from PySide6.QtGui import QFontDatabase
    fonts_dir = os.path.join(_ASSETS, "fonts")
    for name in ("Outfit-Regular.ttf", "Outfit-SemiBold.ttf",
                 "BricolageGrotesque-Bold.ttf"):
        path = os.path.join(fonts_dir, name)
        if os.path.isfile(path):
            QFontDatabase.addApplicationFont(path)
    _fonts_loaded = True


def chapters() -> list[tuple[str, str]]:
    """(title, path) of every manual chapter, in file order."""
    out = []
    try:
        names = sorted(os.listdir(_HELP_DIR))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".md"):
            continue
        path = os.path.join(_HELP_DIR, name)
        with open(path, encoding="utf-8") as fh:
            first = fh.readline().strip()
        title = re.sub(r"^#+\s*", "", first) or name
        title = title.split("—")[0].strip()
        out.append((title, path))
    return out


# --------------------------------------------------------------------------- #
# markdown -> styled help HTML
# --------------------------------------------------------------------------- #

def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(
        r"`([^`\n]+)`",
        rf'<span style="{_MONO} font-size:13px; color:{_TEAL}; '
        rf'background-color:{_BG_MID};">&nbsp;\1&nbsp;</span>', text)
    text = re.sub(r"\*\*([^*\n]+)\*\*",
                  rf'<b style="color:#f1f3f8;">\1</b>', text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def _table_html(rows: list[list[str]]) -> str:
    parts = [f'<table width="100%" cellspacing="0" cellpadding="9" '
             f'style="margin: 10px 0 14px 0; background-color:{_BG_CARD};">']
    for index, cells in enumerate(rows):
        parts.append("<tr>")
        for cell in cells:
            if index == 0:
                parts.append(
                    f'<td style="background-color:{_BG_MID}; '
                    f'border-bottom: 2px solid {_LINE}; color:{_SKY}; '
                    f'font-size:13px;"><b>{_inline(cell)}</b></td>')
            else:
                parts.append(
                    f'<td style="border-bottom: 1px solid {_LINE}; '
                    f'color:{_MUTED}; font-size:13.5px;">'
                    f"{_inline(cell)}</td>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


def _code_block(lines: list[str]) -> str:
    code = html.escape("\n".join(lines))
    return (f'<table width="100%" cellspacing="0" cellpadding="12" '
            f'style="margin: 8px 0 14px 0;"><tr>'
            f'<td style="background-color:{_BG_MID}; '
            f'border: 1px solid {_LINE};">'
            f'<pre style="{_MONO} font-size:13px; color:{_TEAL}; '
            f'margin:0; white-space:pre-wrap;">{code}</pre>'
            f"</td></tr></table>")


def markdown_to_help_html(text: str) -> str:
    """Render a manual chapter to styled HTML (headings, pipe tables,
    lists, blockquotes, fenced and indented code blocks)."""
    out: list[str] = []
    lines = text.split("\n")
    index = 0
    list_open = False
    paragraph: list[str] = []

    def close_paragraph() -> None:
        if paragraph:
            out.append(f'<p style="font-size:14.5px; line-height:1.5; '
                       f'color:{_TEXT}; margin: 7px 0;">'
                       + " ".join(_inline(p) for p in paragraph) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            out.append("</ul>")
            list_open = False

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            close_paragraph(); close_list()
            block: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            out.append(_code_block(block))
            index += 1
            continue

        if line.startswith("    ") and stripped and not list_open \
                and not paragraph:
            close_list()
            block = []
            while index < len(lines) and (lines[index].startswith("    ")
                                          or not lines[index].strip()):
                if not lines[index].strip() and (
                        index + 1 >= len(lines)
                        or not lines[index + 1].startswith("    ")):
                    break
                block.append(lines[index][4:])
                index += 1
            while block and not block[-1].strip():
                block.pop()
            out.append(_code_block(block))
            continue

        if stripped.startswith("|") and index + 1 < len(lines) \
                and re.match(r"^\s*\|[\s\-|:]+\|\s*$", lines[index + 1]):
            close_paragraph(); close_list()
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [c.strip() for c in
                         lines[index].strip().strip("|").split("|")]
                if not re.match(r"^[\s\-:]+$", "".join(cells)):
                    rows.append(cells)
                index += 1
            out.append(_table_html(rows))
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            close_paragraph(); close_list()
            level = len(heading.group(1))
            title = heading.group(2)
            if level == 1:
                main, _, subtitle = title.partition("—")
                out.append(
                    f'<h1 style="font-family:{_HEAD_FONT}; font-size:27px; '
                    f'color:#f1f3f8; margin: 4px 0 2px 0;">'
                    f"{_inline(main.strip())}</h1>")
                if subtitle.strip():
                    out.append(f'<p style="font-size:15px; color:{_MUTED}; '
                               f'margin: 0 0 6px 0;">'
                               f"{_inline(subtitle.strip())}</p>")
                out.append(f'<table width="72" cellspacing="0" '
                           f'cellpadding="2" style="margin: 6px 0 16px 0;">'
                           f'<tr><td style="background-color:{_TEAL};">'
                           f"</td></tr></table>")
            elif level == 2:
                out.append(
                    f'<h2 style="font-family:{_HEAD_FONT}; font-size:17.5px; '
                    f'color:{_SKY}; margin: 20px 0 6px 0;">'
                    f"{_inline(title)}</h2>")
            else:
                out.append(
                    f'<h3 style="font-size:15px; color:{_TEAL}; '
                    f'margin: 14px 0 4px 0;">{_inline(title)}</h3>')
            index += 1
            continue

        if stripped.startswith(">"):
            close_paragraph(); close_list()
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip("> "))
                index += 1
            out.append(
                f'<table width="100%" cellspacing="0" cellpadding="10" '
                f'style="margin: 8px 0 12px 0;"><tr>'
                f'<td width="4" style="background-color:{_VIOLET};"></td>'
                f'<td style="background-color:{_BG_CARD}; font-size:14px; '
                f'color:{_MUTED};">{_inline(" ".join(quote))}</td>'
                f"</tr></table>")
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if bullet or numbered:
            close_paragraph()
            if not list_open:
                out.append('<ul style="margin: 6px 0 10px 0;">')
                list_open = True
            item = (bullet or numbered).group(1)
            out.append(f'<li style="font-size:14.5px; line-height:1.5; '
                       f'color:{_TEXT}; margin: 5px 0;">{_inline(item)}</li>')
            index += 1
            continue

        if not stripped:
            close_paragraph(); close_list()
        elif list_open:
            # continuation line of the previous bullet — append in place
            assert out and out[-1].endswith("</li>")
            out[-1] = out[-1][:-len("</li>")] + " " + _inline(stripped)                 + "</li>"
        else:
            paragraph.append(stripped)
        index += 1

    close_paragraph(); close_list()
    return (f'<div style="font-family:{_BODY_FONT}; color:{_TEXT};">'
            + "".join(out) + "</div>")


# --------------------------------------------------------------------------- #
# window
# --------------------------------------------------------------------------- #

class HelpWindow(QWidget):
    """Non-modal manual window with the website look."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        _load_fonts()
        self.setWindowTitle("polytess Manual")
        self.resize(980, 700)
        self.setStyleSheet(f"background-color: {_BG_DEEP};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {_LINE}; }}")
        layout.addWidget(splitter)

        sidebar = QWidget()
        sidebar.setStyleSheet(f"background-color: {_BG_MID};")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 16, 10, 12)
        brand = QLabel("polytess <span style='color:#4dd6c5;'>Manual</span>")
        brand.setStyleSheet(
            f"font-family: {_HEAD_FONT}; font-size: 17px; font-weight: bold; "
            f"color: #f1f3f8; background: transparent;")
        side_layout.addWidget(brand)
        side_layout.addSpacing(10)

        self.chapter_list = QListWidget()
        self.chapter_list.setFrameShape(QListWidget.NoFrame)
        self.chapter_list.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none;
                           font-family: {_BODY_FONT}; font-size: 13.5px;
                           color: {_MUTED}; outline: none; }}
            QListWidget::item {{ padding: 8px 10px; border-radius: 5px;
                                 margin: 1px 0; }}
            QListWidget::item:hover {{ background: {_BG_CARD}; }}
            QListWidget::item:selected {{ background: {_BG_CARD};
                                          color: {_TEAL}; }}""")
        self._paths: list[str] = []
        for number, (title, path) in enumerate(chapters(), start=1):
            QListWidgetItem(f"{number:02d}   {title}", self.chapter_list)
            self._paths.append(path)
        self.chapter_list.currentRowChanged.connect(self._show)
        side_layout.addWidget(self.chapter_list, 1)

        footer = QLabel("F1 opens this manual")
        footer.setStyleSheet(f"color: {_DIM}; font-size: 11px; "
                             f"background: transparent;")
        side_layout.addWidget(footer)
        splitter.addWidget(sidebar)

        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        self.viewer.setFrameShape(QTextBrowser.NoFrame)
        self.viewer.setStyleSheet(
            f"QTextBrowser {{ background-color: {_BG_DEEP}; border: none; "
            f"padding: 26px 34px 26px 30px; }}")
        splitter.addWidget(self.viewer)
        splitter.setSizes([250, 730])
        splitter.setCollapsible(0, False)

        if self._paths:
            self.chapter_list.setCurrentRow(0)

    def _show(self, row: int) -> None:
        if 0 <= row < len(self._paths):
            with open(self._paths[row], encoding="utf-8") as fh:
                self.viewer.setHtml(markdown_to_help_html(fh.read()))

    def open_chapter(self, index: int) -> None:
        self.chapter_list.setCurrentRow(index)
