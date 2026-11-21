#!/usr/bin/env python3
"""Deterministic layout math for Fused ``canvas.toml`` files.

This is a line-for-line port of the workbench's own layout code, so the numbers
it prints are the numbers the workbench will compute when it loads the canvas:

- folder packing      -> client/src/udfrun/studio/utils/folder-layout.ts
- auto-arrange rows   -> client/src/udfrun/studio/utils/auto-arrange.ts
- new-node placement  -> client/src/udfrun/studio/utils/node-placement.ts
- constants           -> client/src/udfrun/studio/constants.ts

Needs Python 3.11+ (``tomllib``). No third-party packages.

Commands (run ``--help`` on any of them):

    canvas_layout.py check DIR            report overlaps / wrong folder sizes
    canvas_layout.py fix DIR              re-pack folders, arrange on overlap
    canvas_layout.py arrange DIR          re-lay top-level nodes in rows
    canvas_layout.py folder-size ...      compute a folder's size from children
    canvas_layout.py place DIR ...        where the workbench would put a node
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - older interpreters
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        sys.stderr.write(
            "canvas_layout.py needs Python 3.11+ (tomllib). "
            "Try: python3.12 canvas_layout.py ...  or  uv run --python 3.12 canvas_layout.py ...\n"
        )
        raise SystemExit(2)

# --------------------------------------------------------------------------- #
# Constants — mirror client/src/udfrun/studio/constants.ts
# --------------------------------------------------------------------------- #

GAP = 75  # STUDIO_NODE_GAP_PX: between nodes, rows, folder children
FOLDER_PADDING = 40  # NODE_DEFAULTS.UDF_FOLDER.PADDING: left / right / bottom inset
FOLDER_TOP_INSET = GAP  # folder-layout.ts: topInset = gap
FOLDER_MIN_WIDTH = 200  # NODE_DEFAULTS.UDF_FOLDER.MIN_WIDTH
FOLDER_DEFAULT_WIDTH = 1500  # NODE_DEFAULTS.UDF_FOLDER.DEFAULT_WIDTH
FOLDER_DEFAULT_COLOR = "#9370DB40"

# Default node body sizes the workbench uses when it creates a node.
DEFAULT_SIZES: dict[str, tuple[int, int]] = {
    "udf": (700, 500),  # .py — NODE_DEFAULTS.UDF
    "json": (700, 500),  # .json JSON-UI widget — same default as UDF
    "html": (700, 500),  # .html template node — same default as UDF
    "text": (350, 250),  # .md sticky note — NODE_DEFAULTS.TEXTBOX
}

# Auto-arrange: target row width = average node width * this (auto-arrange.ts)
ARRANGE_ROW_FACTOR = 3.5

# Description panel (node-description-panel.tsx + textbox-renderer.tsx).
# Rendered BELOW the node body, outside ``height``. The workbench measures the
# panel's offsetHeight in the browser and adds THAT to the child's height
# (folder-layout.ts getNodeDimensions): padding 4px top + 4px bottom, the
# ProseMirror paragraph(s) at 14px * scale * 1.5 line height, plus the last
# paragraph's 8px bottom margin. The 4px marginTop gap is outside offsetHeight
# and is not counted. offsetHeight is an integer, so the result is rounded.
# One line at the default scale: 4 + 4 + 31.5 + 8 = 47.5 → 48 (checked against
# canvases the workbench saved).
DESC_PANEL_GAP = 4  # marginTop between the node body and the panel: on screen, not in offsetHeight
DESC_PANEL_PADDING = 4
DESC_PARAGRAPH_MARGIN = 8
DESC_FONT_PX = 14
DESC_LINE_HEIGHT = 1.5
DESC_DEFAULT_SCALE = 1.5  # DEFAULT_NODE_DESCRIPTION_SCALE_FACTOR
DESC_AVG_CHAR_EM = 0.55  # rough average glyph width for wrap estimate
# The browser wraps text by real glyph widths; this script only estimates
# them. A folder whose declared height is within this many px per described
# child of the estimate is taken as the workbench's own measurement and kept.
DESC_TOLERANCE_PER_CHILD = 8

KIND_BY_EXT = {".py": "udf", ".json": "json", ".html": "html", ".md": "text"}


# --------------------------------------------------------------------------- #
# Pure geometry helpers
# --------------------------------------------------------------------------- #


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def intersects(self, other: Rect) -> bool:
        """Strict AABB intersection (touching edges do not count) — node-placement.ts."""
        return (
            self.x < other.right
            and self.right > other.x
            and self.y < other.bottom
            and self.bottom > other.y
        )

    def contains_point(self, px: float, py: float) -> bool:
        return self.x <= px <= self.right and self.y <= py <= self.bottom


def description_lines(
    text: str, width_px: float, scale: float = DESC_DEFAULT_SCALE
) -> int:
    """Estimate how many rendered lines a description takes at ``width_px``.

    The workbench measures this from the DOM; we can only estimate. Each
    paragraph wraps at roughly ``width / (font * 0.55)`` characters.
    """
    if not text or not text.strip():
        return 0
    font = DESC_FONT_PX * scale
    chars_per_line = max(8, int(width_px / (font * DESC_AVG_CHAR_EM)))
    lines = 0
    for para in text.replace("\r\n", "\n").split("\n"):
        stripped = para.strip()
        if not stripped:
            continue
        lines += max(1, math.ceil(len(stripped) / chars_per_line))
    return lines


def description_panel_px(lines: int, scale: float = DESC_DEFAULT_SCALE) -> float:
    """The panel's offsetHeight for ``lines`` rendered lines (0 for none)."""
    if lines <= 0:
        return 0.0
    line_px = DESC_FONT_PX * scale * DESC_LINE_HEIGHT
    exact = 2 * DESC_PANEL_PADDING + lines * line_px + DESC_PARAGRAPH_MARGIN
    return float(math.floor(exact + 0.5))


