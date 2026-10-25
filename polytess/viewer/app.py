# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Viewer main window: start page (recent flows, open) → form page or
board page, depending on whether the flow has sub-workflow cards."""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu,
                               QMessageBox, QPushButton, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from polytess import __version__
from polytess.core.app_settings import AppSettings
from polytess.graph.board import board_spec
from polytess.graph.model import Graph
from polytess.gui.icons import icon
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

        self._build_menus()
        self._build_toolbar()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.start_page = StartPage(self)
        self.stack.addWidget(self.start_page)
        self.mobile = None                       # MobileServer, started on demand

    # ---- menu bar + toolbar (same look as the Studio) ----------------------------- #

    def _build_menus(self) -> None:
        from polytess.viewer.style import BOARD_THEMES
        self.act_start = QAction(icon("graph", "text"), "&Start Page", self,
                                 shortcut="Ctrl+Home", triggered=self.show_start)
        self.act_open = QAction(icon("folder", "text"), "&Open Flow…", self,
                                shortcut=QKeySequence.Open, triggered=self.open_dialog)
        self.act_about = QAction(icon("help", "text"), "&About polytess Viewer", self,
                                 triggered=self._about)
        self.act_quit = QAction("&Quit", self, shortcut=QKeySequence.Quit,
                                triggered=self.close)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.act_open)
        self.recent_menu = file_menu.addMenu("Open &Recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        file_menu.addSeparator()
        file_menu.addAction(self.act_start)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        view_menu = self.menuBar().addMenu("&View")
        theme_menu = view_menu.addMenu("&Board Theme")
        self.theme_menu = theme_menu
        self.theme_group = QActionGroup(self)
        current_theme = str(AppSettings.instance().get("viewer_board_theme") or "classic")
        for key, theme in BOARD_THEMES.items():
            action = QAction(key.capitalize(), self, checkable=True)
            action.setData(key)
            action.setToolTip(theme["label"])
            action.setStatusTip(theme["label"])
            action.setChecked(key == current_theme)
            action.triggered.connect(lambda _c=False, k=key: self.set_board_theme(k))
            self.theme_group.addAction(action)
            theme_menu.addAction(action)
        celebration_menu = view_menu.addMenu("&Celebrations")
        self.celebration_menu = celebration_menu
        self.celebration_group = QActionGroup(self)
        for level in celebrations.LEVELS:
            action = QAction(level.capitalize(), self, checkable=True)
            action.setData(level)
            action.setChecked(level == celebrations.level())
            action.triggered.connect(lambda _c=False, lv=level: celebrations.set_level(lv))
            self.celebration_group.addAction(action)
            celebration_menu.addAction(action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        # burger menu: every command in one place (phones and small screens)
        self.burger_menu = QMenu(self)
        self.burger_menu.addAction(self.act_open)
        self.burger_menu.addMenu(self.recent_menu)
        self.burger_menu.addAction(self.act_start)
        self.burger_menu.addSeparator()
        # same QActions as the View menu, in menus of their own (a QMenu
        # must not be attached to two parents — PySide deletes it)
        # keep Python references: QMenu.addMenu(str) does not hand the new
        # menu's ownership to C++ in PySide, a dropped wrapper deletes it
        self.settings_menu = self.burger_menu.addMenu("Settings")
        self.theme_sub = self.settings_menu.addMenu("Board Theme")
        for action in self.theme_group.actions():
            self.theme_sub.addAction(action)
        self.celebration_sub = self.settings_menu.addMenu("Celebrations")
        for action in self.celebration_group.actions():
            self.celebration_sub.addAction(action)
        self.burger_menu.addSeparator()
        self.burger_menu.addAction(self.act_about)
        self.burger_menu.addAction(self.act_quit)
        self.burger_button = QToolButton()
        self.burger_button.setIcon(icon("menu", "text"))
        self.burger_button.setToolTip("Menu")
        self.burger_button.setMenu(self.burger_menu)
        self.burger_button.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(self.burger_button)
        toolbar.addSeparator()
        toolbar.addAction(self.act_open)
        toolbar.addSeparator()
        toolbar.addAction(self.act_about)

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        paths = [p for p in (AppSettings.instance().get("viewer_recent") or [])
                 if os.path.isfile(p)]
        if not paths:
            empty = self.recent_menu.addAction("(nothing yet)")
            empty.setEnabled(False)
            return
        for path in paths:
            action = self.recent_menu.addAction(os.path.basename(path))
            action.setStatusTip(path)
            action.triggered.connect(lambda _c=False, p=path: self.open_flow(p))

    def set_board_theme(self, name: str) -> None:
        AppSettings.instance().set("viewer_board_theme", name)
        AppSettings.instance().save()
        for action in self.theme_group.actions():
            action.setChecked(action.data() == name)
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
