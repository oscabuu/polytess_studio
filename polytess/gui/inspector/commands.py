# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""QUndoStack commands for node CONTENT edits (field values, and the
Instructions/Conditions/Branches lists) — as opposed to
polytess/gui/graph/commands.py, which covers graph STRUCTURE (nodes,
edges, positions).

Both commands only touch model objects (never widgets): a rebuild
triggered by undo/redo replaces the whole Inspector widget tree, so
holding a widget reference here would go stale after the first such
rebuild. ``_first`` mirrors MoveNodesCommand in graph/commands.py: the
caller already applied the edit live (for instant feedback while
typing/dragging/dropping) before pushing, so the command's own first
redo() is a no-op — only a *later* redo() (after an undo) must reapply.
"""

from __future__ import annotations

from PySide6.QtGui import QUndoCommand


class EditFieldCommand(QUndoCommand):
    """One field's value changed (a node header field, a PropertySource's
    value, or a whole PropertyGet/PropertySet.source swap). Consecutive
    edits to the same (target, attr) — e.g. every keystroke in a text
    field — merge into a single undo step."""

    def __init__(self, target, attr: str, old_value, new_value, node,
                inspector, label: str = "Edit Field"):
        super().__init__(label)
        self.target = target
        self.attr = attr
        self.old_value = old_value
        self.new_value = new_value
        self.node = node
        self.inspector = inspector
        self._first = True

    def _notify(self) -> None:
        self.inspector.node_changed.emit(self.node)
        self.inspector.refresh_if_showing(self.node)

    def redo(self) -> None:
        if self._first:            # value already applied live by the caller
            self._first = False
            return
        setattr(self.target, self.attr, self.new_value)
        self._notify()

    def undo(self) -> None:
        setattr(self.target, self.attr, self.old_value)
        self._notify()

    def id(self) -> int:
        return (hash((id(self.target), self.attr)) & 0x7fffffff) or 1

    def mergeWith(self, other) -> bool:
        if not isinstance(other, EditFieldCommand):
            return False
        if other.target is not self.target or other.attr != self.attr:
            return False
        self.new_value = other.new_value
        return True


class ListEditCommand(QUndoCommand):
    """A structural edit (insert/replace/duplicate/delete/reorder) on an
    Instructions/Conditions/Branches list. Snapshots the whole list
    before/after via each item's serialization-based ``.copy()`` —
    simpler and more robust than a separate command per operation kind,
    and handles drag-reorder (which isn't a single insert/delete) the
    same way."""

    def __init__(self, items: list, before: list, after: list, node,
                inspector, label: str = "Edit List"):
        super().__init__(label)
        self.items = items
        self.before = before
        self.after = after
        self.node = node
        self.inspector = inspector
        self._first = True

    def _notify(self) -> None:
        self.inspector.node_changed.emit(self.node)
        self.inspector.refresh_if_showing(self.node)

    def redo(self) -> None:
        if self._first:            # list already updated live by the caller
            self._first = False
            return
        self.items[:] = [item.copy() for item in self.after]
        self._notify()

    def undo(self) -> None:
        self.items[:] = [item.copy() for item in self.before]
        self._notify()


class UndoCallbacks:
    """Bundles the two push-undo callbacks threaded through the field and
    list editors (fields.py, poly_list.py) so a node's content edits
    become undoable. ``None`` wherever there's no active undo stack
    (e.g. a widget built in isolation in a test) — editors then fall
    back to applying the change directly, matching the pre-undo
    behavior."""

    def __init__(self, push_field, push_list):
        self.push_field = push_field
        self.push_list = push_list
