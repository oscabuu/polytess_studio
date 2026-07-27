# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Reorderable polymorphic list — the Python counterpart of 's
TPolymorphicListTool / TPolymorphicItemTool (the Actions/Conditions editor).

Every row is a 22px head (drag handle · icon · dynamic title · breakpoint ·
disable · duplicate · delete) with an expandable body holding the item's
fields. Rows drag-reorder with a blue drop marker; right-click offers
Copy / Paste / Replace / Insert / Breakpoint / Disable / Collapse / Help.
"""

from __future__ import annotations

import json
from typing import Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QMenu, QMessageBox,
                               QPushButton, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)

from polytess.core.metadata import get_meta, iter_subclasses, resolve_type
from polytess.core.serialization import from_data, to_data
from polytess.gui.icons import icon
from polytess.gui.theme import ACCENTS, COLORS, ICON_SIZE, ROW_HEIGHT
from polytess.gui.type_selector import TypeSelectorPopup

_CLIP_KEY = "$polytess-clip"


def _clip_copy(item, base_name: str) -> None:
    payload = {_CLIP_KEY: base_name, "data": to_data(item)}
    QApplication.clipboard().setText(json.dumps(payload))


def _clip_paste(base_cls):
    try:
        payload = json.loads(QApplication.clipboard().text())
        if not isinstance(payload, dict) or _CLIP_KEY not in payload:
            return None
        item = from_data(payload["data"])
        cls = resolve_type(payload["data"].get("$type", ""))
        if isinstance(item, base_cls) or issubclass(cls, base_cls):
            return item
    except Exception:
        pass
    return None


class ItemRow(QWidget):

    def __init__(self, owner: "PolymorphicListWidget", item, index: int):
        super().__init__(owner)
        self.owner = owner
        self.item = item
        self.index = index

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- head (22px bar) ---------------------------------------------- #
        self.head = QFrame()
        self.head.setFixedHeight(ROW_HEIGHT)
        self.head.setCursor(Qt.PointingHandCursor)
        self._apply_head_style()
        head_layout = QHBoxLayout(self.head)
        head_layout.setContentsMargins(2, 0, 2, 0)
        head_layout.setSpacing(3)

        self.handle = QLabel()
        self.handle.setPixmap(icon("drag", "text-light").pixmap(ICON_SIZE, ICON_SIZE))
        self.handle.setCursor(Qt.SizeAllCursor)
        self.handle.setFixedWidth(ICON_SIZE + 2)
        self.handle.installEventFilter(owner)
        head_layout.addWidget(self.handle)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon(item.icon, item.color).pixmap(ICON_SIZE, ICON_SIZE))
        head_layout.addWidget(self.icon_label)

        self.title_label = QLabel()
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        head_layout.addWidget(self.title_label, 1)

        self.bp_label = QLabel()
        self.bp_label.setPixmap(icon("breakpoint", "red").pixmap(12, 12))
        self.bp_label.setToolTip("Breakpoint")
        head_layout.addWidget(self.bp_label)

        for name, tip, slot in (
                ("cancel", "Disable / Enable", self._toggle_enabled),
                ("duplicate", "Duplicate", self._duplicate),
                ("minus", "Delete", self._delete)):
            btn = QToolButton()
            btn.setIcon(icon(name, "text-light"))
            btn.setAutoRaise(True)
            btn.setToolTip(tip)
            btn.setFixedSize(18, 18)
            btn.clicked.connect(slot)
            head_layout.addWidget(btn)

        layout.addWidget(self.head)

        # ---- body ------------------------------------------------------------ #
        self.body = QFrame()
        self.body.setObjectName("itemBody")
        # scope to the body frame itself — a bare "QFrame" selector would also
        # box every QLabel inside (QLabel is a QFrame subclass)
        self.body.setStyleSheet(
            f"QFrame#itemBody {{ background: {COLORS['list-body']};"
            f" border: 1px solid {COLORS['border-default']}; border-top: none; }}"
            f"QFrame#itemBody QLabel {{ background: transparent; border: none; }}")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(10, 5, 7, 5)
        from polytess.gui.inspector.fields import build_fields_widget
        fields = build_fields_widget(item, self._on_fields_changed, graph=owner.graph)
        if fields is not None:
            body_layout.addWidget(fields)
        else:
            hint = QLabel("No editable fields")
            hint.setStyleSheet(f"color: {ACCENTS['text-light']}; border: none;")
            body_layout.addWidget(hint)
        layout.addWidget(self.body)

        self.head.installEventFilter(self)
        self.refresh()

    # ---- events ---------------------------------------------------------------- #

    def eventFilter(self, obj, event):
        if obj is self.head:
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._toggle_expanded()
                return True
            if event.type() == QEvent.ContextMenu:
                self._context_menu(event.globalPos())
                return True
        return super().eventFilter(obj, event)

    # ---- actions ------------------------------------------------------------------ #

    def _toggle_expanded(self) -> None:
        self.item._ui_expanded = not getattr(self.item, "_ui_expanded", False)
        self.refresh()

    def _toggle_enabled(self) -> None:
        self.item.is_enabled = not self.item.is_enabled
        self.refresh()
        self.owner.changed.emit()

    def _duplicate(self) -> None:
        self.owner.duplicate_item(self.index)

    def _delete(self) -> None:
        self.owner.delete_item(self.index)

    def _on_fields_changed(self) -> None:
        self.refresh()
        self.owner.changed.emit()

    def _context_menu(self, global_pos) -> None:
        menu = QMenu(self)
        menu.addAction("Copy", lambda: _clip_copy(self.item, self.owner.base_cls.__name__))
        paste = menu.addAction("Paste", lambda: self.owner.paste_item(self.index + 1))
        paste.setEnabled(_clip_paste(self.owner.base_cls) is not None)
        menu.addSeparator()
        menu.addAction("Replace…", lambda: self.owner.pick_type(
            lambda cls: self.owner.replace_item(self.index, cls())))
        menu.addAction("Insert Above…", lambda: self.owner.pick_type(
            lambda cls: self.owner.insert_item(self.index, cls())))
        menu.addAction("Insert Below…", lambda: self.owner.pick_type(
            lambda cls: self.owner.insert_item(self.index + 1, cls())))
        menu.addSeparator()
        bp = menu.addAction("Breakpoint")
        bp.setCheckable(True)
        bp.setChecked(self.item.breakpoint)
        bp.triggered.connect(self._toggle_breakpoint)
        menu.addAction("Enable" if not self.item.is_enabled else "Disable",
                       self._toggle_enabled)
        menu.addSeparator()
        menu.addAction("Collapse All", self.owner.collapse_all)
        menu.addAction("Expand All", self.owner.expand_all)
        menu.addSeparator()
        menu.addAction("Help", self._show_help)
        menu.exec(global_pos)

    def _toggle_breakpoint(self) -> None:
        self.item.breakpoint = not self.item.breakpoint
        self.refresh()
        self.owner.changed.emit()

    def _show_help(self) -> None:
        m = get_meta(type(self.item))
        text = f"<b>{m.title}</b>"
        if m.category:
            text += f"<br><i>{m.category}</i>"
        if m.description:
            text += f"<br><br>{m.description}"
        for pname, pdesc in m.parameters:
            text += f"<br>• <b>{pname}</b>: {pdesc}"
        QMessageBox.information(self, "Help", text)

    # ---- painting ---------------------------------------------------------------------- #

    def _apply_head_style(self, drop: str | None = None) -> None:
        expanded = getattr(self.item, "_ui_expanded", False) if hasattr(self, "item") else False
        bg = COLORS["list-head-expanded"] if expanded else COLORS["list-head"]
        border_top = f"2px solid {COLORS['border-active']}" if drop == "above" \
            else f"1px solid {COLORS['border-default']}"
        border_bottom = f"2px solid {COLORS['border-active']}" if drop == "below" \
            else f"1px solid {COLORS['border-default']}"
        self.head.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {COLORS['border-default']};"
            f" border-top: {border_top}; border-bottom: {border_bottom}; }}"
            f"QFrame:hover {{ background: {COLORS['list-head-hover']}; }}"
            f"QLabel {{ border: none; background: transparent; }}"
            f"QToolButton {{ border: none; background: transparent; }}")

    def set_drop_marker(self, position: str | None) -> None:
        self._apply_head_style(position)

    def set_dragged(self, dragging: bool) -> None:
        effect = QGraphicsOpacityEffect(self) if dragging else None
        if effect is not None:
            effect.setOpacity(0.25)
        self.setGraphicsEffect(effect)

    def refresh(self) -> None:
        # titles stay neutral — only the icon carries the thematic color
        color = ACCENTS["text"] if self.item.is_enabled else ACCENTS["text-light"]
        title = self.item.title
        if len(title) > 90:
            title = title[:87] + "…"
        self.title_label.setText(title)
        self.title_label.setStyleSheet(
            f"color: {color}; border: none; background: transparent;")
        self.icon_label.setPixmap(icon(self.item.icon, self.item.color)
                                  .pixmap(ICON_SIZE, ICON_SIZE))
        self.bp_label.setVisible(self.item.breakpoint)
        self.body.setVisible(getattr(self.item, "_ui_expanded", False))
        self._apply_head_style()
        opacity = QGraphicsOpacityEffect(self.head) if not self.item.is_enabled else None
        if opacity is not None:
            opacity.setOpacity(0.4)
        self.head.setGraphicsEffect(opacity)


class PolymorphicListWidget(QWidget):
    """The list tool: head bar + stacked rows + 'Add …' footer."""

    changed = Signal()

    def __init__(self, title: str, base_cls: type, items: list, graph=None,
                 favorites_key: str = "", direct_add_cls: type | None = None,
                 parent=None):
        super().__init__(parent)
        self.base_cls = base_cls
        self.items = items          # the *live* model list, mutated in place
        self.graph = graph
        self.favorites_key = favorites_key
        self.direct_add_cls = direct_add_cls
        self._rows: list[ItemRow] = []
        self._drag_row: ItemRow | None = None
        self._drop_index: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QFrame()
        head.setFixedHeight(20)
        head.setStyleSheet(
            f"QFrame {{ background: {COLORS['list-head']};"
            f" border: 1px solid {COLORS['border-default']};"
            f" border-top-left-radius: 3px; border-top-right-radius: 3px; }}"
            f"QLabel {{ border: none; background: transparent;"
            f" color: {ACCENTS['text-light']}; }}")
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(6, 0, 6, 0)
        self._head_label = QLabel(title)
        head_layout.addWidget(self._head_label)
        head_layout.addStretch(1)
        self._count_label = QLabel("")
        head_layout.addWidget(self._count_label)
        layout.addWidget(head)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        layout.addWidget(self.rows_container)

        foot = QFrame()
        foot.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg-dark']};"
            f" border: 1px solid {COLORS['border-default']}; border-top: none;"
            f" border-bottom-left-radius: 3px; border-bottom-right-radius: 3px; }}")
        foot_layout = QHBoxLayout(foot)
        foot_layout.setContentsMargins(4, 3, 4, 3)
        label = get_meta(base_cls).title if get_meta(base_cls).title else base_cls.__name__
        self.add_button = QPushButton(f"  Add {label}…")
        self.add_button.setIcon(icon("plus", "text-light"))
        self.add_button.clicked.connect(self._add_clicked)
        foot_layout.addWidget(self.add_button, 1)
        paste_btn = QToolButton()
        paste_btn.setIcon(icon("duplicate", "text-light"))
        paste_btn.setToolTip("Paste")
        paste_btn.setAutoRaise(True)
        paste_btn.clicked.connect(lambda: self.paste_item(len(self.items)))
        foot_layout.addWidget(paste_btn)
        layout.addWidget(foot)

        self.rebuild()

    # ---- structure edits ------------------------------------------------------- #

    def pick_type(self, on_pick: Callable[[type], None]) -> None:
        if self.direct_add_cls is not None:
            on_pick(self.direct_add_cls)
            return
        candidates = list(iter_subclasses(self.base_cls))
        popup = TypeSelectorPopup(candidates, on_pick, parent=self.window(),
                                  favorites_key=self.favorites_key)
        popup.open_at(QCursor.pos())

    def _add_clicked(self) -> None:
        self.pick_type(lambda cls: self.insert_item(len(self.items), cls()))

    def insert_item(self, index: int, item) -> None:
        item._ui_expanded = True
        self.items.insert(index, item)
        self.rebuild()
        self.changed.emit()

    def replace_item(self, index: int, item) -> None:
        item._ui_expanded = True
        self.items[index] = item
        self.rebuild()
        self.changed.emit()

    def duplicate_item(self, index: int) -> None:
        clone = self.items[index].copy()
        self.items.insert(index + 1, clone)
        self.rebuild()
        self.changed.emit()

    def delete_item(self, index: int) -> None:
        del self.items[index]
        self.rebuild()
        self.changed.emit()

    def paste_item(self, index: int) -> None:
        item = _clip_paste(self.base_cls)
        if item is not None:
            self.insert_item(min(index, len(self.items)), item)

    def collapse_all(self) -> None:
        for item in self.items:
            item._ui_expanded = False
        self.rebuild()

    def expand_all(self) -> None:
        for item in self.items:
            item._ui_expanded = True
        self.rebuild()

    # ---- rebuild ------------------------------------------------------------------ #

    def rebuild(self) -> None:
        while self.rows_layout.count():
            child = self.rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._rows = []
        for index, item in enumerate(self.items):
            row = ItemRow(self, item, index)
            self._rows.append(row)
            self.rows_layout.addWidget(row)
        self._count_label.setText(str(len(self.items)) if self.items else "empty")

    # ---- drag reorder (event filter installed on row handles) --------------------- #

    def eventFilter(self, obj, event):
        row = None
        for candidate in self._rows:
            if candidate.handle is obj:
                row = candidate
                break
        if row is None:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_row = row
            row.set_dragged(True)
            return True
        if event.type() == QEvent.MouseMove and self._drag_row is not None:
            self._update_drop_marker(event.globalPosition().toPoint())
            return True
        if event.type() == QEvent.MouseButtonRelease and self._drag_row is not None:
            src = self._drag_row.index
            dst = self._drop_index
            self._drag_row.set_dragged(False)
            self._drag_row = None
            self._clear_markers()
            if dst is not None and dst != src and dst != src + 1:
                item = self.items.pop(src)
                if dst > src:
                    dst -= 1
                self.items.insert(dst, item)
                self.rebuild()
                self.changed.emit()
            self._drop_index = None
            return True
        return super().eventFilter(obj, event)

    def _update_drop_marker(self, global_pos) -> None:
        self._clear_markers()
        self._drop_index = None
        for row in self._rows:
            top_left = row.mapToGlobal(row.rect().topLeft())
            middle = top_left.y() + row.head.height() / 2
            if global_pos.y() < middle:
                row.set_drop_marker("above")
                self._drop_index = row.index
                return
        if self._rows:
            self._rows[-1].set_drop_marker("below")
            self._drop_index = len(self.items)

    def _clear_markers(self) -> None:
        for row in self._rows:
            row.set_drop_marker(None)
