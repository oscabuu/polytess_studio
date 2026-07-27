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
