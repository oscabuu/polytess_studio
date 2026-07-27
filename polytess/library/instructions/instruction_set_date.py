# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Write a date/time into a variable: now, now + offset, or a specific date."""

from __future__ import annotations

from datetime import datetime, timedelta

from polytess.core.dates import format_date, parse_date
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetDate, PropertyGetNumber,
                                    PropertySetAny, SetGraphVariable)


@meta(title="Set Date", category="Variables/Set Date", icon="clock", color="teal",
      description="Writes a date/time into a variable: the current time, the "
                  "current time plus an offset, or a specific date "
                  "('YYYY-MM-DD HH:MM:SS', ISO-8601 or DD.MM.YYYY)",
      parameters=(("Target", "The (date) variable to write"),
                  ("Mode", "now | now + offset | specific"),
                  ("Days/Hours/Minutes/Seconds", "Offset (mode 'now + offset'; "
                   "negative values go into the past)"),
                  ("Specific", "The date (mode 'specific')")),
      keywords=("time", "datetime", "timestamp", "deadline", "schedule"))
class SetDate(Instruction):
    FIELD_CHOICES = {"mode": ["now", "now + offset", "specific"]}

    def __init__(self, name: str = "", mode: str = "now"):
        super().__init__()
        self.target = PropertySetAny(SetGraphVariable(name))
        self.mode = mode
        self.days = PropertyGetNumber(0)
        self.hours = PropertyGetNumber(0)
        self.minutes = PropertyGetNumber(0)
        self.seconds = PropertyGetNumber(0)
        self.specific = PropertyGetDate("")

    @property
    def title(self) -> str:
        if self.mode == "specific":
            what = str(self.specific)
        elif self.mode == "now + offset":
            parts = []
            for prop, unit in ((self.days, "d"), (self.hours, "h"),
                               (self.minutes, "m"), (self.seconds, "s")):
                value = getattr(prop.source, "value", None)
                if isinstance(value, (int, float)) and value:
                    parts.append(f"{value:+g}{unit}")
            what = "now " + " ".join(parts) if parts else "now + offset"
        else:
            what = "now"
        return f"Set {self.target} = {what}"

    async def run(self, ctx):
        if self.mode == "specific":
            raw = self.specific.get(ctx)
            when = parse_date(raw)
            if when is None:
                raise ValueError(f"Set Date: {raw!r} is not a valid date")
        else:
            when = datetime.now()
            if self.mode == "now + offset":
                when += timedelta(days=self.days.get(ctx),
                                  hours=self.hours.get(ctx),
                                  minutes=self.minutes.get(ctx),
                                  seconds=self.seconds.get(ctx))
        self.target.set(format_date(when), ctx)
