"""Unit tests for the anti-hallucination Evidence Gate."""
import unittest
from pathlib import Path
from aecdi.evidence import EvidenceGate
from aecdi.models import Evidence, Finding

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_project"

class TestEvidenceGate(unittest.TestCase):
    def setUp(self):
        self.files = {
            "CD_Set_RevB.pdf": SAMPLE_DIR / "CD_Set_RevB.pdf",
            "BOQ_RevB.xlsx": SAMPLE_DIR / "BOQ_RevB.xlsx",
            "Project_Manual.pdf": SAMPLE_DIR / "Project_Manual.pdf"
        }
        self.gate = EvidenceGate(self.files)

    def test_verify_valid_pdf_anchor(self):
        # Title block sheet number on page 0 of CD_Set_RevB.pdf
        ev = Evidence(
            doc="CD_Set_RevB.pdf",
            snippet="G-001",
            role="title block",
            sheet="G-001",
            page=0,
            bbox=(1040.0, 700.0, 1210.0, 770.0)
        )
        ok, msg = self.gate.verify_one(ev)
        self.assertTrue(ok, f"Verification failed: {msg}")

    def test_reject_fabricated_pdf_snippet(self):
        # Fabricated snippet that does not exist at that location
        ev = Evidence(
            doc="CD_Set_RevB.pdf",
            snippet="NON_EXISTENT_TAG_999",
            role="hallucinated tag",
            sheet="G-001",
            page=0,
            bbox=(1040.0, 700.0, 1210.0, 770.0)
        )
        ok, msg = self.gate.verify_one(ev)
        self.assertFalse(ok)
        self.assertIn("not found at cited location", msg)

    def test_verify_valid_xlsx_anchor(self):
        # First door item in BOQ
        ev = Evidence(
            doc="BOQ_RevB.xlsx",
            snippet="08-100",
            role="BOQ item",
            xlsx_sheet="Doors",
            row=4,
            cell="A4"
        )
        ok, msg = self.gate.verify_one(ev)
        self.assertTrue(ok, f"XLSX verification failed: {msg}")

    def test_reject_wrong_xlsx_cell(self):
        ev = Evidence(
            doc="BOQ_RevB.xlsx",
            snippet="999-WRONG",
            role="BOQ item",
            xlsx_sheet="Doors",
            row=4,
            cell="A4"
        )
        ok, msg = self.gate.verify_one(ev)
        self.assertFalse(ok)

    def test_gate_drops_finding_below_min_evidence(self):
        # A finding with 1 fabricated anchor and min_evidence=1
        f = Finding(
            type="missing_info",
            severity="high",
            tier="confirmed",
            statement="Fabricated conflict claim",
            entities=["DOOR:999"],
            sheets=["G-001"],
            evidence=[
                Evidence(
                    doc="CD_Set_RevB.pdf",
                    snippet="FAKE_SNIPPET",
                    sheet="G-001",
                    page=0,
                    bbox=(100.0, 100.0, 150.0, 150.0)
                )
            ],
            method="test:mock",
            confidence=0.9,
            min_evidence=1
        )
        shipped, rejected, stats = self.gate.apply([f])
        self.assertEqual(len(shipped), 0)
        self.assertEqual(len(rejected), 1)
        self.assertIn("REJECTED by evidence gate", rejected[0].rationale)

if __name__ == "__main__":
    unittest.main()
