# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Viewer main window: start page (recent flows, open) → form page or
board page, depending on whether the flow has sub-workflow cards."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QPushButton, QSizePolicy,
                               QStackedWidget, QToolBar, QVBoxLayout, QWidget)

from polytess import __version__
from polytess.core.app_settings import AppSettings
from polytess.graph.board import board_spec
from polytess.graph.model import Graph
from polytess.viewer import celebrations
from polytess.viewer.board_page import BoardPage
from polytess.viewer.form_page import FormPage

MAX_RECENT = 12


class StartPage(QWidget):

    def __init__(self, window: "ViewerWindow", parent=None):
        super().__init__(parent)
        self._window = window
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 48, 60, 48)
        layout.setSpacing(12)
        title = QLabel("polytess Viewer")
        title.setObjectName("title")
        layout.addWidget(title)
        sub = QLabel("Open a flow, fill in its inputs and start it. A main process "
                     "with sub-workflows opens as a board.")
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)
        open_button = QPushButton("Open flow…")
        open_button.setObjectName("primary")
        open_button.setFixedWidth(180)
        open_button.clicked.connect(window.open_dialog)
        layout.addWidget(open_button)
        recent_head = QLabel("Recent")
        recent_head.setObjectName("section")
        layout.addWidget(recent_head)
        self.recent = QListWidget()
        self.recent.itemActivated.connect(
            lambda item: window.open_flow(item.data(Qt.UserRole)))
        layout.addWidget(self.recent, 1)
        hint = QLabel("Tip: drop a .flow.json anywhere on this window.")
        hint.setObjectName("hint")
        layout.addWidget(hint)
        self.refresh()

    def refresh(self) -> None:
        self.recent.clear()
        for path in AppSettings.instance().get("viewer_recent") or []:
            if not os.path.isfile(path):
                continue
            item = QListWidgetItem(f"{os.path.basename(path)}    {os.path.dirname(path)}")
            item.setData(Qt.UserRole, path)
            self.recent.addItem(item)


class ViewerWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"polytess Viewer {__version__}")
        self.resize(1240, 820)
        self.statusBar()
        self.setAcceptDrops(True)
        self._page: QWidget | None = None

        bar = QToolBar("Main")
        bar.setMovable(False)
        self.addToolBar(bar)
        home = QPushButton("Start")
        home.setObjectName("flat")
        home.clicked.connect(self.show_start)
        bar.addWidget(home)
        open_button = QPushButton("Open…")
        open_button.setObjectName("flat")
        open_button.clicked.connect(self.open_dialog)
        bar.addWidget(open_button)
        phone_button = QPushButton("Phone…")
        phone_button.setObjectName("flat")
        phone_button.setToolTip("Follow the board on your phone (QR code)")
        phone_button.clicked.connect(self.share_on_phone)
        bar.addWidget(phone_button)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(spacer)
        bar.addWidget(QLabel("Board "))
        self.theme_box = QComboBox()
        from polytess.viewer.style import BOARD_THEMES
        for key, theme in BOARD_THEMES.items():
            self.theme_box.addItem(key.capitalize(), key)
            self.theme_box.setItemData(self.theme_box.count() - 1, theme["label"],
                                       Qt.ToolTipRole)
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(
            str(AppSettings.instance().get("viewer_board_theme") or "classic"))))
        self.theme_box.currentIndexChanged.connect(lambda _i: self._set_board_theme())
        bar.addWidget(self.theme_box)
        bar.addWidget(QLabel("   Celebrations "))
        self.celebration_box = QComboBox()
        for level in celebrations.LEVELS:
            self.celebration_box.addItem(level, level)
        self.celebration_box.setCurrentIndex(
            self.celebration_box.findData(celebrations.level()))
        self.celebration_box.currentIndexChanged.connect(
            lambda _i: celebrations.set_level(self.celebration_box.currentData()))
        bar.addWidget(self.celebration_box)
        about = QPushButton("About")
        about.setObjectName("flat")
        about.clicked.connect(self._about)
        bar.addWidget(about)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.start_page = StartPage(self)
        self.stack.addWidget(self.start_page)
        self.mobile = None                       # MobileServer, started on demand

    def _set_board_theme(self) -> None:
        name = self.theme_box.currentData()
        AppSettings.instance().set("viewer_board_theme", name)
        AppSettings.instance().save()
        if isinstance(self._page, BoardPage):
            self._page.view.set_theme(name)

    # ---- phone mirror -------------------------------------------------------------- #

    def share_on_phone(self) -> None:
        from polytess.viewer import mobile_server
        if not mobile_server.available():
            QMessageBox.information(
                self, "Follow on phone",
                "The phone mirror needs the packages 'aiohttp' and 'qrcode':\n"
                "pip install polytess[mobile]")
            return
        if self.mobile is None:
            settings = AppSettings.instance()
            self.mobile = mobile_server.MobileServer(
                port=int(settings.get("mobile_port") or 8765),
                allow_control=lambda: bool(settings.get("mobile_allow_control")))
            self.mobile.on_remote_action = self._remote_action
            self._attach_mirror()
        if not self.mobile.running:
            import asyncio

            async def boot():
                try:
                    await self.mobile.start()
                    self.statusBar().showMessage(
                        f"Phone mirror listening on port {self.mobile.port}")
                except OSError as exc:
                    QMessageBox.critical(self, "Follow on phone",
                                         f"Cannot start the phone mirror on port "
                                         f"{self.mobile.port}:\n{exc}")
            asyncio.ensure_future(boot())
        from polytess.viewer.share_dialog import ShareDialog
        ShareDialog(self.mobile, self).exec()

    def _attach_mirror(self) -> None:
        if self.mobile is None:
            return
        page = self._page if isinstance(self._page, BoardPage) else None
        if page is not None:
            page.mirror = self.mobile
        self.mobile.set_page(page)

    def _remote_action(self, text: str) -> None:
        self.statusBar().showMessage(f"Phone: {text}", 5000)
        page = self._page if isinstance(self._page, BoardPage) else None
        if page is not None:
            page.run_panel.log.log("info", f"Phone requested: {text}")

    # ---- navigation ----------------------------------------------------------------- #

    def show_start(self) -> None:
        if self._page is not None and not self._page.confirm_close():
            return
        if self._page is not None:
            self.stack.removeWidget(self._page)
            self._page.deleteLater()
            self._page = None
        self.start_page.refresh()
        self.stack.setCurrentWidget(self.start_page)
        self._attach_mirror()

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open flow", "",
                                              "Workflows (*.flow.json)")
        if path:
            self.open_flow(path)

    def open_flow(self, path: str) -> None:
        if self._page is not None and not self._page.confirm_close():
            return
        try:
            graph = Graph.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open flow", f"Cannot open {path}:\n{exc}")
            return
        self._remember(path)
        if self._page is not None:
            self.stack.removeWidget(self._page)
            self._page.deleteLater()
        spec = board_spec(graph)
        page = BoardPage(graph) if spec.cards else FormPage(graph)
        page.back_requested.connect(self.show_start)
        self._page = page
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)
        self.setWindowTitle(f"{graph.name} — polytess Viewer")
        self._attach_mirror()

    def _remember(self, path: str) -> None:
        settings = AppSettings.instance()
        recent = [p for p in (settings.get("viewer_recent") or []) if p != path]
        recent.insert(0, os.path.abspath(path))
        settings.set("viewer_recent", recent[:MAX_RECENT])
        settings.save()

    def _about(self) -> None:
        QMessageBox.about(self, "polytess Viewer",
                          f"polytess Viewer {__version__}\n\nRuns flows built in "
                          f"polytess Studio — inputs as a form, main processes as a "
                          f"board. It never edits a flow.")

    # ---- drag & drop of flow files ------------------------------------------------ #

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if any(u.toLocalFile().endswith(".flow.json") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt API)
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.endswith(".flow.json"):
                self.open_flow(path)
                break

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._page is not None and not self._page.confirm_close():
            event.ignore()
            return
        if self.mobile is not None and self.mobile.running:
            import asyncio
            asyncio.ensure_future(self.mobile.stop())
        event.accept()