def description_height(
    text: str, width_px: float, scale: float = DESC_DEFAULT_SCALE
) -> float:
    """Estimated extra height (px) the description panel adds below a node."""
    return description_panel_px(description_lines(text, width_px, scale), scale)


def folder_grid_layout(
    folder_width: float,
    children: list[tuple[str, float, float]],
    padding: float = FOLDER_PADDING,
    gap: float = GAP,
) -> tuple[dict[str, tuple[float, float]], float]:
    """Port of ``computeFolderGridLayout`` (folder-layout.ts).

    ``children`` = ``[(name, width, effective_height), ...]`` in ``childUdfOrder``.
    ``effective_height`` must already include the description panel height.
    Returns ``({name: (x, y)}, folder_height)`` with child positions relative to
    the folder's top-left.
    """
    side = padding
    top = gap
    bottom = padding
    if not children:
        return {}, top + bottom

    usable = round(folder_width) - side * 2
    cur_x: float = side
    cur_y: float = top
    row_max_h = 0.0
    positions: dict[str, tuple[float, float]] = {}

    for name, w, h in children:
        if cur_x > side and cur_x + w > side + usable:
            cur_x = side
            cur_y += row_max_h + gap
            row_max_h = 0.0
        positions[name] = (cur_x, cur_y)
        cur_x += w + gap
        row_max_h = max(row_max_h, h)

    height = cur_y + row_max_h + bottom if cur_x > side else cur_y - gap + bottom
    return positions, height


def min_folder_width(
    child_widths: Iterable[float], padding: float = FOLDER_PADDING
) -> float:
    """Port of ``computeMinFolderWidth``: widest child + 2 * padding, at least 200."""
    widest = max(list(child_widths) or [0])
    return max(FOLDER_MIN_WIDTH, widest + padding * 2)


def _children_placed(folder_w: float, kids: list[Node]) -> bool:
    """True when every child sits where the workbench could have packed it:
    inside the folder's inset, none on top of another. Children an author
    left at 0,0 (or stacked) are not a measurement to keep."""
    rects: list[Rect] = []
    for k in kids:
        if k.x is None or k.y is None:
            return False
        if k.x < FOLDER_PADDING - 0.5 or k.y < FOLDER_TOP_INSET - 0.5:
            return False
        if k.x + k.eff_w > folder_w - FOLDER_PADDING + 0.5:
            return False
        r = Rect(k.x, k.y, k.eff_w, k.eff_h)
        if any(r.intersects(o) for o in rects):
            return False
        rects.append(r)
    return True


def effective_folder_width(
    declared: float | None, child_widths: Iterable[float]
) -> float:
    """Port of the width rule in ``recomputeFolderLayout``."""
    base = round(declared if declared is not None else FOLDER_DEFAULT_WIDTH)
    return round(max(base, min_folder_width(child_widths)))


