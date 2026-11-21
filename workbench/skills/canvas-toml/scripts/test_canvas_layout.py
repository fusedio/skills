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
            # offsetHeight the workbench measured for one line: 4 + 4 padding,
            # 31.5 line, 8 paragraph margin = 47.5 → 48 (newcans_324: a folder
            # of three described children is 13.5 px taller than 3 × 43.5)
            cl.description_height("One short line", 700), 48.0
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
        # one row: a (500) + b (500 + 48 desc) → 75 + 548 + 40
        self.assertEqual(outer.eff_h, 75 + 548 + 40)
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


# A canvas as the Fused server exports it and fused-render's sync writes it
# (rtoml's layout): keys in document order, edges on one line, a blank line
# before every table. Folder heights are what the workbench measured in the
# browser; the Data folder is 4 px off this script's estimate (1286), as a
# wrapped line the browser measured differently would be.
SERVER_CANVAS = """type = "canvas"
version = 2
name = "qa"

[canvas]
comments = []
edges = [["load_trips", "map_pickups"], ["load_trips", "chart_trip_counts"]]

[[canvas.nodes]]
udfName = "Data"
x = 0
y = 0
zIndex = 0
width = 780
height = 1290
type = "udf-folder"
folderName = "Data"
title = "Data"
childUdfOrder = ["load_trips", "tsunami_data"]

[[canvas.nodes]]
udfName = "load_trips"
x = 40
y = 75
zIndex = 1
width = 700
height = 500
title = "load_trips"
description = "NYC yellow taxi trips (Jan 2023 sample)"
visible = true
nodeDescriptionScaleFactor = 1.5

[[canvas.nodes]]
udfName = "tsunami_data"
x = 40
y = 698
zIndex = 2
width = 700
height = 500
title = "tsunami_data"
description = "NOAA historical tsunami events (plain table)"
visible = true
nodeDescriptionScaleFactor = 1.5

[[canvas.nodes]]
udfName = "map_pickups"
x = 855
y = 0
zIndex = 3
width = 700
height = 500
title = "map_pickups"
visible = true

[[canvas.nodes]]
udfName = "chart_trip_counts"
x = 1630
y = 0
zIndex = 4
width = 700
height = 500
title = "chart_trip_counts"
visible = true

[canvas.viewport]
x = 193.476
y = 74.09435458789119
zoom = 0.26794336563407317

[canvas.viewportBounds]
minX = -722.0766676181036
minY = -276.52990926851646
maxX = 3995.3381375919967
maxY = 4123.653678819069
"""


