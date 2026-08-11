# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Chat transcript view shared by the assistant panels.

Renders a conversation as styled HTML in a QTextBrowser: user questions and
assistant answers get distinct bubbles, fenced code blocks become dark boxes
with syntax highlighting, and typography is deliberately generous (larger
font, breathing room) so longer answers stay readable.

The markdown subset covers what the assistants actually produce: fenced
code blocks, inline code, bold/italic, headings, bullet/numbered lists and
paragraphs. Everything else is escaped verbatim.
"""

from __future__ import annotations

import html
import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTextBrowser

from polytess.gui.theme import ACCENTS, COLORS

# ---- palette ---------------------------------------------------------------- #

_USER_BG = "#243447"          # calm blue-tinted bubble for questions
_ASSISTANT_BG = COLORS["bg-dark"]
_ERROR_BG = "#4a2622"
_CODE_BG = "#141414"
_CODE_BORDER = COLORS["border-element"]
_TEXT = "#e8e8e8"
_MUTED = ACCENTS["text-light"]

_FONT = "font-size: 14px;"
_MONO = "font-family: Menlo, Consolas, 'DejaVu Sans Mono', monospace; font-size: 13px;"

# ---- syntax highlighting (HTML spans) ---------------------------------------- #

_PY_KEYWORDS = (
    "False None True and as assert async await break class continue def del "
    "elif else except finally for from global if import in is lambda nonlocal "
    "not or pass raise return try while with yield match case").split()

_PY_RULES = [
    ("comment", re.compile(r"#[^\n]*")),
    ("string", re.compile(
        r"[rbf]*('''.*?'''|\"\"\".*?\"\"\"|'[^'\n]*'|\"[^\"\n]*\")",
        re.DOTALL | re.IGNORECASE)),
    ("decorator", re.compile(r"@[A-Za-z_][\w.]*")),
    ("defname", re.compile(r"\b(?:def|class)\s+[A-Za-z_]\w*")),
    ("keyword", re.compile(r"\b(?:%s)\b" % "|".join(_PY_KEYWORDS))),
    ("number", re.compile(r"\b\d[\d_]*(?:\.\d+)?(?:e[+-]?\d+)?\b",
                          re.IGNORECASE)),
]

_PY_COLORS = {
    "comment": "#7a9e6d",
    "string": ACCENTS["green"],
    "decorator": ACCENTS["yellow"],
    "defname": ACCENTS["blue"],
    "keyword": ACCENTS["purple"],
    "number": ACCENTS["teal"],
}

_JSON_RULES = [
    ("key", re.compile(r"\"[^\"\n]*\"(?=\s*:)")),
    ("string", re.compile(r"\"[^\"\n]*\"")),
    ("keyword", re.compile(r"\b(?:true|false|null)\b")),
    ("number", re.compile(r"-?\b\d+(?:\.\d+)?(?:e[+-]?\d+)?\b", re.IGNORECASE)),
]

_JSON_COLORS = {
    "key": ACCENTS["blue"],
    "string": ACCENTS["green"],
    "keyword": ACCENTS["purple"],
    "number": ACCENTS["teal"],
}


def _highlight(code: str, rules, colors) -> str:
    """Escaped HTML with color spans; overlapping matches: first rule wins."""
    matches: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for kind, pattern in rules:
        for m in pattern.finditer(code):
            span = (m.start(), m.end())
            if any(s < span[1] and span[0] < e for s, e in taken):
                continue
            matches.append((*span, kind))
            taken.append(span)
    matches.sort()
    out, pos = [], 0
    for start, end, kind in matches:
        out.append(html.escape(code[pos:start]))
        out.append(f'<span style="color:{colors[kind]};">'
                   f"{html.escape(code[start:end])}</span>")
        pos = end
    out.append(html.escape(code[pos:]))
    return "".join(out)


def highlight_code(code: str, language: str = "") -> str:
    language = language.lower()
    if language in ("python", "py"):
        return _highlight(code, _PY_RULES, _PY_COLORS)
    if language in ("json",):
        return _highlight(code, _JSON_RULES, _JSON_COLORS)
    return html.escape(code)


# ---- markdown subset -> HTML -------------------------------------------------- #

def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`\n]+)`",
                  rf'<span style="{_MONO} background-color:{_CODE_BG};">'
                  r"&nbsp;\1&nbsp;</span>", text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def markdown_to_html(text: str) -> str:
    """Render the assistant-markdown subset; code fences become dark
    highlighted boxes."""
    parts: list[str] = []
    pos = 0
    fence = re.compile(r"```([A-Za-z0-9_+-]*)[ \t]*\n(.*?)(?:```|\Z)", re.DOTALL)
    for m in fence.finditer(text):
        parts.append(_prose_to_html(text[pos:m.start()]))
        language, code = m.group(1), m.group(2).rstrip("\n")
        parts.append(
            f'<table width="100%" cellspacing="0" cellpadding="10" '
            f'style="margin-top:8px; margin-bottom:8px;"><tr>'
            f'<td style="background-color:{_CODE_BG}; '
            f'border:1px solid {_CODE_BORDER};">'
            f'<pre style="{_MONO} margin:0; white-space:pre-wrap;">'
            f"{highlight_code(code, language)}</pre></td></tr></table>")
        pos = m.end()
    parts.append(_prose_to_html(text[pos:]))
    return "".join(parts)


def _prose_to_html(text: str) -> str:
    out: list[str] = []
    list_open = False

    def close_list():
        nonlocal list_open
        if list_open:
            out.append("</ul>")
            list_open = False

    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            close_list()
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if heading:
            close_list()
            out.append(f'<p style="{_FONT} margin:10px 0 4px 0;">'
                       f"<b>{_inline(heading.group(2))}</b></p>")
        elif bullet or numbered:
            if not list_open:
                out.append('<ul style="margin:4px 0 4px 0;">')
                list_open = True
            item = (bullet or numbered).group(1)
            out.append(f'<li style="{_FONT} margin:3px 0;">{_inline(item)}</li>')
        else:
            close_list()
            out.append(f'<p style="{_FONT} margin:6px 0;">{_inline(stripped)}</p>')
    close_list()
    return "".join(out)


# ---- transcript view ---------------------------------------------------------- #

_ROLE_STYLE = {
    "user": (_USER_BG, ACCENTS["blue"], "You"),
    "assistant": (_ASSISTANT_BG, ACCENTS["teal"], "Claude"),
    "error": (_ERROR_BG, ACCENTS["red"], "Error"),
}


def transcript_to_html(transcript: list[tuple[str, str]]) -> str:
    """The full conversation as one HTML document body."""
    bubbles: list[str] = []
    for role, text in transcript:
        bg, label_color, label = _ROLE_STYLE.get(role, _ROLE_STYLE["assistant"])
        if role == "assistant":
            body = markdown_to_html(text) if text else \
                f'<p style="{_FONT} margin:6px 0; color:{_MUTED};">…</p>'
        else:
            body = _prose_to_html(text)
        bubbles.append(
            f'<table width="100%" cellspacing="0" cellpadding="10" '
            f'style="margin-top:10px;"><tr>'
            f'<td style="background-color:{bg};">'
            f'<p style="font-size:11px; margin:0 0 4px 0;">'
            f'<b style="color:{label_color};">{label}</b></p>'
            f"{body}</td></tr></table>")
    return (f'<div style="color:{_TEXT}; {_FONT}">' + "".join(bubbles) + "</div>")


class ChatView(QTextBrowser):
    """Read-only conversation display with bubble styling.

    While an answer streams in, the view follows the end of the text;
    scrolling up detaches it (so earlier parts can be read), scrolling
    back to the bottom re-attaches it.

    Attach/detach reacts ONLY to real user input (wheel, dragging the
    scrollbar handle, scroll-arrow/page clicks, keys) — never to
    programmatic ``valueChanged``: ``setHtml`` resets the scrollbar and
    lays out asynchronously, so value-based detection would randomly
    lose the bottom mid-stream. While detached, the reading position is
    restored after every re-render instead of being yanked to the top."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self.setStyleSheet(
            f"QTextBrowser {{ background: {COLORS['bg-darkest']};"
            f" border: 1px solid {COLORS['border-element']};"
            f" padding: 4px; }}")
        self._stick_to_bottom = True
        self._held_value = 0            # reading position while detached
        bar = self.verticalScrollBar()
        bar.rangeChanged.connect(lambda *_: self._apply_position())
        bar.sliderMoved.connect(self._sync_stick_from_user)
        # arrow/page/groove clicks: the value updates after the signal,
        # so evaluate on the next event-loop pass
        bar.actionTriggered.connect(
            lambda _action: QTimer.singleShot(0, self._sync_stick))

    # ---- user intent --------------------------------------------------------- #

    def wheelEvent(self, event):         # noqa: N802 (Qt API)
        super().wheelEvent(event)
        self._sync_stick()

    def keyPressEvent(self, event):      # noqa: N802 (Qt API)
        super().keyPressEvent(event)
        self._sync_stick()

    def _sync_stick(self) -> None:
        self._sync_stick_from_user(self.verticalScrollBar().value())

    def _sync_stick_from_user(self, value: int) -> None:
        bar = self.verticalScrollBar()
        self._stick_to_bottom = value >= bar.maximum() - 40
        self._held_value = value

    # ---- rendering ----------------------------------------------------------- #

    def _apply_position(self) -> None:
        """Pin to the bottom, or restore the detached reading position
        (also called on late layout growth via rangeChanged)."""
        bar = self.verticalScrollBar()
        if self._stick_to_bottom:
            bar.setValue(bar.maximum())
        else:
            bar.setValue(min(self._held_value, bar.maximum()))

    def set_transcript(self, transcript: list[tuple[str, str]]) -> None:
        self.setHtml(transcript_to_html(transcript))
        self._apply_position()
