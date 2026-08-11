# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Flow documentation export — a linked, styled PDF (doxygen-style).

``generate_flow_doc(graph, path)`` renders one PDF per flow: a clickable
graph diagram (clicking a node jumps to its chapter), a linked table of
contents, one numbered chapter per node with its payload and parameters,
cross-linked connections, and the blackboard (variables/lists/tables).

The visual language follows winthirstudios.com/polytess.html: deep dark
pages, card panels, the site's accent palette and its fonts (Outfit for
body text, Bricolage Grotesque for headings — bundled under
``polytess/assets/fonts``, SIL OFL licensed; Helvetica is the fallback).
"""

from __future__ import annotations

import datetime
import html
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Flowable, HRFlowable, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from polytess.core.metadata import get_meta
from polytess.graph.model import Graph, Node
from polytess.graph.nodes import (ActionsNode, BranchNode, ConditionsNode,
                                  ExitNode, StartNode, SubGraphNode,
                                  TriggerNode)

# ---- winthirstudios.com/polytess.html design tokens ------------------------- #

BG_DEEP = "#0a0d14"
BG_MID = "#11151f"
BG_CARD = "#161b27"
LINE = "#232938"
TEXT_PRIMARY = "#f1f3f8"
TEXT_MUTED = "#8b94a8"
TEXT_DIM = "#525a6e"
TEAL = "#4dd6c5"
SKY = "#6cc7ff"
VIOLET = "#8b7dff"
MUSTARD = "#ffc857"
CORAL = "#ff7a6b"
LIME = "#b8e547"

_ACCENTS = {"purple": VIOLET, "blue": SKY, "green": LIME, "red": CORAL,
            "yellow": MUSTARD, "teal": TEAL}

_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "assets", "fonts")

BODY, BODY_BOLD, HEAD = "Helvetica", "Helvetica-Bold", "Helvetica-Bold"


def _register_fonts() -> None:
    global BODY, BODY_BOLD, HEAD
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = (("Outfit", "Outfit-Regular.ttf"),
                  ("Outfit-SemiBold", "Outfit-SemiBold.ttf"),
                  ("Bricolage-Bold", "BricolageGrotesque-Bold.ttf"))
    try:
        for name, filename in candidates:
            path = os.path.join(_FONTS_DIR, filename)
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, path))
        BODY, BODY_BOLD, HEAD = "Outfit", "Outfit-SemiBold", "Bricolage-Bold"
    except Exception:
        pass                       # missing fonts: Helvetica fallback


def _accent(node: Node) -> str:
    return _ACCENTS.get(getattr(node, "accent", "blue"), SKY)


def _esc(text) -> str:
    return html.escape(str(text))


# ---- content helpers -------------------------------------------------------- #

def _node_order(graph: Graph) -> list[Node]:
    """Stable chapter order: BFS from the entry nodes, leftovers by x."""
    order: list[Node] = []
    seen: set[str] = set()
    frontier = [n for n in graph.nodes if isinstance(n, (StartNode, TriggerNode))]
    frontier.sort(key=lambda n: (n.y, n.x))
    while frontier:
        node = frontier.pop(0)
        if node.guid in seen:
            continue
        seen.add(node.guid)
        order.append(node)
        children = sorted(graph.children(node), key=lambda n: (n.y, n.x))
        frontier.extend(c for c in children if c.guid not in seen)
    for node in sorted(graph.nodes, key=lambda n: (n.x, n.y)):
        if node.guid not in seen:
            order.append(node)
            seen.add(node.guid)
    return order


def _display_value(value) -> str:
    display = getattr(value, "display", None)
    if display is not None:
        return str(display)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _item_fields(item) -> list[tuple[str, str]]:
    from polytess.core.conditions import ConditionList
    from polytess.core.instructions import InstructionList
    from polytess.core.metadata import humanize
    rows = []
    for key, value in vars(item).items():
        if key.startswith("_"):
            continue
        if key == "is_enabled" and value is True:
            continue                       # default — no documentation value
        if key == "breakpoint" and value is False:
            continue
        if isinstance(value, InstructionList):
            rows.append((humanize(key), f"{len(value)} nested steps"))
            continue
        if isinstance(value, ConditionList):
            rows.append((humanize(key), f"{len(value)} nested checks"))
            continue
        text = _display_value(value)
        if len(text) > 90:
            text = text[:87] + "…"
        rows.append((humanize(key), text))
    return rows


def _node_estimate_height(node: Node) -> float:
    return 30.0 + 15.0 * min(len(node.content_lines()), 4)


# ---- diagram flowable -------------------------------------------------------- #

class _DiagramFlowable(Flowable):
    """Vector rendering of the graph; every node is a link annotation."""

    def __init__(self, graph: Graph, order: dict[str, int], width: float,
                 max_height: float = 240.0):
        super().__init__()
        self.graph = graph
        self.order = order
        nodes = graph.nodes
        xs = [n.x for n in nodes] + [n.x + n.width for n in nodes]
        ys = [n.y for n in nodes] + [n.y + _node_estimate_height(n)
                                     for n in nodes]
        self.min_x, self.max_x = min(xs, default=0), max(xs, default=1)
        self.min_y, self.max_y = min(ys, default=0), max(ys, default=1)
        pad = 14.0
        graph_w = (self.max_x - self.min_x) or 1.0
        graph_h = (self.max_y - self.min_y) or 1.0
        self.scale = min(width / (graph_w + pad * 2),
                         max_height / (graph_h + pad * 2), 1.0)
        self.pad = pad
        self.width = width
        self.height = (graph_h + pad * 2) * self.scale

    def _pos(self, x: float, y: float) -> tuple[float, float]:
        # model space -> flowable space (y grows downwards in the model)
        fx = (x - self.min_x + self.pad) * self.scale
        fy = self.height - (y - self.min_y + self.pad) * self.scale
        return fx, fy

    def draw(self) -> None:
        from reportlab.lib.colors import HexColor
        canv = self.canv
        node_h = {n.guid: _node_estimate_height(n) for n in self.graph.nodes}

        canv.setStrokeColor(HexColor(TEXT_DIM))
        canv.setLineWidth(0.9)
        for edge in self.graph.edges:
            src = self.graph.node_by_guid(edge.src_node)
            dst = self.graph.node_by_guid(edge.dst_node)
            if src is None or dst is None:
                continue
            x1, y1 = self._pos(src.x + src.width, src.y + node_h[src.guid] / 2)
            x2, y2 = self._pos(dst.x, dst.y + node_h[dst.guid] / 2)
            dx = max(24.0 * self.scale, abs(x2 - x1) / 2)
            path = canv.beginPath()
            path.moveTo(x1, y1)
            path.curveTo(x1 + dx, y1, x2 - dx, y2, x2, y2)
            canv.drawPath(path, stroke=1, fill=0)

        for node in self.graph.nodes:
            w = node.width * self.scale
            h = node_h[node.guid] * self.scale
            x, y_top = self._pos(node.x, node.y)
            y = y_top - h
            canv.setFillColor(HexColor(BG_CARD))
            canv.setStrokeColor(HexColor(LINE))
            canv.setLineWidth(1)
            canv.roundRect(x, y, w, h, 3.5, stroke=1, fill=1)
            accent = HexColor(_accent(node))
            canv.setFillColor(accent)
            canv.rect(x, y_top - 3.0, w, 3.0, stroke=0, fill=1)

            def _fit(text, font, size, avail):
                if canv.stringWidth(text, font, size) <= avail:
                    return text
                while text and canv.stringWidth(text + "…", font, size) > avail:
                    text = text[:-1]
                return text + "…"

            canv.setFillColor(HexColor(TEXT_PRIMARY))
            canv.setFont(BODY_BOLD, 7.3)
            name = _fit(node.name, BODY_BOLD, 7.3, w - 24)
            canv.drawString(x + 5, y_top - 13.5, name)
            number = self.order.get(node.guid)
            if number is not None:
                canv.setFillColor(HexColor(TEXT_DIM))
                canv.setFont(BODY, 6.5)
                canv.drawRightString(x + w - 5, y_top - 13.5, f"{number:02d}")

            canv.setFillColor(HexColor(TEXT_MUTED))
            canv.setFont(BODY, 6.0)
            for i, line in enumerate(node.content_lines()[:4]):
                title = getattr(line, "title", None) or type(line).__name__
                title = _fit(str(title), BODY, 6.0, w - 10)
                canv.drawString(x + 5, y_top - 24 - i * 9.5, title)

            ax1, ay1 = canv.absolutePosition(x, y)
            ax2, ay2 = canv.absolutePosition(x + w, y + h)
            canv.linkAbsolute("", f"node-{node.guid}",
                              Rect=(ax1, ay1, ax2, ay2))


# ---- page painting ----------------------------------------------------------- #

def _page_painter(graph: Graph):
    from reportlab.lib.colors import HexColor

    def paint(canv, doc) -> None:
        width, height = A4
        canv.saveState()
        canv.setFillColor(HexColor(BG_DEEP))
        canv.rect(0, 0, width, height, stroke=0, fill=1)
        canv.setStrokeColor(HexColor(LINE))
        canv.setLineWidth(0.8)
        canv.line(18 * mm, 16 * mm, width - 18 * mm, 16 * mm)
        canv.setFillColor(HexColor(TEXT_DIM))
        canv.setFont(BODY, 8)
        canv.drawString(18 * mm, 11 * mm,
                        f"polytess Studio — {graph.name} · "
                        f"{graph.lineage.tag}")
        canv.drawRightString(A4[0] - 18 * mm, 11 * mm, f"{canv.getPageNumber()}")
        canv.restoreState()

    return paint


# ---- document assembly -------------------------------------------------------- #

def _styles() -> dict[str, ParagraphStyle]:
    return {
        "brand": ParagraphStyle("brand", fontName=BODY_BOLD, fontSize=10,
                                textColor=TEAL, spaceAfter=2),
        "h1": ParagraphStyle("h1", fontName=HEAD, fontSize=26, leading=31,
                             textColor=TEXT_PRIMARY, spaceAfter=4),
        "meta": ParagraphStyle("meta", fontName=BODY, fontSize=9, leading=13,
                               textColor=TEXT_MUTED, spaceAfter=10),
        "h2": ParagraphStyle("h2", fontName=HEAD, fontSize=15, leading=19,
                             textColor=TEXT_PRIMARY, spaceBefore=14,
                             spaceAfter=4),
        "toc": ParagraphStyle("toc", fontName=BODY, fontSize=10.5, leading=17,
                              textColor=TEXT_MUTED),
        "nodehead": ParagraphStyle("nodehead", fontName=HEAD, fontSize=14,
                                   leading=18, textColor=TEXT_PRIMARY,
                                   spaceBefore=6),
        "nodetype": ParagraphStyle("nodetype", fontName=BODY, fontSize=8.5,
                                   leading=12, textColor=TEXT_MUTED,
                                   spaceAfter=6),
        "itemhead": ParagraphStyle("itemhead", fontName=BODY_BOLD,
                                   fontSize=10, leading=14,
                                   textColor=TEXT_PRIMARY, spaceBefore=7),
        "itemmeta": ParagraphStyle("itemmeta", fontName=BODY, fontSize=8,
                                   leading=11, textColor=TEXT_DIM,
                                   spaceAfter=2),
        "body": ParagraphStyle("body", fontName=BODY, fontSize=9.5,
                               leading=13.5, textColor=TEXT_MUTED),
        "links": ParagraphStyle("links", fontName=BODY, fontSize=9,
                                leading=13, textColor=TEXT_MUTED,
                                spaceAfter=2),
    }


_KIND_LABEL = {
    StartNode: "Start — entry point of the workflow",
    ExitNode: "Exit — finishes the workflow",
    ActionsNode: "Actions — runs its steps in order",
    ConditionsNode: "Conditions — branches on success / fail",
    BranchNode: "Branch — first matching case wins",
    TriggerNode: "Trigger — fires on its event",
    SubGraphNode: "Sub-Workflow — runs another flow file",
}


def _param_table(rows: list[tuple[str, str]], width: float) -> Table:
    data = [[Paragraph(f'<font color="{TEXT_DIM}">{_esc(k)}</font>',
                       ParagraphStyle("k", fontName=BODY, fontSize=8.5,
                                      leading=11.5)),
             Paragraph(f'<font color="{TEXT_MUTED}">{_esc(v)}</font>',
                       ParagraphStyle("v", fontName=BODY, fontSize=8.5,
                                      leading=11.5))]
            for k, v in rows]
    table = Table(data, colWidths=[width * 0.32, width * 0.68])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_MID),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _group_title_of(graph: Graph, node) -> str:
    """Title of the canvas group whose frame contains *node* ('' if none;
    the innermost = smallest matching frame wins for nested groups)."""
    cx = node.x + getattr(node, "width", 220.0) / 2.0
    cy = node.y + 20.0
    best_title, best_area = "", None
    for group in graph.groups:
        if group.x <= cx <= group.x + group.width \
                and group.y <= cy <= group.y + group.height:
            area = group.width * group.height
            if best_area is None or area < best_area:
                best_title, best_area = group.title, area
    return best_title


def generate_flow_doc(graph: Graph, path: str, source_path: str = "") -> str:
    """Write the documentation PDF for *graph* to *path*; returns *path*."""
    _register_fonts()
    styles = _styles()
    story = _build_story(graph, styles, source_path)
    document = SimpleDocTemplate(
        path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=22 * mm,
        title=f"{graph.name} — polytess flow documentation",
        author="polytess Studio")
    painter = _page_painter(graph)
    document.build(story, onFirstPage=painter, onLaterPages=painter)
    return path


def _build_story(graph: Graph, styles, source_path: str = "") -> list:
    """The full document content as reportlab flowables — separated from
    the PDF build so tests can inspect the rendered text."""
    order_nodes = _node_order(graph)
    numbers = {n.guid: i + 1 for i, n in enumerate(order_nodes)}
    content_width = A4[0] - 36 * mm

    story: list = []
    story.append(Paragraph("polytess Studio", styles["brand"]))
    story.append(Paragraph(_esc(graph.name), styles["h1"]))
    lineage = graph.lineage
    meta_bits = [f"{lineage.tag}", f"family {lineage.flow_id[:8]}",
                 datetime.date.today().isoformat(),
                 f"{len(graph.nodes)} nodes · {len(graph.edges)} connections"]
    if lineage.has_parent:
        meta_bits.insert(1, f"branched from {lineage.parent_branch}"
                            f"·r{lineage.parent_revision}")
    if source_path:
        meta_bits.append(os.path.basename(source_path))
    story.append(Paragraph("&nbsp;&nbsp;·&nbsp;&nbsp;".join(
        _esc(b) for b in meta_bits), styles["meta"]))
    story.append(HRFlowable(width="100%", thickness=1, color=LINE,
                            spaceAfter=10))

    story.append(_DiagramFlowable(graph, numbers, content_width))
    story.append(Paragraph(
        f'<font color="{TEXT_DIM}" size="8">Click a node to jump to its '
        f"chapter.</font>", styles["meta"]))

    story.append(Paragraph("Contents", styles["h2"]))
    for node in order_nodes:
        number = numbers[node.guid]
        kind = _KIND_LABEL.get(type(node), type(node).__name__).split(" — ")[0]
        count = node.counter
        suffix = f" — {kind}" + (f", {count} item{'s' if count != 1 else ''}"
                                 if count else "")
        group_title = _group_title_of(graph, node)
        if group_title:
            suffix += f"  ·  {group_title}"
        story.append(Paragraph(
            f'<a href="#node-{node.guid}" color="{SKY}">'
            f"{number:02d}&nbsp;&nbsp;{_esc(node.name)}</a>"
            f'<font color="{TEXT_DIM}">{_esc(suffix)}</font>', styles["toc"]))
    story.append(Paragraph(
        f'<a href="#blackboard" color="{SKY}">Blackboard</a>'
        f'<font color="{TEXT_DIM}"> — variables, lists and tables</font>',
        styles["toc"]))
    story.append(PageBreak())

    for node in order_nodes:
        number = numbers[node.guid]
        accent = _accent(node)
        story.append(Paragraph(
            f'<a name="node-{node.guid}"/>'
            f'<font color="{accent}">{number:02d}</font>&nbsp;&nbsp;'
            f"{_esc(node.name)}", styles["nodehead"]))
        story.append(HRFlowable(width="100%", thickness=1.4, color=accent,
                                spaceAfter=3))
        kind = _KIND_LABEL.get(type(node), type(node).__name__)
        flags = []
        group_title = _group_title_of(graph, node)
        if group_title:
            flags.append(f"group “{group_title}”")
        if not node.enabled:
            flags.append("disabled")
        if node.breakpoint:
            flags.append("breakpoint set")
        flag_text = f"  ·  {', '.join(flags)}" if flags else ""
        story.append(Paragraph(_esc(kind + flag_text), styles["nodetype"]))

        connection_bits = []
        for edge in graph.in_edges(node):
            src = graph.node_by_guid(edge.src_node)
            if src is not None:
                connection_bits.append(
                    f'<font color="{TEXT_DIM}">in:</font>&nbsp;'
                    f'<a href="#node-{src.guid}" '
                    f'color="{SKY}">{numbers.get(src.guid, 0):02d} '
                    f"{_esc(src.name)}</a>")
        for edge in graph.out_edges(node):
            dst = graph.node_by_guid(edge.dst_node)
            if dst is not None:
                port = ("out" if edge.src_port == "out"
                        else f"out ({edge.src_port})")
                connection_bits.append(
                    f'<font color="{TEXT_DIM}">{port}:</font>&nbsp;'
                    f'<a href="#node-{dst.guid}" '
                    f'color="{SKY}">{numbers.get(dst.guid, 0):02d} '
                    f"{_esc(dst.name)}</a>")
        if connection_bits:
            story.append(Paragraph("&nbsp;&nbsp;·&nbsp;&nbsp;".join(
                connection_bits), styles["links"]))

        if isinstance(node, SubGraphNode) and node.file:
            story.append(Paragraph(f"Runs workflow file "
                                   f"<b>{_esc(node.file)}</b>",
                                   styles["body"]))
        if isinstance(node, ConditionsNode):
            story.append(Paragraph(
                f"Check mode: <b>{_esc(node.check_mode.upper())}</b> — "
                f"continues on the success or fail port.", styles["body"]))

        for item in node.content_lines():
            item_meta = get_meta(type(item))
            title = getattr(item, "title", None) or item_meta.title
            story.append(Paragraph(_esc(title), styles["itemhead"]))
            story.append(Paragraph(
                _esc(f"{item_meta.title}  ·  {item_meta.category}"),
                styles["itemmeta"]))
            if item_meta.description:
                story.append(Paragraph(_esc(item_meta.description),
                                       styles["body"]))
            rows = _item_fields(item)
            if rows:
                story.append(Spacer(0, 3))
                story.append(_param_table(rows, content_width))
        story.append(Spacer(0, 14))

    story.append(Paragraph('<a name="blackboard"/>Blackboard', styles["h2"]))
    story.append(HRFlowable(width="100%", thickness=1.4, color=TEAL,
                            spaceAfter=6))
    ungrouped = [v for v in graph.variables if not getattr(v, "group", "")]
    grouped: dict[str, list] = {}
    for variable in graph.variables:
        group = getattr(variable, "group", "")
        if group:
            grouped.setdefault(group, []).append(variable)

    def variable_rows(variables) -> list[tuple[str, str]]:
        return [(f"{v.name}  ({v.type_id})", _display_value(v.value))
                for v in variables]

    list_rows = [(f"{l.name}  (list of {l.type_id})",
                  ", ".join(str(i) for i in l.items[:6])
                  + ("…" if len(l.items) > 6 else ""))
                 for l in graph.lists]
    if ungrouped or list_rows:
        story.append(_param_table(variable_rows(ungrouped) + list_rows,
                                  content_width))
    for group in sorted(grouped):
        story.append(Paragraph(_esc(group), styles["itemhead"]))
        story.append(_param_table(variable_rows(grouped[group]),
                                  content_width))
    if not (ungrouped or grouped or list_rows):
        story.append(Paragraph("No graph variables defined.", styles["body"]))
    return story
