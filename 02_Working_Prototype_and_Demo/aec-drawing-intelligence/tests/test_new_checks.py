"""v1.2 checks: untagged doors, model-export mismatch, redline closure, metric units, scanned sheets."""
import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from aecdi.evaluation import score_project
from aecdi.pipeline import Inputs, run
from aecdi.synth.render import generate
from aecdi.units import parse_mm, parse_scale


class TestNewChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.imperial = generate(0, cls.tmp)
        cls.metric = generate(0, cls.tmp, units="metric")
        cls.clean = generate(0, cls.tmp, clean=True)
        cls.r_imp = run(Inputs.discover(cls.imperial)).result
        cls.r_met = run(Inputs.discover(cls.metric)).result
        cls.r_clean = run(Inputs.discover(cls.clean)).result

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def by(self, result, method):
        return [f for f in result.findings if f.method == method]

    def test_inputs_discovered(self):
        i = Inputs.discover(self.imperial)
        self.assertTrue(i.redlines.name.endswith("_REDLINES.pdf"))
        self.assertEqual(i.rev_a.name, "CD_Set_RevA.pdf")
        self.assertTrue(i.native.name.endswith(".txt"))

    def test_untagged_door_found_once(self):
        f = self.by(self.r_imp, "rule:MISS-011")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tier, "probable")
        self.assertEqual(self.by(self.r_clean, "rule:MISS-011"), [])

    def test_model_export_mismatch(self):
        f = self.by(self.r_imp, "rule:NATIVE-001")
        self.assertEqual(len(f), 1)
        self.assertIn("door 103", f[0].statement)
        self.assertEqual(len(f[0].evidence), 2)                          # sheet cell + Revit export line
        self.assertTrue(any(e.doc.endswith(".txt") and e.verified for e in f[0].evidence))
        self.assertEqual(self.by(self.r_clean, "rule:NATIVE-001"), [])

    def test_redline_closure(self):
        f = self.by(self.r_imp, "rule:MARKUP-001")
        self.assertEqual(len(f), 1)
        self.assertIn("DOOR 106", f[0].statement)
        status = {m["text"]: m["incorporated"] for m in self.r_imp.markups}
        self.assertEqual(sum(status.values()), 2)                         # the two clouded changes answer their markups
        self.assertTrue(all(m["incorporated"] for m in self.r_clean.markups))

    def test_all_seeded_defects_detected_no_false_positives(self):
        import json
        for d, r in ((self.imperial, self.r_imp), (self.metric, self.r_met), (self.clean, self.r_clean)):
            sc = score_project(r.findings, json.loads((d / "answer_key.json").read_text(encoding="utf-8")))
            self.assertEqual(sc["detected"], sc["defects"], d.name)
            self.assertEqual(sc["fp"], [], d.name)
            self.assertEqual(r.stats["anchors_checked"], r.stats["anchors_verified"])

    def test_metric_units(self):
        self.assertAlmostEqual(parse_scale("1:100"), 72 / 25.4 * 304.8 / 100, places=6)
        self.assertAlmostEqual(parse_mm("7620"), 25.0, places=6)
        self.assertIsNone(parse_mm("121"))                                 # door mark, not a dimension
        dims = self.by(self.r_met, "rule:DIM-001")
        self.assertTrue(any("7450 + 9100 + 7600 = 24150" in f.statement for f in dims))

    def _scan(self, page_no: int):
        """Copy of the project where one sheet of Rev B is an image-only scan."""
        proj = self.tmp / f"scanned_{page_no}"
        shutil.copytree(self.imperial, proj)
        src = pymupdf.open(self.imperial / "CD_Set_RevB.pdf")
        out = pymupdf.open()
        for i, page in enumerate(src):
            if i == page_no:
                pix = page.get_pixmap(dpi=100)
                np_ = out.new_page(width=page.rect.width, height=page.rect.height)
                np_.insert_image(np_.rect, pixmap=pix)
            else:
                out.insert_pdf(src, from_page=i, to_page=i)
        out.save(proj / "CD_Set_RevB.pdf")
        return run(Inputs.discover(proj)).result

    def test_scanned_schedule_abstains(self):
        r = self._scan(5)                                                  # M-601 equipment schedule scanned
        ing = self.by(r, "rule:ING-001")
        self.assertEqual(len(ing), 1)
        self.assertEqual(ing[0].tier, "needs_review")
        self.assertEqual(r.stats["unreadable_pages"], 1)
        # no schedule could be read, so no conclusions about equipment are drawn from its absence
        self.assertEqual([f for f in r.findings if f.method in ("rule:MISS-009", "rule:XD-001", "rule:XD-002",
                                                               "rule:XD-003", "rule:XD-004")], [])
        self.assertEqual(r.stats["anchors_checked"], r.stats["anchors_verified"])

    def test_scanned_plan_downgrades_completeness_findings(self):
        r = self._scan(4)                                                  # M-101 mechanical plan scanned
        self.assertEqual(len(self.by(r, "rule:ING-001")), 1)
        miss = [f for f in r.findings if f.method in ("rule:MISS-009", "rule:MISS-010")]
        self.assertTrue(miss)                                              # scheduled equipment no longer seen on a plan
        self.assertTrue(all(f.tier != "confirmed" for f in miss))


if __name__ == "__main__":
    unittest.main()
