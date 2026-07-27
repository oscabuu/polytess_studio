# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""polytess Simpack/Abaqus plugin TEMPLATE.

File convention (one class per file):

    polytess_simpack/instruction_<name>.py   -> Action  "<Name>"
    polytess_simpack/condition_<name>.py     -> Condition
    polytess_simpack/event_<name>.py         -> Event

Every module in this folder loads AUTOMATICALLY at startup — dropping
in a new file is enough, no import line needed. Files with a leading
underscore (e.g. _template.py) are skipped.

Pattern for a new action: copy _template.py, rename, fill in, restart
the studio. Installing the plugin (once):
``pip install -e plugins/simpack_template`` — polytess loads it through
the "polytess.plugins" entry point.
"""

from polytess.library import import_all_modules

import_all_modules(__name__)
