# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Viewer additions to the Studio stylesheet — calmer, larger, one accent."""

from __future__ import annotations

from polytess.gui.theme import ACCENTS, COLORS

STATUS_FILL = {            # card accent per board status
    "pending": "#5a5a5a",
    "queued": "#6b571a",
    "active": "#3d7ad9",
    "done": "#519932",
    "failed": "#b03a3a",
    "stale": "#8a6d1f",
}
STATUS_LABEL = {
    "pending": "Backlog", "queued": "Queued", "active": "Running",
    "done": "Done", "failed": "Failed", "stale": "Outdated",
}


def viewer_qss() -> str:
    return f"""
QWidget {{ font-size: 13px; }}
QLabel#title {{ font-size: 22px; font-weight: 600; }}
QLabel#subtitle {{ font-size: 13px; color: {ACCENTS['text-light']}; }}
QLabel#section {{ font-size: 14px; font-weight: 600; color: {ACCENTS['blue']};
                  padding-top: 8px; }}
QLabel#hint {{ color: {ACCENTS['text-light']}; font-size: 12px; }}
QLabel#error {{ color: {ACCENTS['red']}; }}
QPushButton#primary {{
    background: {COLORS['border-active']}; color: white; font-weight: 600;
    padding: 8px 22px; border-radius: 6px; font-size: 14px; border: none;
}}
QPushButton#primary:disabled {{ background: {COLORS['bg-lightest']};
                                color: {ACCENTS['text-light']}; }}
QPushButton#primary:hover {{ background: #4d8ae9; }}
QPushButton#danger {{ background: {COLORS['error']}; color: white;
                      padding: 6px 16px; border-radius: 6px; border: none; }}
QPushButton#flat {{ background: transparent; border: 1px solid {COLORS['border-hover']};
                    padding: 6px 14px; border-radius: 6px; }}
QPushButton#flat:hover {{ background: {COLORS['bg-lighter']}; }}
QFrame#card {{ background: {COLORS['bg-dark']}; border: 1px solid {COLORS['border-element']};
               border-radius: 8px; }}
QFrame#panel {{ background: {COLORS['bg-dark']}; border-radius: 8px; }}
QLineEdit[invalid="true"], QDoubleSpinBox[invalid="true"],
QSpinBox[invalid="true"], QComboBox[invalid="true"] {{
    border: 1px solid {ACCENTS['red']};
}}
QProgressBar {{ border: none; border-radius: 4px; background: {COLORS['bg-darkest']};
                height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {COLORS['border-active']}; border-radius: 4px; }}
"""


# ---- board colour themes (Viewer setting "viewer_board_theme") --------------- #
# column_body / column_head are per column (backlog, active, done);
# card_fill per status ("" = neutral dark card), card_border, head_text.

BOARD_THEMES: dict[str, dict] = {
    "classic": {            # as shipped in 1.18: neutral dark columns, stripe only
        "label": "Classic — neutral columns, colour stripe on the card",
        "column_body": {"backlog": "#2a2a2a", "active": "#2a2a2a", "done": "#2a2a2a"},
        "column_head": {"backlog": "#333333", "active": "#333333", "done": "#333333"},
        "head_text": {"backlog": "#ffffff", "active": "#ffffff", "done": "#ffffff"},
        "card_fill": {}, "card_border": "#303030", "stripe": 6,
    },
    "tinted": {             # each column softly tinted in its meaning
        "label": "Tinted — columns softly coloured (grey → blue → green)",
        "column_body": {"backlog": "#2c2c2e", "active": "#22303f", "done": "#23321f"},
        "column_head": {"backlog": "#3a3a3d", "active": "#2b4a6b", "done": "#2f5b2a"},
        "head_text": {"backlog": "#ffffff", "active": "#ffffff", "done": "#ffffff"},
        "card_fill": {}, "card_border": "#3a3a3a", "stripe": 6,
    },
    "headers": {            # strong solid column headers, neutral bodies
        "label": "Headers — solid coloured column headers",
        "column_body": {"backlog": "#2a2a2a", "active": "#2a2a2a", "done": "#2a2a2a"},
        "column_head": {"backlog": "#5a5a5a", "active": "#3d7ad9", "done": "#519932"},
        "head_text": {"backlog": "#ffffff", "active": "#ffffff", "done": "#ffffff"},
        "card_fill": {}, "card_border": "#303030", "stripe": 8,
    },
    "cards": {              # the cards themselves carry their status colour
        "label": "Cards — cards filled in a dark shade of their status",
        "column_body": {"backlog": "#2a2a2a", "active": "#2a2a2a", "done": "#2a2a2a"},
        "column_head": {"backlog": "#333333", "active": "#333333", "done": "#333333"},
        "head_text": {"backlog": "#ffffff", "active": "#ffffff", "done": "#ffffff"},
        "card_fill": {"pending": "#353535", "queued": "#3d3620", "active": "#1f3552",
                      "done": "#213d1e", "failed": "#4a2020", "stale": "#403516"},
        "card_border": "#444444", "stripe": 6,
    },
    "vivid": {              # tinted columns + coloured headers + card fills
        "label": "Vivid — tinted columns, coloured headers and cards",
        "column_body": {"backlog": "#2e2e30", "active": "#1f2d3d", "done": "#1f2f1c"},
        "column_head": {"backlog": "#5a5a5a", "active": "#3d7ad9", "done": "#519932"},
        "head_text": {"backlog": "#ffffff", "active": "#ffffff", "done": "#ffffff"},
        "card_fill": {"pending": "#383838", "queued": "#45391c", "active": "#243f61",
                      "done": "#254a21", "failed": "#5a2424", "stale": "#4a3d18"},
        "card_border": "#4a4a4a", "stripe": 8,
    },
}


def board_theme(name: str | None = None) -> dict:
    from polytess.core.app_settings import AppSettings
    key = name or str(AppSettings.instance().get("viewer_board_theme") or "classic")
    return BOARD_THEMES.get(key, BOARD_THEMES["classic"])