def arrange_rows(
    items: list[tuple[str, float, float]],
    origin: tuple[float, float] = (0.0, 0.0),
    columns: int | None = None,
    gap: float = GAP,
) -> dict[str, tuple[float, float]]:
    """Port of ``autoArrangeNodes`` (auto-arrange.ts).

    ``items`` = ``[(name, width, height), ...]`` in the order they should flow.
    Without ``columns`` rows wrap when the running width (each item counted as
    ``width + gap``) would exceed ``average width * 3.5`` — the workbench rule.
    With ``columns`` every row holds exactly that many items (the workbench's
    own column mode under-fills because of the gap term; we use the plain count).
    """
    if not items:
        return {}
    avg_w = sum(w for _, w, _ in items) / len(items)
    target = avg_w * ARRANGE_ROW_FACTOR

    rows: list[list[tuple[str, float, float]]] = []
    row: list[tuple[str, float, float]] = []
    row_w = 0.0
    for item in items:
        step = item[1] + gap
        full = len(row) >= columns if columns else (row_w + step > target)
        if row and full:
            rows.append(row)
            row, row_w = [], 0.0
        row.append(item)
        row_w += step
    if row:
        rows.append(row)

    out: dict[str, tuple[float, float]] = {}
    y = origin[1]
    for r in rows:
        x = origin[0]
        row_h = max(h for _, _, h in r)
        for name, w, _ in r:
            out[name] = (x, y)
            x += w + gap
        y += row_h + gap
    return out


def placement_candidates_near(
    ref: Rect, size: tuple[float, float], direction: str = "right", gap: float = GAP
) -> list[tuple[float, float]]:
    """Candidate positions next to ``ref`` — node-placement.ts.

    ``direction="right"`` reproduces ``findNonOverlappingPosition`` (duplicate):
    right, bottom, top, left, corners, then far variants.
    Other directions reproduce ``findNonOverlappingPositionInDirection``.
    """
    tw, th = size
    right = (ref.right + gap, ref.y)
    bottom = (ref.x, ref.bottom + gap)
    top = (ref.x, ref.y - th - gap)
    left = (ref.x - tw - gap, ref.y)
    rb = (ref.right + gap, ref.bottom + gap)
    rt = (ref.right + gap, ref.y - th - gap)
    lb = (ref.x - tw - gap, ref.bottom + gap)
    lt = (ref.x - tw - gap, ref.y - th - gap)
    far = {
        "right": (ref.right + gap * 2, ref.y),
        "bottom": (ref.x, ref.bottom + gap * 2),
        "left": (ref.x - tw - gap * 2, ref.y),
        "top": (ref.x, ref.y - th - gap * 2),
    }
    sides = {"right": right, "bottom": bottom, "top": top, "left": left}
    adjacent = {
        "right": [rb, rt],
        "bottom": [lb, rb],
        "top": [lt, rt],
        "left": [lb, lt],
    }
    order = ["right", "bottom", "top", "left"]
    if direction == "right":
        return [
            right,
            bottom,
            top,
            left,
            rb,
            rt,
            lb,
            lt,
            far["right"],
            far["bottom"],
            far["left"],
            far["top"],
        ]
    first = [sides[direction]] + adjacent[direction]
    rest = [sides[d] for d in order if d != direction]
    corners = [c for c in (rb, rt, lb, lt) if c not in adjacent[direction]]
    return (
        first
        + rest
        + corners
        + [far[direction]]
        + [far[d] for d in order if d != direction]
    )


def placement_candidates_center(
    center: tuple[float, float],
    size: tuple[float, float],
    gap: float = GAP,
    rings: int = 5,
) -> list[tuple[float, float]]:
    """``findNonOverlappingPositionFromViewport``: centre, then rings right/bottom/left/top/diagonals."""
    w, h = size
    sx, sy = w + gap, h + gap
    bx, by = center[0] - w / 2, center[1] - h / 2
    out = [(bx, by)]
    for r in range(1, rings + 1):
        out += [
            (bx + r * sx, by),
            (bx, by + r * sy),
            (bx - r * sx, by),
            (bx, by - r * sy),
            (bx + r * sx, by + r * sy),
            (bx - r * sx, by + r * sy),
            (bx + r * sx, by - r * sy),
            (bx - r * sx, by - r * sy),
        ]
    return out


def first_free(
    candidates: list[tuple[float, float]], size: tuple[float, float], taken: list[Rect]
) -> tuple[float, float]:
    for x, y in candidates:
        r = Rect(x, y, size[0], size[1])
        if not any(r.intersects(t) for t in taken):
            return (x, y)
    return candidates[0]


# --------------------------------------------------------------------------- #
# Canvas model
# --------------------------------------------------------------------------- #


@dataclass
class Node:
    raw: dict[str, Any]
    name: str
    kind: str  # udf | json | html | text | folder | unknown
    x: float | None
    y: float | None
    width: float | None
    height: float | None
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    # computed
    eff_w: float = 0.0
    eff_h: float = 0.0  # body + description (nodes) / packed height (folders)
    desc_h: float = 0.0
    computed_children: dict[str, tuple[float, float]] = field(default_factory=dict)
    # folders: the packed height from estimated description panels, and the
    # declared height it was close enough to that the declared one is kept.
    packed_h: float = 0.0
    height_kept: bool = False

    @property
    def occupied_h(self) -> float:
        """Height this node takes on screen at the top level: the body, the
        description panel and the gap above it (inside a folder the
        workbench packs by offsetHeight alone, so ``eff_h`` has no gap)."""
        return self.eff_h + (DESC_PANEL_GAP if self.desc_h > 0 else 0)

    @property
    def is_folder(self) -> bool:
        return self.kind == "folder"