class ServerLayout(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "canvas.toml").write_text(SERVER_CANVAS)
        for n in ("load_trips", "tsunami_data", "map_pickups", "chart_trip_counts"):
            (self.dir / f"{n}.py").write_text("@fused.udf\ndef udf():\n    pass\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_dump_is_byte_identical_to_the_server_layout(self) -> None:
        self.assertEqual(cl.dump_toml(cl.tomllib.loads(SERVER_CANVAS)), SERVER_CANVAS)

    def test_multiline_string_round_trips(self) -> None:
        doc = {"canvas": {"nodes": [{"udfName": "n", "description": "two\nlines \"q\""}]}}
        self.assertEqual(cl.tomllib.loads(cl.dump_toml(doc)), doc)

    def test_workbench_measured_folder_height_is_kept(self) -> None:
        c = cl.Canvas.load(self.dir)
        c.check()
        self.assertEqual([p for p in c.problems if p["level"] == "error"], [])
        data = c.nodes["Data"]
        self.assertTrue(data.height_kept)
        self.assertEqual(data.eff_h, 1290)           # declared, used for row math
        self.assertEqual(data.packed_h, 75 + 548 + 75 + 548 + 40)  # the estimate
        self.assertEqual(c.apply_folder_fix(), [])
        self.assertEqual(c.apply_restack(), [])

    def test_fix_on_a_server_canvas_is_a_no_op(self) -> None:
        self.assertEqual(cl.cmd_fix(__import__("argparse").Namespace(
            dir=str(self.dir), arrange=False, columns=None, keep_gaps=False, dry_run=False, json=False)), 0)
        self.assertEqual((self.dir / "canvas.toml").read_text(), SERVER_CANVAS)

    def test_a_wrong_folder_height_is_still_an_error(self) -> None:
        text = SERVER_CANVAS.replace("height = 1290", "height = 1400")
        (self.dir / "canvas.toml").write_text(text)
        c = cl.Canvas.load(self.dir)
        c.check()
        msgs = [p["msg"] for p in c.problems if p["level"] == "error"]
        self.assertIn("folder height will be recomputed by the workbench", msgs)
        self.assertFalse(c.nodes["Data"].height_kept)


class WriterEdgeCases(unittest.TestCase):
    """Values as rtoml writes them (probed against rtoml 0.12 output)."""

    def rt(self, doc):
        self.assertEqual(cl.tomllib.loads(cl.dump_toml(doc)), doc)
        return cl.dump_toml(doc)

    def test_strings(self) -> None:
        cases = {
            "nl": ("two\nlines", 'nl = """\ntwo\nlines"""\n'),
            "bs": ("a\\b", "bs = 'a\\b'\n"),
            "q": ('say "hi"', "q = 'say \"hi\"'\n"),
            "both": ('a\\b\n"q"', "both = '''\na\\b\n\"q\"'''\n"),
            "tq": ("x'''y\nz", 'tq = """\nx\'\'\'y\nz"""\n'),
            "cr": ("a\rb", 'cr = "a\\rb"\n'),
            "ctl": ("a\x01b", 'ctl = "a\\u0001b"\n'),
            "delc": ("q\x7f", 'delc = "q\\u007F"\n'),
            "tab": ("a\tb", 'tab = "a\\tb"\n'),
            "sq": ("it's", 'sq = "it\'s"\n'),
            "uni": ("héllo", 'uni = "héllo"\n'),
        }
        for key, (value, want) in cases.items():
            with self.subTest(key=key):
                self.assertEqual(self.rt({key: value}), want)

    def test_floats_and_keys(self) -> None:
        cases = {
            "f1": (1e16, "f1 = 10000000000000000.0\n"),
            "f2": (1e-7, "f2 = 0.0000001\n"),
            "f3": (0.30000000000000004, "f3 = 0.30000000000000004\n"),
            "f5": (-0.0, "f5 = -0.0\n"),
            "f6": (123456789012345.6, "f6 = 123456789012345.6\n"),
            "a b": (1, '"a b" = 1\n'),
            "k.d": (2, '"k.d" = 2\n'),
            "ké": (3, '"ké" = 3\n'),
            "emptylist": ([], "emptylist = []\n"),
        }
        for key, (value, want) in cases.items():
            with self.subTest(key=key):
                self.assertEqual(self.rt({key: value}), want)
        self.assertEqual(cl.dump_toml({"n": float("nan"), "i": float("inf"), "m": float("-inf")}),
                         "n = nan\ni = inf\nm = -inf\n")

    def test_tables(self) -> None:
        self.assertEqual(self.rt({"empty": {}}), "[empty]\n")
        self.assertEqual(self.rt({"nested": {"a": {"b": 1}}}), "[nested.a]\nb = 1\n")
        self.assertEqual(
            self.rt({"n": [{"a": 1, "t": {"b": 2}, "m": [{"c": 3}]}]}),
            "[[n]]\na = 1\n\n[[n.m]]\nc = 3\n\n[n.t]\nb = 2\n")


class KeptHeightEdges(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for n in ("load_trips", "tsunami_data", "map_pickups", "chart_trip_counts"):
            (self.dir / f"{n}.py").write_text("@fused.udf\ndef udf():\n    pass\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_wrong_width_means_nothing_is_kept(self) -> None:
        (self.dir / "canvas.toml").write_text(SERVER_CANVAS.replace("width = 780", "width = 1600"))
        c = cl.Canvas.load(self.dir)
        c.check()
        self.assertFalse(c.nodes["Data"].height_kept)
        changed = c.apply_folder_fix()
        self.assertIn("Data", changed)
        self.assertIn("tsunami_data", changed)        # re-packed for the new column count
        self.assertEqual((c.nodes["Data"].width, c.nodes["Data"].height), (1600, c.nodes["Data"].eff_h))

    def test_kept_height_is_reported_as_info(self) -> None:
        (self.dir / "canvas.toml").write_text(SERVER_CANVAS)
        c = cl.Canvas.load(self.dir)
        c.check()
        infos = [p for p in c.problems if p["level"] == "info" and p["msg"].startswith("folder height kept")]
        self.assertEqual([(p["declared"], p["estimated"]) for p in infos], [(1290.0, 1286.0)])
        c.apply_folder_fix()
        self.assertEqual((c.nodes["Data"].width, c.nodes["Data"].height), (780, 1290.0))

    def test_children_at_the_origin_are_repacked_not_kept(self) -> None:
        text = SERVER_CANVAS.replace("x = 40\ny = 698\n", "x = 0\ny = 0\n")
        (self.dir / "canvas.toml").write_text(text)
        c = cl.Canvas.load(self.dir)
        c.check()
        self.assertFalse(c.nodes["Data"].height_kept)
        changed = c.apply_folder_fix()
        self.assertIn("tsunami_data", changed)
        self.assertEqual((c.nodes["tsunami_data"].raw["x"], c.nodes["tsunami_data"].raw["y"]), (40, 698))
        self.assertEqual(c.nodes["Data"].height, 1286)

    def test_top_level_occupancy_includes_the_panel_gap(self) -> None:
        # b sits 551 px under a's body; a's panel starts at 504 (4 px gap)
        # and ends at 552, so on screen they touch by one pixel.
        (self.dir / "canvas.toml").write_text(
            '[canvas]\nedges = []\n\n[[canvas.nodes]]\nudfName = "load_trips"\nx = 0\ny = 0\n'
            'width = 700\nheight = 500\ndescription = "one line"\n\n[[canvas.nodes]]\n'
            'udfName = "map_pickups"\nx = 0\ny = 551\nwidth = 700\nheight = 500\n')
        c = cl.Canvas.load(self.dir)
        c.check()
        self.assertEqual(c.nodes["load_trips"].occupied_h, 500 + 48 + 4)
        msgs = [p["msg"] for p in c.problems if p["level"] != "info"]
        self.assertTrue(any(m.startswith("description panel overlaps") for m in msgs), msgs)
        c.apply_restack()
        self.assertEqual(c.nodes["map_pickups"].y, 500 + 48 + 4 + 75)

    def test_no_described_children_means_no_slack(self) -> None:
        text = SERVER_CANVAS.replace('description = "NYC yellow taxi trips (Jan 2023 sample)"\n', "")
        text = text.replace('description = "NOAA historical tsunami events (plain table)"\n', "")
        (self.dir / "canvas.toml").write_text(text)
        c = cl.Canvas.load(self.dir)
        c.check()
        self.assertFalse(c.nodes["Data"].height_kept)
        self.assertIn("folder height will be recomputed by the workbench",
                      [p["msg"] for p in c.problems if p["level"] == "error"])


if __name__ == "__main__":
    unittest.main()
