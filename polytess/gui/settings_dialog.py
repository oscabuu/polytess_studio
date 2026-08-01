# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Global settings dialog (gear button in the toolbar).

Edits the AppSettings singleton (~/.polytess/settings.json):
- Command server: console commands run as ``ssh <server> "command"``
- Claude assistant: API key + model for the code-editor chat
- Reports: default corporate font and colors for generated reports/plots
"""

from __future__ import annotations

import socket

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QFontComboBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from polytess.core.app_settings import (DEFAULTS, AppSettings,
                                       sync_python_include_paths)
from polytess.gui.theme import ACCENTS
from polytess.gui.widgets import StringListEdit


class _ColorButton(QPushButton):
    """Swatch button opening a color picker."""

    def __init__(self, value: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 24)
        self.set_color(value)
        self.clicked.connect(self._pick)

    def set_color(self, value: str) -> None:
        self._color = value or "#000000"
        self.setStyleSheet(f"QPushButton {{ background: {self._color};"
                           f" border: 1px solid #1a1a1a; }}")
        self.setText("")
        self.setToolTip(self._color)

    def color(self) -> str:
        return self._color

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self,
                                       "Choose color")
        if chosen.isValid():
            self.set_color(chosen.name())


class SettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        settings = AppSettings.instance()

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ---- command server ------------------------------------------------ #
        server_page = QWidget()
        server_layout = QVBoxLayout(server_page)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        self.use_server = QCheckBox("Run console commands on the command "
                                    "server (ssh)")
        self.use_server.setChecked(bool(settings.get("use_command_server")))
        form.addRow(self.use_server)
        self.server = QLineEdit(str(settings.get("command_server")))
        self.server.setPlaceholderText(DEFAULTS["command_server"])
        form.addRow("Command Server", self.server)
        self.ssh_options = QLineEdit(str(settings.get("ssh_options")))
        form.addRow("SSH Options", self.ssh_options)
        server_layout.addLayout(form)
        hint = QLabel(
            f"Commands run as  ssh &lt;server&gt; 'cd \"…\" && command'  — "
            f"tcsh-safe, requires non-interactive SSH auth (key). This "
            f"machine ({socket.gethostname().split('.')[0]}) runs commands "
            f"locally when it IS the command server.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {ACCENTS['text-light']};")
        server_layout.addWidget(hint)
        server_layout.addStretch(1)
        tabs.addTab(server_page, "Command Server")

        # ---- solver profiles ------------------------------------------------ #
        solver_page = QWidget()
        solver_layout = QVBoxLayout(solver_page)
        self._solver_fields: dict[str, dict] = {}
        for kind, label in (("mks", "MKS (Simpack)"), ("fem", "FEM (Abaqus)")):
            group_form = QFormLayout()
            group_form.setHorizontalSpacing(12)
            title = QLabel(f"<b>{label}</b>")
            solver_layout.addWidget(title)
            fields: dict = {}
            fields["command"] = QLineEdit(str(settings.get(f"{kind}_command")))
            fields["command"].setPlaceholderText(DEFAULTS[f"{kind}_command"])
            group_form.addRow("Solver Command", fields["command"])
            fields["use_ssh"] = QCheckBox("Run via SSH on:")
            fields["use_ssh"].setChecked(bool(settings.get(f"{kind}_use_ssh")))
            fields["host"] = QLineEdit(str(settings.get(f"{kind}_host")))
            fields["host"].setPlaceholderText("hostname")
            ssh_row = QHBoxLayout()
            ssh_row.addWidget(fields["use_ssh"])
            ssh_row.addWidget(fields["host"], 1)
            fields["shell"] = QComboBox()
            fields["shell"].addItems(["tcsh", "bash", "cmd"])
            fields["shell"].setCurrentText(str(settings.get(f"{kind}_shell")
                                               or "tcsh"))
            ssh_row.addWidget(QLabel("Remote shell"))
            ssh_row.addWidget(fields["shell"])
            group_form.addRow(ssh_row)
            path_row = QHBoxLayout()
            fields["path_local"] = QLineEdit(
                str(settings.get(f"{kind}_path_local")))
            fields["path_local"].setPlaceholderText(r"local prefix, e.g. P:\projects")
            fields["path_remote"] = QLineEdit(
                str(settings.get(f"{kind}_path_remote")))
            fields["path_remote"].setPlaceholderText("remote prefix, e.g. /proj/projects")
            path_row.addWidget(fields["path_local"], 1)
            path_row.addWidget(QLabel("↔"))
            path_row.addWidget(fields["path_remote"], 1)
            group_form.addRow("Path Mapping", path_row)
            solver_layout.addLayout(group_form)
            solver_layout.addSpacing(10)
            self._solver_fields[kind] = fields
        solver_hint = QLabel(
            "Solver instructions with an empty command field use these "
            "profiles. With SSH enabled the call is wrapped for the REMOTE "
            "login shell (tcsh/bash on Linux, cmd on Windows) and the path "
            "mapping translates the shared-storage prefix — requires the "
            "project storage to be mounted on both sides and key-based SSH.")
        solver_hint.setWordWrap(True)
        solver_hint.setStyleSheet(f"color: {ACCENTS['text-light']};")
        solver_layout.addWidget(solver_hint)
        solver_layout.addStretch(1)
        tabs.addTab(solver_page, "Solvers")

        # ---- assistant ------------------------------------------------------ #
        assistant_page = QWidget()
        assistant_layout = QVBoxLayout(assistant_page)
        assistant_form = QFormLayout()
        assistant_form.setHorizontalSpacing(12)
        self.assistant_provider = QComboBox()
        self.assistant_provider.addItem("Anthropic (Claude API)", "anthropic")
        self.assistant_provider.addItem("GitHub Copilot (subscription)",
                                        "copilot")
        current_provider = str(settings.get("assistant_provider")
                               or "anthropic")
        self.assistant_provider.setCurrentIndex(
            1 if current_provider == "copilot" else 0)
        assistant_form.addRow("Provider", self.assistant_provider)
        self.api_key = QLineEdit(str(settings.get("anthropic_api_key")))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("sk-ant-…  (empty = use "
                                        "ANTHROPIC_API_KEY env var)")
        assistant_form.addRow("Anthropic API Key", self.api_key)
        self.model = QLineEdit(str(settings.get("assistant_model")))
        self.model.setPlaceholderText(DEFAULTS["assistant_model"])
        assistant_form.addRow("Model (Anthropic)", self.model)
        self.copilot_model = QLineEdit(str(settings.get("copilot_model")))
        self.copilot_model.setPlaceholderText(DEFAULTS["copilot_model"])
        assistant_form.addRow("Model (Copilot)", self.copilot_model)
        self.github_host = QLineEdit(str(settings.get("github_host")))
        self.github_host.setPlaceholderText(
            "empty = github.com — GHE e.g. https://firma.ghe.com")
        assistant_form.addRow("GitHub Host (GHE)", self.github_host)
        self.github_token = QLineEdit(str(settings.get("github_token")))
        self.github_token.setEchoMode(QLineEdit.Password)
        self.github_token.setPlaceholderText(
            "optional — empty = use 'copilot login'")
        assistant_form.addRow("GitHub Token", self.github_token)
        assistant_layout.addLayout(assistant_form)
        assistant_hint = QLabel(
            "Used by both studio assistants (code editor chat + flow "
            "assistant). Anthropic: API key here or ANTHROPIC_API_KEY env "
            "var. GitHub Copilot: needs 'pip install github-copilot-sdk' "
            "and a one-time login — on GitHub Enterprise: "
            "copilot login --host https://&lt;tenant&gt;.ghe.com — the "
            "host configured above is exported as COPILOT_GH_HOST for "
            "every request.")
        assistant_hint.setWordWrap(True)
        assistant_hint.setStyleSheet(f"color: {ACCENTS['text-light']};")
        assistant_layout.addWidget(assistant_hint)
        assistant_layout.addStretch(1)
        tabs.addTab(assistant_page, "Assistant")

        # ---- reports -------------------------------------------------------- #
        report_page = QWidget()
        report_layout = QVBoxLayout(report_page)
        report_form = QFormLayout()
        report_form.setHorizontalSpacing(12)
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentText(str(settings.get("report_font")))
        report_form.addRow("Font", self.font_combo)
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 32)
        self.font_size.setValue(int(settings.get("report_font_size") or 11))
        report_form.addRow("Font Size", self.font_size)
        self.color_primary = _ColorButton(str(settings.get("report_color_primary")))
        report_form.addRow("Primary Color", self.color_primary)
        self.color_secondary = _ColorButton(
            str(settings.get("report_color_secondary")))
        report_form.addRow("Secondary Color", self.color_secondary)
        self.color_accent = _ColorButton(str(settings.get("report_color_accent")))
        report_form.addRow("Accent Color", self.color_accent)
        report_layout.addLayout(report_form)
        report_hint = QLabel(
            "Corporate defaults for generated reports, documents and plots. "
            "Instructions read them via AppSettings (report_font, "
            "report_font_size, report_color_primary/secondary/accent).")
        report_hint.setWordWrap(True)
        report_hint.setStyleSheet(f"color: {ACCENTS['text-light']};")
        report_layout.addWidget(report_hint)
        report_layout.addStretch(1)
        tabs.addTab(report_page, "Reports")

        # ---- python ----------------------------------------------------------- #
        python_page = QWidget()
        python_layout = QVBoxLayout(python_page)
        python_layout.addWidget(QLabel("<b>Include Paths</b>"))
        self.python_include_paths = StringListEdit(
            [str(p) for p in settings.get("python_include_paths") or []])
        python_layout.addWidget(self.python_include_paths)
        python_hint = QLabel(
            "Extra directories added to sys.path at startup (and "
            "immediately when you save here) — so custom_library modules "
            "and in-studio Python code can import your own local packages "
            "without an environment variable.")
        python_hint.setWordWrap(True)
        python_hint.setStyleSheet(f"color: {ACCENTS['text-light']};")
        python_layout.addWidget(python_hint)
        python_layout.addStretch(1)
        tabs.addTab(python_page, "Python")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        settings = AppSettings.instance()
        settings.set("use_command_server", self.use_server.isChecked())
        settings.set("command_server", self.server.text().strip())
        settings.set("ssh_options", self.ssh_options.text().strip())
        for kind, fields in self._solver_fields.items():
            settings.set(f"{kind}_command", fields["command"].text().strip())
            settings.set(f"{kind}_use_ssh", fields["use_ssh"].isChecked())
            settings.set(f"{kind}_host", fields["host"].text().strip())
            settings.set(f"{kind}_shell", fields["shell"].currentText())
            settings.set(f"{kind}_path_local",
                         fields["path_local"].text().strip())
            settings.set(f"{kind}_path_remote",
                         fields["path_remote"].text().strip())
        settings.set("assistant_provider",
                     self.assistant_provider.currentData())
        settings.set("anthropic_api_key", self.api_key.text().strip())
        settings.set("assistant_model",
                     self.model.text().strip() or DEFAULTS["assistant_model"])
        settings.set("copilot_model",
                     self.copilot_model.text().strip()
                     or DEFAULTS["copilot_model"])
        settings.set("github_host", self.github_host.text().strip())
        settings.set("github_token", self.github_token.text().strip())
        settings.set("report_font", self.font_combo.currentText())
        settings.set("report_font_size", self.font_size.value())
        settings.set("report_color_primary", self.color_primary.color())
        settings.set("report_color_secondary", self.color_secondary.color())
        settings.set("report_color_accent", self.color_accent.color())
        settings.set("python_include_paths",
                     [p.strip() for p in self.python_include_paths.values() if p.strip()])
        settings.save()
        sync_python_include_paths()
        self.accept()