@dataclass
class Canvas:
    path: Path
    doc: dict[str, Any]
    nodes: dict[str, Node]
    order: list[str]
    problems: list[dict[str, Any]] = field(default_factory=list)

    def error(self, msg: str, **ctx: Any) -> None:
        self.problems.append({"level": "error", "msg": msg, **ctx})

    def warn(self, msg: str, **ctx: Any) -> None:
        self.problems.append({"level": "warn", "msg": msg, **ctx})

    def info(self, msg: str, **ctx: Any) -> None:
        self.problems.append({"level": "info", "msg": msg, **ctx})

    # -- loading ---------------------------------------------------------- #

    @classmethod
    def load(cls, directory: Path) -> Canvas:
        toml_path = directory / "canvas.toml"
        if not toml_path.exists():
            raise SystemExit(f"no canvas.toml in {directory}")
        doc = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        canvas_tbl = doc.get("canvas") or {}
        raw_nodes = canvas_tbl.get("nodes") or []
        stems = {
            p.stem: p.suffix for p in directory.iterdir() if p.suffix in KIND_BY_EXT
        }

        nodes: dict[str, Node] = {}
        order: list[str] = []
        c = cls(toml_path, doc, nodes, order)
        for i, raw in enumerate(raw_nodes):
            name = str(raw.get("udfName") or raw.get("folderName") or f"udf_{i}")
            if raw.get("type") == "udf-folder":
                kind = "folder"
            else:
                kind = KIND_BY_EXT.get(stems.get(name, ""), "unknown")
            if name in nodes:
                c.error("duplicate udfName", node=name)
                continue
            n = Node(
                raw=raw,
                name=name,
                kind=kind,
                x=_num(raw.get("x")),
                y=_num(raw.get("y")),
                width=_num(raw.get("width")),
                height=_num(raw.get("height")),
            )
            nodes[name] = n
            order.append(name)

        # parentage from childUdfOrder (hydrateFolderParentage)
        for name in order:
            n = nodes[name]
            if not n.is_folder:
                continue
            for child in n.raw.get("childUdfOrder") or []:
                child = str(child)
                if child not in nodes:
                    c.error(
                        "childUdfOrder names a node that does not exist",
                        folder=name,
                        child=child,
                    )
                    continue
                if nodes[child].parent is not None:
                    c.error(
                        "node listed in two folders",
                        node=child,
                        folders=[nodes[child].parent, name],
                    )
                    continue
                if child == name:
                    c.error("folder lists itself as a child", folder=name)
                    continue
                if nodes[child].is_folder:
                    # canvas.toml cannot nest folders: both the client and the server
                    # hydrators skip folder nodes when resolving childUdfOrder, so the
                    # inner folder is rendered top-level at its own x/y.
                    c.error(
                        "nested folders are not supported in canvas.toml — the inner folder "
                        "will render top-level at its own x/y; move it out of childUdfOrder",
                        folder=name, child=child,
                    )
                    continue
                nodes[child].parent = name
                n.children.append(child)
        return c

    # -- computing -------------------------------------------------------- #

    def compute(self) -> None:
        """Fill ``eff_w/eff_h`` for every node and ``computed_children`` for folders."""
        for n in self.nodes.values():
            if n.is_folder:
                continue
            dw, dh = DEFAULT_SIZES.get(n.kind, DEFAULT_SIZES["udf"])
            if n.width is None:
                self.error("missing width", node=n.name, default=dw)
            if n.height is None:
                self.error("missing height", node=n.name, default=dh)
            if n.x is None or n.y is None:
                self.error(
                    "missing x/y (the workbench cannot place this node)", node=n.name
                )
            n.eff_w = n.width if n.width is not None else dw
            body_h = n.height if n.height is not None else dh
            scale = _num(n.raw.get("nodeDescriptionScaleFactor")) or DESC_DEFAULT_SCALE
            n.desc_h = (
                0.0
                if n.kind == "text"
                else description_height(
                    str(n.raw.get("description") or ""), n.eff_w, scale
                )
            )
            n.eff_h = body_h + n.desc_h

        # folders: deepest first (reflowAllFolderLayouts)
        folders = [n for n in self.nodes.values() if n.is_folder]
        folders.sort(key=lambda f: -self._depth(f))
        for f in folders:
            if f.x is None or f.y is None:
                self.error("missing x/y", node=f.name)
            kids = [self.nodes[c] for c in f.children]
            kids_sizes = [(k.name, k.eff_w, k.eff_h) for k in kids]
            f.eff_w = effective_folder_width(f.width, [k.eff_w for k in kids])
            positions, height = folder_grid_layout(f.eff_w, kids_sizes)
            f.computed_children = positions
            f.packed_h = height
            # Description panels are measured by the browser; this script
            # estimates them. A declared height within the estimate's slack is
            # the workbench's own number: keep it, and lay out around it.
            slack = DESC_TOLERANCE_PER_CHILD * sum(1 for k in kids if k.desc_h > 0)
            width_ok = f.width is None or round(f.width) == f.eff_w
            f.height_kept = (
                f.height is not None and width_ok and slack > 0
                and abs(f.height - height) <= slack
                and _children_placed(f.eff_w, kids)
            )
            f.eff_h = f.height if f.height_kept and f.height is not None else height

    def _depth(self, n: Node) -> int:
        d = 0
        cur = n
        while cur.parent is not None:
            d += 1
            cur = self.nodes[cur.parent]
        return d

    def top_level(self) -> list[Node]:
        return [self.nodes[n] for n in self.order if self.nodes[n].parent is None]

    def rect(self, n: Node, with_description: bool = True) -> Rect:
        h = n.occupied_h if (with_description or n.is_folder) else (n.height or 0)
        return Rect(n.x or 0.0, n.y or 0.0, n.eff_w, h)

    # -- checks ----------------------------------------------------------- #

    def check(self) -> None:
        self.compute()
        for f in (n for n in self.nodes.values() if n.is_folder):
            if f.width is not None and round(f.width) != f.eff_w:
                self.error(
                    "folder width will be recomputed by the workbench",
                    folder=f.name,
                    declared=f.width,
                    computed=f.eff_w,
                )
            if f.height is not None and abs(f.height - f.eff_h) > 0.5:
                self.error(
                    "folder height will be recomputed by the workbench",
                    folder=f.name,
                    declared=f.height,
                    computed=f.eff_h,
                )
            elif f.height_kept and f.height is not None and abs(f.height - f.packed_h) > 0.5:
                self.info(
                    "folder height kept (description panels are measured by the browser; "
                    "the declared height is within the estimate's slack)",
                    folder=f.name,
                    declared=f.height,
                    estimated=f.packed_h,
                )
            for child, (cx, cy) in f.computed_children.items():
                k = self.nodes[child]
                if k.x is None or k.y is None:
                    continue
                if abs(k.x - cx) > 0.5 or abs(k.y - cy) > 0.5:
                    self.info(
                        "child x/y differs from the packed position (harmless: the workbench re-packs)",
                        folder=f.name,
                        child=child,
                        declared=[k.x, k.y],
                        computed=[cx, cy],
                    )
            if not f.children:
                self.warn("folder has no children", folder=f.name)

        tops = self.top_level()
        for n in tops:
            if n.x is not None and n.y is not None and (n.x < 0 or n.y < 0):
                self.warn(
                    "negative coordinates (allowed, but start at 0,0 for readability)",
                    node=n.name,
                    x=n.x,
                    y=n.y,
                )
        for i, a in enumerate(tops):
            ra_body = self.rect(a, with_description=False)
            ra_full = self.rect(a)
            for b in tops[i + 1 :]:
                rb_body = self.rect(b, with_description=False)
                rb_full = self.rect(b)
                if ra_body.intersects(rb_body):
                    self.error(
                        "top-level nodes overlap",
                        nodes=[a.name, b.name],
                        a=_r(ra_body),
                        b=_r(rb_body),
                    )
                elif ra_full.intersects(rb_full):
                    self.warn(
                        "description panel overlaps a neighbour (estimated — add row height for descriptions)",
                        nodes=[a.name, b.name],
                    )

    @property
    def has_errors(self) -> bool:
        return any(p["level"] == "error" for p in self.problems)

    # -- mutations -------------------------------------------------------- #

    def apply_folder_fix(self) -> list[str]:
        """Write computed folder width/height and child positions back into ``raw``."""
        changed: list[str] = []
        for f in (n for n in self.nodes.values() if n.is_folder):
            # Drop entries the workbench ignores anyway (nested folders, unknown names)
            order = [str(c) for c in (f.raw.get("childUdfOrder") or [])]
            kept = [c for c in order if c in f.children]
            if kept != order:
                f.raw["childUdfOrder"] = kept
                changed.append(f.name)
            if _set_num(f.raw, "width", f.eff_w) | _set_num(f.raw, "height", f.eff_h):
                changed.append(f.name)
            if f.height_kept:
                # The workbench measured this folder; its child positions are
                # the real ones too, and this script's are only estimates.
                f.width, f.height = f.eff_w, f.eff_h
                continue
            for child, (cx, cy) in f.computed_children.items():
                k = self.nodes[child]
                if _set_num(k.raw, "x", cx) | _set_num(k.raw, "y", cy):
                    changed.append(child)
            f.width, f.height = f.eff_w, f.eff_h
        return changed

    def apply_restack(self, gap: float = GAP, row_tolerance: float = 40.0, keep_gaps: bool = False) -> list[str]:
        """Keep the author's rows and columns, only open the gaps the workbench needs.

        Top-level nodes whose ``y`` is within ``row_tolerance`` form a row. Inside
        a row nodes keep their order and get ``x = prev.right + gap``; each row
        gets ``y = prev_row.bottom + gap`` where bottom includes folder packing
        and description panels. The first node keeps its ``x``/``y``. With
        ``keep_gaps`` nothing moves left or up (gaps only open, never close).
        """
        tops = sorted(self.top_level(), key=lambda n: ((n.y or 0), (n.x or 0)))
        rows: list[list[Node]] = []
        for n in tops:
            if rows and abs((n.y or 0) - (rows[-1][0].y or 0)) <= row_tolerance:
                rows[-1].append(n)
            else:
                rows.append([n])
        changed: list[str] = []
        prev_bottom: float | None = None
        for row in rows:
            row.sort(key=lambda n: (n.x or 0))
            row_y = row[0].y or 0.0
            if prev_bottom is not None:
                row_y = max(row_y, prev_bottom + gap) if keep_gaps else prev_bottom + gap
            prev_right: float | None = None
            bottom = row_y
            for n in row:
                x = n.x or 0.0
                if prev_right is not None:
                    x = max(x, prev_right + gap) if keep_gaps else prev_right + gap
                if _set_num(n.raw, "x", x) | _set_num(n.raw, "y", row_y):
                    changed.append(n.name)
                n.x, n.y = x, row_y
                prev_right = x + n.eff_w
                bottom = max(bottom, row_y + n.occupied_h)
            prev_bottom = bottom
        return changed

    def apply_arrange(
        self, columns: int | None = None, origin: tuple[float, float] | None = None
    ) -> list[str]:
        """Re-lay top-level nodes in rows. Order = current reading order (y, then x)."""
        tops = self.top_level()
        tops_sorted = sorted(tops, key=lambda n: (round((n.y or 0) / 50), n.x or 0))
        if origin is None:
            origin = (
                (min((n.x or 0) for n in tops), min((n.y or 0) for n in tops))
                if tops
                else (0.0, 0.0)
            )
        items = [(n.name, n.eff_w, n.occupied_h) for n in tops_sorted]
        pos = arrange_rows(items, origin=origin, columns=columns)
        changed: list[str] = []
        for name, (x, y) in pos.items():
            n = self.nodes[name]
            if _set_num(n.raw, "x", x) | _set_num(n.raw, "y", y):
                changed.append(name)
            n.x, n.y = x, y
        return changed

    def write(self) -> None:
        self.path.write_text(dump_toml(self.doc), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Small helpers + a minimal TOML writer (stdlib has none)
# --------------------------------------------------------------------------- #


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _clean(v: float) -> int | float:
    """A number as the workbench stores it: integral values as ints, the rest
    untouched (rounding would make every rewrite a change the sync has to
    push)."""
    return int(v) if float(v).is_integer() else v


def _set_num(raw: dict[str, Any], key: str, value: float) -> bool:
    new = _clean(value)
    if raw.get(key) == new:
        return False
    raw[key] = new
    return True


def _r(r: Rect) -> list[float]:
    return [_clean(r.x), _clean(r.y), _clean(r.w), _clean(r.h)]




_BASIC_ESCAPES = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\f": "\\f",
                  "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _needs_escape(c: str) -> bool:
    return c < " " or c == "\x7f"


def _basic_str(s: str) -> str:
    out = []
    for c in s:
        if c in _BASIC_ESCAPES:
            out.append(_BASIC_ESCAPES[c])
        elif _needs_escape(c):
            out.append(f"\\u{ord(c):04X}")
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def _toml_str(s: str) -> str:
    """A string as rtoml (toml_edit) writes it: a literal string when that
    saves escaping a backslash or a double quote, else a basic string with
    escapes; the multi-line forms when the text holds a newline."""
    control = any(_needs_escape(c) and c != "\n" for c in s)
    if "\n" in s and not control:
        if ("\\" in s or '"' in s) and "'''" not in s:
            return "'''\n" + s + "'''"
        body = s.replace("\\", "\\\\").replace('"""', '""\\"')
        return '"""\n' + body + '"""'
    if not control and ("\\" in s or '"' in s) and "'" not in s:
        return "'" + s + "'"
    return _basic_str(s)


def _toml_key(k: str) -> str:
    return k if k and all(c.isascii() and (c.isalnum() or c in "_-") for c in k) else _basic_str(k)


def _toml_float(v: float) -> str:
    if v != v:
        return "nan"
    if v in (math.inf, -math.inf):
        return "inf" if v > 0 else "-inf"
    text = repr(v)
    if "e" in text or "E" in text:
        # rtoml writes every float positionally, shortest digits, never 1e16
        from decimal import Decimal
        text = format(Decimal(text), "f")
        if "." not in text:
            text += ".0"
    return text


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return _toml_float(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return _toml_str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(i) for i in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_toml_key(k)} = {_toml_value(x)}" for k, x in v.items()) + " }"
    raise TypeError(f"cannot write {type(v).__name__} to TOML")


