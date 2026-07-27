# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Commercial license dialog — polytess runs fully under the Business
Source License 1.1 without any file; this only manages an OPTIONAL
commercial license that grants rights beyond the BUSL Additional Use
Grant (e.g. resale/hosting). View the active one, import a new license
file, open the license folder."""

from __future__ import annotations

import os
import shutil

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout)

from polytess.core import licensing
from polytess.gui.theme import ACCENTS, COLORS


class LicenseDialog(QDialog):
    """Shows the license state and lets the user import a .lic file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("polytess Commercial License")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"font-size: 14px; padding: 12px; border-radius: 4px;")
        layout.addWidget(self.status_label)

        self.details = QFormLayout()
        self.details.setHorizontalSpacing(14)
        self._detail_labels: dict[str, QLabel] = {}
        for key, title in (("licensee", "Licensee"), ("expires", "Expires"),
                           ("hosts", "Machines"), ("issued", "Issued"),
                           ("file", "License file")):
            label = QLabel("—")
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {ACCENTS['text-light']};")
            self._detail_labels[key] = label
            self.details.addRow(title, label)
        layout.addLayout(self.details)
        layout.addSpacing(6)

        hint = QLabel("polytess is usable in full under the Business Source "
                      "License 1.1 without any file. A commercial license "
                      "(*.lic, issued by Winthir Studios) grants rights "
                      "beyond it, e.g. resale or hosting. Importing copies "
                      "it to ~/.polytess/license.lic; the previous file is "
                      "kept as license.lic.bak.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {ACCENTS['text-light']}; font-size: 11px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox()
        import_button = QPushButton("Import License File…")
        import_button.clicked.connect(self._import)
        buttons.addButton(import_button, QDialogButtonBox.ActionRole)
        folder_button = QPushButton("Open License Folder")
        folder_button.clicked.connect(self._open_folder)
        buttons.addButton(folder_button, QDialogButtonBox.ActionRole)
        buttons.addButton(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.refresh()

    # ---- state ---------------------------------------------------------- #

    def refresh(self) -> None:
        licensing.reset_cache()
        path = licensing.find_license_file()
        try:
            payload = licensing.ensure_licensed()
            self.status_label.setText(
                f"✓  {licensing.license_status()}")
            self.status_label.setStyleSheet(
                f"font-size: 14px; padding: 12px; border-radius: 4px; "
                f"background-color: {COLORS['bg-dark']}; "
                f"color: {ACCENTS['green']};")
            self._detail_labels["licensee"].setText(
                str(payload.get("licensee", "—")))
            expires = str(payload.get("expires") or "").strip()
            self._detail_labels["expires"].setText(expires or "perpetual")
            hosts = payload.get("hosts") or []
            self._detail_labels["hosts"].setText(
                ", ".join(hosts) if hosts else "any machine")
            self._detail_labels["issued"].setText(
                str(payload.get("issued", "—")))
        except licensing.LicenseError as exc:
            no_file = path is None
            self.status_label.setText(
                "polytess runs under the Business Source License 1.1 — "
                "no commercial license installed." if no_file else f"✗  {exc}")
            self.status_label.setStyleSheet(
                f"font-size: 14px; padding: 12px; border-radius: 4px; "
                f"background-color: {COLORS['bg-dark']}; "
                f"color: {ACCENTS['text-light'] if no_file else ACCENTS['red']};")
            for key in ("licensee", "expires", "hosts", "issued"):
                self._detail_labels[key].setText("—")
        self._detail_labels["file"].setText(path or "no license file found")

    # ---- actions -------------------------------------------------------- #

    def _import(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, "Import polytess license", "", "License files (*.lic);;"
            "All files (*)")
        if not source:
            return
        from polytess.core.userdir import user_dir
        target = os.path.join(user_dir(), "license.lic")
        try:
            # validate BEFORE replacing anything
            import json
            with open(source, encoding="utf-8") as fh:
                licensing.verify_license_data(json.load(fh))
            if os.path.isfile(target):
                shutil.copy2(target, target + ".bak")
            shutil.copy2(source, target)
        except licensing.LicenseError as exc:
            QMessageBox.critical(self, "Import license",
                                 f"This license file is not valid:\n{exc}")
            return
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Import license", str(exc))
            return
        self.refresh()
        QMessageBox.information(self, "Import license",
                                "License imported successfully.")

    def _open_folder(self) -> None:
        from polytess.core.userdir import user_dir
        QDesktopServices.openUrl(QUrl.fromLocalFile(user_dir()))
