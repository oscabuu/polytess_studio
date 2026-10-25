"""Pytest bootstrap: make the suite runnable without any pip install.

Puts the project root on sys.path (so ``polytess`` imports from the folder)
and loads all plugins via the folder fallback, so tests may simply
``import polytess_hpc`` / ``import polytess_doe``."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# tests run against the repo's custom instructions (vendor-derived
# blocks live there), never against the user's ~/.polytess/custom_library
os.environ["POLYTESS_CUSTOM_LIBRARY"] = os.path.join(_ROOT, "custom_instructions")

from polytess.cli import _load_everything  # noqa: E402

_load_everything()

# tests always run console commands locally — never ssh to the command server
from polytess.core.app_settings import AppSettings  # noqa: E402

AppSettings.reset(path="", use_command_server=False)

# the whole suite runs against an ephemeral test license (the real signing
# key never touches the repo); GraphProcessor.run enforces it
import json  # noqa: E402
import tempfile  # noqa: E402

from polytess.core import licensing  # noqa: E402

_private_hex, _public_hex = licensing.generate_keypair()
licensing.PUBLIC_KEY_HEX = _public_hex
with tempfile.NamedTemporaryFile("w", suffix=".lic", delete=False) as _fh:
    json.dump(licensing.sign_license(
        {"licensee": "pytest", "expires": "", "hosts": [],
         "issued": "2026-01-01"}, _private_hex), _fh)
os.environ["POLYTESS_LICENSE"] = _fh.name
licensing.reset_cache()


# Widgets a test left behind (MainWindow, assistant panels with running
# QTimers …) are otherwise collected by the cyclic GC at an arbitrary
# later moment — sometimes inside Qt's timer activation during another
# test's processEvents(), which deletes a QObject with live timers in the
# middle of the loop and crashes. Collect them between tests instead.
import gc  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _collect_qt_garbage_between_tests():
    yield
    gc.collect()
    try:
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


# Qt + Python 3.13 segfault during interpreter shutdown on Linux after the
# whole suite passed (PySide6 objects destroyed after the Qt libraries are
# torn down). The result is final once the summary is printed, so on CI
# the process exits right there instead of running the destructors.
import pytest  # noqa: E402


_EXIT_STATUS = 0


def pytest_sessionfinish(session, exitstatus):
    global _EXIT_STATUS
    _EXIT_STATUS = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    # runs after the terminal summary has been printed
    if os.environ.get("POLYTESS_TEST_HARD_EXIT"):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_EXIT_STATUS)