def _is_aot(v: Any) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(i, dict) for i in v)


def _emit_table(
    lines: list[str], path: str, table: dict[str, Any], header: str | None
) -> None:
    """One table in the layout ``rtoml`` writes — the same library the Fused
    server and fused-render's sync use for canvas.toml, so a file this
    script rewrites differs from theirs only where a number changed: keys in
    document order, scalars first, then arrays of tables, then sub-tables;
    arrays (edges included) inline on one line; a blank line before every
    table header. ``path`` is the dotted key of ``table`` ("" at the root),
    ``header`` the line that opens it (None at the root)."""
    keys = list(table)
    plain = [k for k in keys if not isinstance(table[k], (dict, list))]
    arrays = [k for k in keys if isinstance(table[k], list) and not _is_aot(table[k])]
    scalars = plain + arrays  # rtoml: plain values first, then arrays, in document order
    aots = [k for k in keys if _is_aot(table[k])]
    sub_tables = [k for k in keys if isinstance(table[k], dict)]
    # rtoml writes a table's header only when the table has values of its
    # own (or nothing at all); a table that only holds sub-tables is implied.
    if header is not None and (scalars or not (aots or sub_tables) or header.startswith("[[")):
        if lines:
            lines.append("")
        lines.append(header)
    for k in scalars:
        lines.append(f"{_toml_key(k)} = {_toml_value(table[k])}")
    for k in aots:
        name = f"{path}.{_toml_key(k)}" if path else _toml_key(k)
        for item in table[k]:
            _emit_table(lines, name, item, f"[[{name}]]")
    for k in sub_tables:
        name = f"{path}.{_toml_key(k)}" if path else _toml_key(k)
        _emit_table(lines, name, table[k], f"[{name}]")


