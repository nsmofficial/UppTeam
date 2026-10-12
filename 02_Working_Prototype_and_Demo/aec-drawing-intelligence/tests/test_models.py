"""Unit tests for core data models and fingerprinting."""
import unittest
from aecdi.models import Evidence, Finding, RunResult

class TestModels(unittest.TestCase):
    def test_evidence_model(self):
        ev = Evidence(
            doc="CD_Set_RevB.pdf",
            snippet="D1",
            role="plan tag",
            sheet="A-101",
            page=1,
            bbox=(100.0, 150.0, 120.0, 165.0)
        )
        self.assertEqual(ev.doc, "CD_Set_RevB.pdf")
        self.assertIsNone(ev.verified)
        self.assertEqual(ev.bbox, (100.0, 150.0, 120.0, 165.0))

    def test_finding_fingerprint_deterministic(self):
        f1 = Finding(
            type="quantity_mismatch",
            severity="high",
            tier="confirmed",
            statement="Potential discrepancy: Door type D1 count mismatch.",
            entities=["DOOR:101", "DOORTYPE:D1"],
            sheets=["A-101", "A-601"],
            method="rule:QTY-001",
            confidence=0.95
        )
        f2 = Finding(
            type="quantity_mismatch",
            severity="high",
            tier="confirmed",
            statement="Different wording statement.",
            entities=["DOORTYPE:D1", "DOOR:101"],  # different order
            sheets=["A-601", "A-101"],             # different order
            method="rule:QTY-001",
            confidence=0.90
        )
        # Fingerprints must be equal regardless of entity/sheet list ordering
        self.assertEqual(f1.fingerprint(), f2.fingerprint())

    def test_finding_fingerprint_distinct(self):
        f1 = Finding(
            type="quantity_mismatch",
            severity="high",
            tier="confirmed",
            statement="Conflict 1",
            entities=["DOOR:101"],
            sheets=["A-101"],
            method="rule:QTY-001",
            confidence=0.95
        )
        f2 = Finding(
            type="quantity_mismatch",
            severity="high",
            tier="confirmed",
            statement="Conflict 2",
            entities=["DOOR:102"],
            sheets=["A-101"],
            method="rule:QTY-001",
            confidence=0.95
        )
        self.assertNotEqual(f1.fingerprint(), f2.fingerprint())

if __name__ == "__main__":
    unittest.main()
