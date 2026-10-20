"""Tests for canvas_layout.py — run with ``python3 -m unittest`` from this directory.

Ground-truth cases come from canvases the workbench itself saved (the
re-pack ran in the browser, then the canvas was pulled with the CLI), so the
expected numbers are what the workbench really computed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import canvas_layout as cl

UDF = (700.0, 500.0)


def kids(*sizes: tuple[float, float]) -> list[tuple[str, float, float]]:
    return [(f"c{i}", w, h) for i, (w, h) in enumerate(sizes)]


class FolderPacking(unittest.TestCase):
    def test_two_per_row_1555(self) -> None:
        # ploploploploplop / "Points": 1555 wide, four 700x500 → 2 rows, height 1190
        pos, h = cl.folder_grid_layout(1555, kids(UDF, UDF, UDF, UDF))
        self.assertEqual(h, 1190)
        self.assertEqual(pos["c0"], (40, 75))
        self.assertEqual(pos["c1"], (815, 75))
        self.assertEqual(pos["c2"], (40, 650))
        self.assertEqual(pos["c3"], (815, 650))

    def test_mixed_widths_wrap_1240(self) -> None:
        # qa_overnight_overlays_folder: 1240 wide, 420x500 + 720x500 → second wraps
        pos, h = cl.folder_grid_layout(1240, kids((420, 500), (720, 500)))
        self.assertEqual(pos["c1"], (40, 650))
        self.assertEqual(h, 1190)

    def test_exact_fit_1755(self) -> None:
        # ploploploploplop / "Stats": 40+700+75+900 = 1715 == 1755-40 → fits one row
        pos, h = cl.folder_grid_layout(1755, kids(UDF, (900, 400)))
        self.assertEqual(pos["c1"], (815, 75))
        self.assertEqual(h, 615)

    def test_three_per_row_2930(self) -> None:
        # ploploploploplop / "Maps": six 900x650 in 2930 → 3 per row, height 1490
        pos, h = cl.folder_grid_layout(2930, kids(*([(900, 650)] * 6)))
        self.assertEqual(
            [pos[f"c{i}"] for i in range(6)],
            [(40, 75), (1015, 75), (1990, 75), (40, 800), (1015, 800), (1990, 800)],
        )
        self.assertEqual(h, 1490)

    def test_one_row_3105(self) -> None:
        _, h = cl.folder_grid_layout(3105, kids(UDF, UDF, UDF, UDF))
        self.assertEqual(h, 615)

    def test_empty_folder(self) -> None:
        pos, h = cl.folder_grid_layout(1500, [])
        self.assertEqual(pos, {})
        self.assertEqual(h, 115)

    def test_first_child_never_wraps(self) -> None:
        pos, h = cl.folder_grid_layout(200, kids(UDF))
        self.assertEqual(pos["c0"], (40, 75))
        self.assertEqual(h, 615)

    def test_row_height_is_tallest_child(self) -> None:
        pos, h = cl.folder_grid_layout(1555, kids((700, 300), (700, 500), UDF))
        self.assertEqual(pos["c2"], (40, 650))  # 75 + 500 + 75

    def test_min_and_effective_width(self) -> None:
        self.assertEqual(cl.min_folder_width([700]), 780)
        self.assertEqual(cl.min_folder_width([]), 200)
        self.assertEqual(cl.effective_folder_width(100, [700]), 780)
        self.assertEqual(cl.effective_folder_width(None, [700]), 1500)
        self.assertEqual(cl.effective_folder_width(1554.6, [700]), 1555)


class Descriptions(unittest.TestCase):
    def test_empty_adds_nothing(self) -> None:
        self.assertEqual(cl.description_height("", 700), 0)
        self.assertEqual(cl.description_height("   ", 700), 0)

    def test_one_line(self) -> None:
        self.assertAlmostEqual(
            cl.description_height("One short line", 700), 4 + 8 + 31.5
        )

    def test_explicit_lines(self) -> None:
        self.assertEqual(cl.description_lines("a\nb\nc", 700), 3)
        self.assertEqual(cl.description_lines("a\n\n\nb", 700), 2)

    def test_wrapping(self) -> None:
        self.assertEqual(
            cl.description_lines("x" * 140, 700), 3
        )  # ~60 chars per line at 700px
        self.assertEqual(cl.description_lines("x" * 40, 700), 1)


class Arrange(unittest.TestCase):
    def test_three_udfs_per_row(self) -> None:
        pos = cl.arrange_rows(kids(UDF, UDF, UDF, UDF))
        self.assertEqual(pos["c0"], (0, 0))
        self.assertEqual(pos["c2"], (1550, 0))
        self.assertEqual(pos["c3"], (0, 575))

    def test_fixed_columns(self) -> None:
        pos = cl.arrange_rows(kids(UDF, UDF, UDF), columns=2)
        self.assertEqual(pos["c2"], (0, 575))

    def test_row_height_is_tallest(self) -> None:
        pos = cl.arrange_rows(kids((700, 500), (700, 700)), columns=2)
        self.assertEqual(pos["c0"], (0, 0))
        self.assertEqual(pos["c1"], (775, 0))
        pos = cl.arrange_rows(kids((700, 500), (700, 700), UDF), columns=2)
        self.assertEqual(pos["c2"], (0, 775))


class Placement(unittest.TestCase):
    def test_duplicate_order_right_bottom_top_left(self) -> None:
        ref = cl.Rect(0, 0, 700, 500)
        c = cl.placement_candidates_near(ref, (700, 500))
        self.assertEqual(c[:4], [(775, 0), (0, 575), (0, -575), (-775, 0)])

    def test_first_free_skips_taken(self) -> None:
        ref = cl.Rect(0, 0, 700, 500)
        taken = [ref, cl.Rect(775, 0, 700, 500)]
        self.assertEqual(
            cl.first_free(
                cl.placement_candidates_near(ref, (700, 500)), (700, 500), taken
            ),
            (0, 575),
        )

    def test_center_rings(self) -> None:
        c = cl.placement_candidates_center((1000, 1000), (700, 500))
        self.assertEqual(c[0], (650, 750))
        self.assertEqual(c[1], (650 + 775, 750))  # ring 1 right
        self.assertEqual(c[2], (650, 750 + 575))  # ring 1 bottom

    def test_touching_is_not_overlap(self) -> None:
        self.assertFalse(cl.Rect(0, 0, 700, 500).intersects(cl.Rect(700, 0, 700, 500)))
        self.assertTrue(cl.Rect(0, 0, 700, 500).intersects(cl.Rect(699, 0, 700, 500)))


CANVAS = """
type = "canvas"
version = 2