def dump_toml(doc: dict[str, Any]) -> str:
    lines: list[str] = []
    _emit_table(lines, "", doc, None)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _print_problems(c: Canvas, as_json: bool) -> None:
    if as_json:
        print(json.dumps(c.problems, indent=2))
        return
    if not c.problems:
        print("ok: no layout problems")
        return
    for p in c.problems:
        ctx = {k: v for k, v in p.items() if k not in ("level", "msg")}
        print(f"{p['level']:5} {p['msg']}" + (f"  {json.dumps(ctx)}" if ctx else ""))


def _print_summary(c: Canvas) -> None:
    for n in c.top_level():
        kind = "folder" if n.is_folder else n.kind
        extra = f" desc+{_clean(n.desc_h)}" if n.desc_h else ""
        print(
            f"  {n.name:30} {kind:6} @({_clean(n.x or 0)}, {_clean(n.y or 0)}) {_clean(n.eff_w)}x{_clean(n.eff_h)}{extra}"
        )
        if n.is_folder:
            for child, (cx, cy) in n.computed_children.items():
                k = c.nodes[child]
                print(
                    f"    {child:28} {k.kind:6} @({_clean(cx)}, {_clean(cy)}) {_clean(k.eff_w)}x{_clean(k.eff_h)}"
                    + (f" desc+{_clean(k.desc_h)}" if k.desc_h else "")
                )


