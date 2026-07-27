# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Date/time helpers for the 'date' value type.

Dates are stored as plain strings (``YYYY-MM-DD HH:MM:SS``) so they stay
JSON-serializable and readable in the blackboard; parsing accepts ISO-8601
plus common German formats.
"""

from __future__ import annotations

from datetime import datetime

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_EXTRA_FORMATS = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
)


def format_date(value: datetime) -> str:
    return value.strftime(DATE_FORMAT)


def parse_date(value) -> datetime | None:
    """datetime | timestamp | string -> datetime (None if empty/unparsable)."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
        for fmt in _EXTRA_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None
