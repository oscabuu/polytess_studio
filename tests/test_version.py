# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Version consistency: single source, changelog in sync."""

import os
import re

import polytess


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", polytess.__version__)


def test_changelog_top_entry_matches_version():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    changelog = open(os.path.join(root, "CHANGELOG.md"),
                     encoding="utf-8").read()
    match = re.search(r"^## (\d+\.\d+\.\d+)", changelog, re.MULTILINE)
    assert match, "CHANGELOG.md has no version entry"
    assert match.group(1) == polytess.__version__, (
        "CHANGELOG.md top entry and polytess.__version__ diverge — "
        "every commit bumps both")


def test_pyproject_uses_dynamic_version():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pyproject = open(os.path.join(root, "pyproject.toml"),
                     encoding="utf-8").read()
    assert 'dynamic = ["version"]' in pyproject
    assert 'attr = "polytess.__version__"' in pyproject