def cmd_check(args: argparse.Namespace) -> int:
    c = Canvas.load(Path(args.dir))
    c.check()
    if not args.json:
        _print_summary(c)
    _print_problems(c, args.json)
    return 1 if c.has_errors else 0


def cmd_fix(args: argparse.Namespace) -> int:
    c = Canvas.load(Path(args.dir))
    c.check()
    changed = c.apply_folder_fix()
    if args.arrange:
        changed += c.apply_arrange(columns=args.columns)
    else:
        changed += c.apply_restack(keep_gaps=args.keep_gaps)
    if args.dry_run:
        print("would change:", sorted(set(changed)) or "nothing")
    else:
        c.write()
        print("updated:", sorted(set(changed)) or "nothing")
    # re-check after the fix
    c2 = Canvas.load(Path(args.dir)) if not args.dry_run else c
    c2.problems = []
    c2.check()
    _print_problems(c2, args.json)
    return 1 if c2.has_errors else 0


def cmd_arrange(args: argparse.Namespace) -> int:
    c = Canvas.load(Path(args.dir))
    c.compute()
    c.apply_folder_fix()
    origin = tuple(float(v) for v in args.origin.split(",")) if args.origin else None
    changed = c.apply_arrange(columns=args.columns, origin=origin)  # type: ignore[arg-type]
    if args.dry_run:
        print("would move:", changed or "nothing")
        _print_summary(c)
    else:
        c.write()
        print("moved:", changed or "nothing")
        c2 = Canvas.load(Path(args.dir))
        c2.check()
        _print_summary(c2)
        _print_problems(c2, False)
    return 0