[canvas]
edges = [["a", "b"]]

[[canvas.nodes]]
type = "udf-folder"
udfName = "F"
folderName = "F"
childUdfOrder = ["a", "b", "inner"]
x = 0
y = 0
zIndex = 0
width = 1555
height = 100

[[canvas.nodes]]
type = "udf-folder"
udfName = "inner"
folderName = "inner"
childUdfOrder = ["c"]
x = 0
y = 0
zIndex = 0
width = 100
height = 100

[[canvas.nodes]]
udfName = "a"
x = 0
y = 0
zIndex = 1
width = 700
height = 500

[[canvas.nodes]]
udfName = "b"
description = "One line"
x = 0
y = 0
zIndex = 2
width = 700
height = 500

[[canvas.nodes]]
udfName = "c"
x = 0
y = 0
zIndex = 3
width = 700
height = 500

[[canvas.nodes]]
udfName = "top"
x = 100
y = 100
zIndex = 4
width = 700
height = 500
"""


class EndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "canvas.toml").write_text(CANVAS)
        for n in ("a", "b", "c", "top"):
            (self.dir / f"{n}.py").write_text("@fused.udf\ndef udf():\n    pass\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_check_reports_problems(self) -> None:
        c = cl.Canvas.load(self.dir)
        c.check()
        msgs = [p["msg"] for p in c.problems]
        self.assertIn("folder height will be recomputed by the workbench", msgs)
        self.assertIn("top-level nodes overlap", msgs)
        self.assertTrue(any(m.startswith("nested folders are not supported") for m in msgs))
        inner = c.nodes["inner"]
        self.assertIsNone(inner.parent)  # ignored by the workbench → top-level
        self.assertEqual((inner.eff_w, inner.eff_h), (780, 615))  # min width, one row
        outer = c.nodes["F"]
        # one row: a (500) + b (500 + 43.5 desc) → 75 + 543.5 + 40
        self.assertEqual(outer.eff_h, 75 + 543.5 + 40)
        self.assertNotIn("inner", outer.computed_children)

    def test_fix_makes_check_clean(self) -> None:
        c = cl.Canvas.load(self.dir)
        c.check()
        c.apply_folder_fix()
        c.apply_restack()
        c.write()
        # drop the unsupported nesting the way an author would
        doc = cl.tomllib.loads((self.dir / "canvas.toml").read_text())
        for n in doc["canvas"]["nodes"]:
            if n["udfName"] == "F":
                n["childUdfOrder"] = ["a", "b"]
        (self.dir / "canvas.toml").write_text(cl.dump_toml(doc))
        c2 = cl.Canvas.load(self.dir)
        c2.check()
        self.assertEqual([p for p in c2.problems if p["level"] == "error"], [])
        top = c2.nodes["top"]
        # top (y=100) is its own row below the folder row: keeps x, y = tallest in row 0 + 75
        row0_bottom = max(c2.nodes["F"].eff_h, c2.nodes["inner"].eff_h)
        self.assertEqual((top.x, top.y), (100, row0_bottom + 75))

    def test_toml_round_trip(self) -> None:
        doc = cl.tomllib.loads(CANVAS)
        self.assertEqual(cl.tomllib.loads(cl.dump_toml(doc)), doc)


if __name__ == "__main__":
    unittest.main()
