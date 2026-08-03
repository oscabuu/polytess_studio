# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Fire a trigger when a date/time is reached."""

from __future__ import annotations

import asyncio
from datetime import datetime

from polytess.core.dates import parse_date
from polytess.core.events import Event
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetDate


@meta(title="On Date", category="Lifecycle/On Date", icon="clock", color="teal",
      description="Fires when the given date/time is reached. The date can "
                  "come from a (date) variable — moving it (e.g. via Set Date) "
                  "re-arms the trigger; each distinct date fires once. The "
                  "date string is the Loop Target.",
      parameters=(("Date", "Fixed date or date variable to watch"),
                  ("Fire If Past", "Also fire when the date is already in the "
                   "past when the workflow starts"),
                  ("Poll Interval S", "How often a changed date is picked up")),
      keywords=("schedule", "at", "deadline", "alarm", "cron", "time"))
class OnDate(Event):
    persistent = True

    FIELD_HELP = {
        "date": "Date/time to fire at; a fixed date or a date variable. "
                "Moving the variable (e.g. via Set Date) re-arms the "
                "trigger; each distinct date fires once. The date string "
                "becomes the Loop Target of the triggered flow.",
        "fire_if_past": "If enabled, the trigger also fires when the date "
                        "is already in the past at workflow start; if "
                        "disabled (default), past dates are consumed "
                        "silently.",
        "poll_interval_s": "Seconds between checks for a moved/changed "
                           "date (default 1.0, minimum 0.05).",
    }

    def __init__(self, date: str = ""):
        super().__init__()
        self.date = PropertyGetDate(date)
        self.fire_if_past = False
        self.poll_interval_s = 1.0

    @property
    def title(self) -> str:
        return f"On Date {self.date}"

    def start(self, fire, ctx):
        super().start(fire, ctx)

        async def ticker():
            # dates are stored with 1 s resolution — floor the arm time so a
            # date written "now" in the same second still counts as future
            armed_at = datetime.now().replace(microsecond=0)
            fired_for: datetime | None = None
            while self._fire is not None:
                target = parse_date(self.date.get(ctx))
                now = datetime.now()
                if target is not None and target != fired_for and now >= target:
                    fired_for = target
                    if self.fire_if_past or target >= armed_at:
                        self.fire(self.date.get(ctx))
                    # else: already past when the trigger armed — consumed
                # sleep until the target (capped by the poll interval so a
                # moved date is picked up promptly)
                delay = max(0.05, float(self.poll_interval_s))
                if target is not None and target > now:
                    delay = min(delay, max(0.02, (target - now).total_seconds()))
                await asyncio.sleep(delay)

        self._task = asyncio.ensure_future(ticker())

    def stop(self):
        task = getattr(self, "_task", None)
        if task is not None:
            task.cancel()
            self._task = None
        super().stop()
