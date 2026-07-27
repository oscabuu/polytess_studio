# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Type-selector popup — searchable "Add …" menu.

A frameless popup with a search field on top, a paged category list in the
middle (folders navigate like sliding pages, with a back header) and
a live description footer. Favorites (starred via context menu) appear at
the root. Used for "Add Instruction…", "Add Condition…", property-source
dropdowns and the node-create menu.
"""

from __future__ import annotations

from typing import Callable, Sequence

from PySide6.QtCore import QPoint, QSettings, QSize, Qt, Signal
from PySide6.QtWidgets import (QFrame, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QVBoxLayout)

from polytess.core.metadata import CategoryNode, get_meta, levenshtein
from polytess.gui.icons import icon
from polytess.gui.theme import COLORS

_ROLE_KIND = Qt.UserRole          # "folder" | "entry" | "back"
_ROLE_PAYLOAD = Qt.UserRole + 1


def _search(candidates: Sequence[type], query: str) -> list[type]:
    query = query.strip().lower()
    scored = []
    for cls in candidates:
        m = get_meta(cls)
        tokens = [(m.title.lower(), 10)]
        tokens += [(seg.lower(), 8) for seg in m.category.split("/") if seg]
        tokens += [(k.lower(), 7) for k in m.keywords]
        tokens += [(w, 2) for w in m.description.lower().split()[:20]]
        best = 0.0
        for token, prio in tokens:
            if query == token:
                best = max(best, prio * 3.0)
            elif token.startswith(query):
                best = max(best, prio * 2.0)
            elif query in token:
                best = max(best, prio * 1.5)
            else:
                for word in token.split():
                    dist = levenshtein(query, word)
                    if dist <= max(1, len(query) // 3):
                        best = max(best, prio * (1.0 - dist / max(len(word), 1)))
        if best > 0:
            scored.append((best, m.title.lower(), cls))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [cls for _, _, cls in scored[:60]]


def _build_tree(candidates: Sequence[type]) -> CategoryNode:
    root = CategoryNode("")
    for cls in candidates:
        node = root
        for folder in get_meta(cls).category_folders:
            node = node.folders.setdefault(folder, CategoryNode(folder))
        node.entries.append(cls)
    # a single top-level folder (e.g. every node type under "Nodes") is a
    # pointless extra click — descend into it automatically
    while not root.entries and len(root.folders) == 1:
        root = next(iter(root.folders.values()))
    return root


class TypeSelectorPopup(QFrame):
    """popup(candidates, on_pick).open_at(global_pos)"""

    picked = Signal(object)   # the chosen class

    def __init__(self, candidates: Sequence[type], on_pick: Callable[[type], None],
                 parent=None, favorites_key: str = ""):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._candidates = [c for c in candidates if not get_meta(c).hidden]
        self._on_pick = on_pick
        self._root = _build_tree(self._candidates)
        self._page_stack: list[CategoryNode] = [self._root]
        self._favorites_key = favorites_key
        self._settings = QSettings("polytess", "studio")

        self.setFixedSize(QSize(300, 420))
        self.setStyleSheet(
            f"TypeSelectorPopup {{ border: 1px solid {COLORS['border-hover']};"
            f" background: {COLORS['bg-dark']}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.textChanged.connect(self._refresh)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.listing = QListWidget()
        self.listing.setFrameShape(QFrame.NoFrame)
        self.listing.setUniformItemSizes(True)
        self.listing.itemActivated.connect(self._activate)
        self.listing.itemClicked.connect(self._activate)
        self.listing.currentItemChanged.connect(self._update_footer)
        self.listing.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listing.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.listing, 1)

        self.footer = QLabel("")
        self.footer.setWordWrap(True)
        self.footer.setMinimumHeight(52)
        self.footer.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.footer.setStyleSheet(
            f"QLabel {{ background: {COLORS['bg-darkest']}; padding: 6px;"
            f" color: #bbbbbb; border-top: 1px solid {COLORS['border-element']}; }}")
        layout.addWidget(self.footer)

        self._refresh()

    # ---- favorites ---------------------------------------------------------- #

    def _fav_names(self) -> list[str]:
        if not self._favorites_key:
            return []
        raw = self._settings.value(f"favorites/{self._favorites_key}", "")
        return [n for n in str(raw).split(";") if n]

    def _toggle_favorite(self, cls: type) -> None:
        names = self._fav_names()
        name = cls.__name__
        if name in names:
            names.remove(name)
        else:
            names.append(name)
        self._settings.setValue(f"favorites/{self._favorites_key}", ";".join(names))
        self._refresh()

    # ---- pages ----------------------------------------------------------------- #

    def _current_page(self) -> CategoryNode:
        return self._page_stack[-1]

    def _refresh(self) -> None:
        self.listing.clear()
        query = self.search.text().strip()
        if query:
            for cls in _search(self._candidates, query):
                self._add_entry(cls)
        else:
            page = self._current_page()
            if len(self._page_stack) > 1:
                back = QListWidgetItem(icon("chevron-left", "text-light"),
                                       f"  {page.name}")
                back.setData(_ROLE_KIND, "back")
                font = back.font(); font.setBold(True); back.setFont(font)
                self.listing.addItem(back)
            if page is self._root and self._favorites_key:
                favs = self._fav_names()
                for cls in self._candidates:
                    if cls.__name__ in favs:
                        self._add_entry(cls, star=True)
            for folder in page.sorted_folders():
                item = QListWidgetItem(icon("folder", "text-light"), folder.name)
                item.setData(_ROLE_KIND, "folder")
                item.setData(_ROLE_PAYLOAD, folder)
                self.listing.addItem(item)
            for cls in page.sorted_entries():
                self._add_entry(cls)
        if self.listing.count():
            self.listing.setCurrentRow(0)

    def _add_entry(self, cls: type, star: bool = False) -> None:
        m = get_meta(cls)
        label = ("★ " if star else "") + m.title
        item = QListWidgetItem(icon(m.icon, m.color), label)
        item.setData(_ROLE_KIND, "entry")
        item.setData(_ROLE_PAYLOAD, cls)
        self.listing.addItem(item)

    def _activate(self, item: QListWidgetItem) -> None:
        kind = item.data(_ROLE_KIND)
        if kind == "back":
            self._page_stack.pop()
            self._refresh()
        elif kind == "folder":
            self._page_stack.append(item.data(_ROLE_PAYLOAD))
            self._refresh()
        elif kind == "entry":
            cls = item.data(_ROLE_PAYLOAD)
            self.close()
            self._on_pick(cls)

    def _update_footer(self, current: QListWidgetItem | None, _prev=None) -> None:
        if current is None or current.data(_ROLE_KIND) != "entry":
            self.footer.setText("")
            return
        m = get_meta(current.data(_ROLE_PAYLOAD))
        parts = [f"<b>{m.title}</b>"]
        if m.category:
            parts.append(f"<span style='color:#888888'>{m.category}</span>")
        if m.description:
            parts.append(m.description)
        self.footer.setText("<br>".join(parts))

    def _context_menu(self, pos: QPoint) -> None:
        item = self.listing.itemAt(pos)
        if item is None or item.data(_ROLE_KIND) != "entry" or not self._favorites_key:
            return
        cls = item.data(_ROLE_PAYLOAD)
        menu = QMenu(self)
        in_favs = cls.__name__ in self._fav_names()
        action = menu.addAction("Remove from favorites" if in_favs else "Add to favorites")
        action.triggered.connect(lambda: self._toggle_favorite(cls))
        menu.exec(self.listing.mapToGlobal(pos))

    # ---- keyboard: arrows navigate list while typing --------------------------- #

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.search and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Down, Qt.Key_Up):
                self.listing.setFocus()
                self.listing.keyPressEvent(event)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                current = self.listing.currentItem()
                if current is not None:
                    self._activate(current)
                return True
            if key == Qt.Key_Backspace and not self.search.text() and len(self._page_stack) > 1:
                self._page_stack.pop()
                self._refresh()
                return True
        return super().eventFilter(obj, event)

    # ---- open ------------------------------------------------------------------- #

    def open_at(self, global_pos: QPoint) -> None:
        screen = self.screen().availableGeometry() if self.screen() else None
        x, y = global_pos.x(), global_pos.y()
        if screen is not None:
            x = min(x, screen.right() - self.width())
            y = min(y, screen.bottom() - self.height())
        self.move(max(0, x), max(0, y))
        self.show()
        self.search.setFocus()
