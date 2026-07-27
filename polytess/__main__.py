# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""polytess Studio entry point:  python -m polytess  [workflow.flow.json ...]"""

from __future__ import annotations

import asyncio
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    from PySide6.QtWidgets import QApplication
    import qasync

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("polytess Studio")
    app.setOrganizationName("Winthir Studios")
    app.setStyle("Fusion")

    from polytess.gui.app_icon import app_icon
    app.setWindowIcon(app_icon())

    from polytess.gui.theme import build_qss
    app.setStyleSheet(build_qss())

    # register built-in library + plugins before any file is loaded
    from polytess.cli import _load_everything
    _load_everything()

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    from polytess.gui.main_window import MainWindow
    window = MainWindow()
    window.show()

    for path in argv:
        window.open_document(path)

    with loop:
        return loop.run_forever()


if __name__ == "__main__":
    sys.exit(main())
