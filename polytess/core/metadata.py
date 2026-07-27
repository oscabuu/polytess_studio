# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Class metadata + registry.

Descriptive attributes (title, category, description, keywords,
parameters, icon, color) plus polymorphic type resolution for the
tagged-JSON serialization.

Every selectable / serializable polymorphic class is decorated with
``@meta(...)``. The decorator stores a :class:`Meta` record on the class
and registers the class in the global type registry, which feeds
- serialization ("$type" tag -> class),
- the searchable type-selector menus (category tree + fuzzy search).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Meta record
# --------------------------------------------------------------------------- #

@dataclass
class Meta:
    title: str = ""
    category: str = ""                     # slash separated: "Files/Create Folder"
    description: str = ""
    keywords: tuple[str, ...] = ()
    parameters: tuple[tuple[str, str], ...] = ()   # (name, description)
    icon: str = "circle"                   # icon name, see gui.icons
    color: str = "text"                    # color token, see gui.theme / COLORS
    version: tuple[int, int, int] = (0, 1, 0)
    hidden: bool = False                   # [HideInSelector]
    type_name: str = ""                    # stable "$type" tag (defaults to class name)

    @property
    def category_path(self) -> list[str]:
        return [p for p in self.category.split("/") if p]

    @property
    def category_folders(self) -> list[str]:
        """All path segments except the last (the last one names the entry)."""
        parts = [p for p in self.category.split("/") if p]
        return parts[:-1] if len(parts) > 1 else []


_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def humanize(name: str) -> str:
    """'InstructionCreateFolder' -> 'Instruction Create Folder' (TextUtils.Humanize)."""
    return _CAMEL_RE.sub(" ", name).replace("_", " ").strip()


# --------------------------------------------------------------------------- #
# Type registry
# --------------------------------------------------------------------------- #

_TYPES: dict[str, type] = {}


class DuplicateTypeName(Exception):
    pass


def register_type(cls: type, type_name: str = "") -> None:
    name = type_name or getattr(cls, "__meta__", None) and cls.__meta__.type_name or cls.__name__
    existing = _TYPES.get(name)
    if existing is not None and existing is not cls:
        raise DuplicateTypeName(
            f"Type name {name!r} already registered by {existing.__module__}.{existing.__qualname__}; "
            f"set meta(type_name=...) on {cls.__module__}.{cls.__qualname__}")
    _TYPES[name] = cls
    cls.__type_name__ = name


def resolve_type(name: str) -> type:
    try:
        return _TYPES[name]
    except KeyError:
        raise KeyError(f"Unknown $type {name!r} — is the defining module/plugin imported?") from None


def type_name_of(cls: type) -> str:
    return getattr(cls, "__type_name__", cls.__name__)


def registered_types() -> dict[str, type]:
    return dict(_TYPES)


def unregister_module(module_name: str) -> None:
    """Drop all types a module registered — before re-executing it
    (hot reload of custom-library files from the code editor)."""
    stale = [name for name, cls in _TYPES.items()
             if getattr(cls, "__module__", "") == module_name]
    for name in stale:
        del _TYPES[name]


def iter_subclasses(base: type, include_hidden: bool = False):
    """All registered concrete subclasses of *base* (selector candidates)."""
    for cls in _TYPES.values():
        if issubclass(cls, base) and cls is not base:
            m = get_meta(cls)
            if m.hidden and not include_hidden:
                continue
            yield cls


# --------------------------------------------------------------------------- #
# @meta decorator
# --------------------------------------------------------------------------- #

def meta(title: str = "", category: str = "", description: str = "",
         keywords: tuple[str, ...] | list[str] = (), parameters=(),
         icon: str = "", color: str = "", version=(0, 1, 0),
         hidden: bool = False, type_name: str = ""):
    """Class decorator declaring style metadata and registering the type."""

    def wrap(cls: type):
        parent: Meta | None = None
        for base in cls.__mro__[1:]:
            pm = base.__dict__.get("__meta__")
            if isinstance(pm, Meta):
                parent = pm
                break
        m = Meta(
            title=title or humanize(cls.__name__),
            category=category,
            description=description,
            keywords=tuple(keywords),
            parameters=tuple(tuple(p) for p in parameters),
            icon=icon or (parent.icon if parent else "circle"),
            color=color or (parent.color if parent else "text"),
            version=tuple(version),
            hidden=hidden,
            type_name=type_name,
        )
        cls.__meta__ = m
        register_type(cls, type_name)
        return cls

    return wrap


_FALLBACK = Meta()


def get_meta(cls: type) -> Meta:
    m = getattr(cls, "__meta__", None)
    if m is None:
        return Meta(title=humanize(cls.__name__))
    return m


# --------------------------------------------------------------------------- #
# Category tree + fuzzy search
# --------------------------------------------------------------------------- #

class CategoryNode:
    """A folder in the selector tree; leaves carry a class."""

    def __init__(self, name: str):
        self.name = name
        self.folders: dict[str, CategoryNode] = {}
        self.entries: list[type] = []

    def sorted_folders(self) -> list["CategoryNode"]:
        return sorted(self.folders.values(), key=lambda n: n.name.lower())

    def sorted_entries(self) -> list[type]:
        return sorted(self.entries, key=lambda c: get_meta(c).title.lower())


def category_tree(base: type, include_hidden: bool = False) -> CategoryNode:
    root = CategoryNode("")
    for cls in iter_subclasses(base, include_hidden):
        node = root
        for folder in get_meta(cls).category_folders:
            node = node.folders.setdefault(folder, CategoryNode(folder))
        node.entries.append(cls)
    return root


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return len(a) + len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _search_text(cls: type) -> list[tuple[str, int]]:
    """(token, priority) pairs; mirrors ISearchable priorities."""
    m = get_meta(cls)
    out = [(m.title.lower(), 10)]
    out += [(seg.lower(), 8) for seg in m.category.split("/") if seg]
    out += [(k.lower(), 7) for k in m.keywords]
    out += [(w, 2) for w in m.description.lower().split()[:20]]
    return out


def search_types(base: type, query: str, limit: int = 50) -> list[type]:
    """Fuzzy search over title/category/keywords/description."""
    query = query.strip().lower()
    if not query:
        return []
    scored: list[tuple[float, str, type]] = []
    for cls in iter_subclasses(base):
        best = 0.0
        for token, prio in _search_text(cls):
            if not token:
                continue
            if query == token:
                score = prio * 3.0
            elif token.startswith(query):
                score = prio * 2.0
            elif query in token:
                score = prio * 1.5
            else:
                # fuzzy: compare against each word of the token
                score = 0.0
                for word in token.split():
                    dist = levenshtein(query, word)
                    if dist <= max(1, len(query) // 3):
                        score = max(score, prio * (1.0 - dist / max(len(word), 1)))
            best = max(best, score)
        if best > 0:
            scored.append((best, get_meta(cls).title.lower(), cls))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [cls for _, _, cls in scored[:limit]]
