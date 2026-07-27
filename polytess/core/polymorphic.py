# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""PolymorphicItem — the shared base of Instructions, Conditions, Branches,
Events, Values and Property sources.

Every item can be disabled, can carry a breakpoint, and exposes a dynamic
``title`` built from its current field values (overridden per subclass so
lists can render e.g. "Set counter = 5").
"""

from __future__ import annotations

from polytess.core.metadata import get_meta


class PolymorphicItem:

    def __init__(self):
        self.is_enabled: bool = True
        self.breakpoint: bool = False

    # ---- presentation ---------------------------------------------------- #

    @property
    def title(self) -> str:
        """Dynamic display title; subclasses interpolate field values."""
        return get_meta(type(self)).title

    @property
    def icon(self) -> str:
        return get_meta(type(self)).icon

    @property
    def color(self) -> str:
        return get_meta(type(self)).color

    def __str__(self) -> str:
        return self.title

    # ---- copy via serialization round-trip ------------- #

    def copy(self):
        from polytess.core import serialization
        return serialization.from_data(serialization.to_data(self))