def cmd_folder_size(args: argparse.Namespace) -> int:
    children: list[tuple[str, float, float]] = []
    for i, spec in enumerate(args.children.split(",")):
        spec = spec.strip()
        if not spec:
            continue
        parts = spec.split("x")
        w, h = float(parts[0]), float(parts[1])
        desc_lines = int(parts[2]) if len(parts) > 2 else 0
        children.append((f"child_{i}", w, h + description_panel_px(desc_lines)))
    width = effective_folder_width(args.width, [w for _, w, _ in children])
    positions, height = folder_grid_layout(width, children)
    rows = len({y for _, y in positions.values()})
    out = {
        "width": _clean(width),
        "height": _clean(height),
        "rows": rows,
        "children": {k: [_clean(x), _clean(y)] for k, (x, y) in positions.items()},
    }
    print(
        json.dumps(out, indent=2)
        if args.json
        else f"width = {out['width']}\nheight = {out['height']}\nrows = {rows}\nchildren = {out['children']}"
    )
    return 0


def cmd_place(args: argparse.Namespace) -> int:
    c = Canvas.load(Path(args.dir))
    c.compute()
    w, h = (float(v) for v in args.size.lower().split("x"))
    taken = [c.rect(n) for n in c.top_level()]
    if args.near:
        ref = c.nodes.get(args.near)
        if ref is None or ref.parent is not None:
            raise SystemExit(f"--near must name a top-level node (got {args.near!r})")
        cands = placement_candidates_near(c.rect(ref), (w, h), args.direction)
    else:
        cx, cy = (float(v) for v in args.center.split(","))
        cands = placement_candidates_center((cx, cy), (w, h))
    x, y = first_free(cands, (w, h), taken)
    print(
        json.dumps(
            {"x": _clean(x), "y": _clean(y), "width": _clean(w), "height": _clean(h)}
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser(
        "check", help="report overlaps and folder sizes the workbench will change"
    )
    s.add_argument("dir")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser(
        "fix", help="re-pack folders and open the gaps between top-level rows/columns"
    )
    s.add_argument("dir")
    s.add_argument(
        "--arrange",
        action="store_true",
        help="re-flow the top level like the workbench auto-arrange instead of keeping your rows",
    )
    s.add_argument("--columns", type=int, help="fixed nodes per row for --arrange")
    s.add_argument("--keep-gaps", action="store_true", help="only open gaps that are too small; never pull nodes closer")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_fix)

    s = sub.add_parser(
        "arrange", help="lay top-level nodes out in rows (workbench auto-arrange)"
    )
    s.add_argument("dir")
    s.add_argument("--columns", type=int)
    s.add_argument(
        "--origin", help="x,y of the first node (default: current min x / min y)"
    )
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_arrange)

    s = sub.add_parser(
        "folder-size", help="compute a folder's packed size from its children"
    )
    s.add_argument(
        "--width",
        type=float,
        default=FOLDER_DEFAULT_WIDTH,
        help="declared folder width (default 1500)",
    )
    s.add_argument(
        "--children",
        required=True,
        help="comma list of WxH or WxHxDESCLINES, e.g. 700x500,700x500x2",
    )
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_folder_size)

    s = sub.add_parser(
        "place",
        help="first free slot for a new node, using the workbench's candidate order",
    )
    s.add_argument("dir")
    s.add_argument("--size", default="700x500")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--near",
        help="top-level node to place next to (duplicate / connect-to-create behaviour)",
    )
    g.add_argument(
        "--center",
        help="x,y flow point to spiral out from (toolbar 'add node' behaviour)",
    )
    s.add_argument(
        "--direction", choices=["right", "bottom", "top", "left"], default="right"
    )
    s.set_defaults(fn=cmd_place)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
