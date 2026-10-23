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
