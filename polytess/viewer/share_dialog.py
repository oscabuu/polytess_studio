# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""'Follow on phone' dialog: QR code + link for the mobile mirror."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout,
                               QApplication)

from polytess.core.app_settings import AppSettings
from polytess.viewer.mobile_server import MobileServer, local_addresses


def qr_pixmap(text: str, size: int = 260) -> QPixmap:
    """QR code rendered with QPainter (no Pillow, no QtSvg)."""
    import qrcode
    code = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(text)
    code.make(fit=True)
    matrix = code.get_matrix()
    modules = len(matrix)
    cell = max(1, size // modules)
    pixmap = QPixmap(modules * cell, modules * cell)
    pixmap.fill(QColor("#ffffff"))
    painter = QPainter(pixmap)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#111111"))
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                painter.drawRect(x * cell, y * cell, cell, cell)
    painter.end()
    return pixmap


class ShareDialog(QDialog):

    def __init__(self, server: MobileServer, parent=None):
        super().__init__(parent)
        self.server = server
        self.setWindowTitle("Follow on phone")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        intro = QLabel("Scan the code with the phone's camera. The phone must reach "
                       "this computer (same Wi-Fi or VPN); the link is valid while "
                       "the Viewer runs.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.qr)

        row = QHBoxLayout()
        row.addWidget(QLabel("Address"))
        self.address = QComboBox()
        for host in local_addresses():
            self.address.addItem(host, host)
        self.address.currentIndexChanged.connect(lambda _i: self._refresh())
        row.addWidget(self.address, 1)
        layout.addLayout(row)

        self.link = QLineEdit()
        self.link.setReadOnly(True)
        layout.addWidget(self.link)

        self.status = QLabel("")
        self.status.setObjectName("hint")
        layout.addWidget(self.status)

        self.control = QCheckBox("Allow start / stop from the phone")
        self.control.setChecked(bool(AppSettings.instance().get("mobile_allow_control")))
        self.control.toggled.connect(self._set_control)
        layout.addWidget(self.control)

        buttons = QHBoxLayout()
        copy = QPushButton("Copy link")
        copy.setObjectName("flat")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.link.text()))
        buttons.addWidget(copy)
        renew = QPushButton("New code")
        renew.setObjectName("flat")
        renew.setToolTip("Invalidate every old link and show a fresh code")
        renew.clicked.connect(self._renew)
        buttons.addWidget(renew)
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._refresh()
        server.on_clients_changed = self.set_clients
        self.set_clients(server.client_count)

    def _refresh(self) -> None:
        url = self.server.url(self.address.currentData() or "127.0.0.1")
        self.link.setText(url)
        self.qr.setPixmap(qr_pixmap(url))

    def _renew(self) -> None:
        self.server.renew_token()
        self._refresh()

    def _set_control(self, enabled: bool) -> None:
        AppSettings.instance().set("mobile_allow_control", enabled)
        AppSettings.instance().save()
        self.server.notify_control()

    def set_clients(self, count: int) -> None:
        self.status.setText(f"{count} phone{'s' if count != 1 else ''} connected"
                            if count else "No phone connected yet")

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.server.on_clients_changed is self.set_clients:
            self.server.on_clients_changed = None
        super().closeEvent(event)
