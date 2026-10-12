"""Unit tests for deterministic checks and cross-discipline coordination rules."""
import unittest
from aecdi.checks.crossdisc import _vph, NOMINAL
from aecdi.graph import TagHit
from aecdi.ingest.drawings import Sheet, Span

class TestDeterministicChecks(unittest.TestCase):
    def test_voltage_normalization(self):
        # 115V maps to nominal 120V
        self.assertEqual(_vph("115/1"), (120, 1))
        self.assertEqual(_vph("120/1"), (120, 1))
        # 208V maps to 208V
        self.assertEqual(_vph("208/3"), (208, 3))
        # 460V maps to nominal 480V
        self.assertEqual(_vph("460/3"), (480, 3))
        self.assertEqual(_vph("480/3"), (480, 3))

    def test_voltage_mismatch_detected(self):
        v_mech = _vph("460/3")  # -> (480, 3)
        v_elec = _vph("208/3")  # -> (208, 3)
        self.assertNotEqual(v_mech, v_elec)

    def test_tag_multiplier_parsing(self):
        # TagHit count property handles TYP. multipliers
        dummy_span = Span("VAV-1", (0,0,10,10), 8.0, (1,0))
        
        # Explicit multiplier: (TYP. OF 4) -> 4
        h1 = TagHit(None, dummy_span, (0,0,10,10), qualifier="(TYP. OF 4)")
        self.assertEqual(h1.count, 4)
        
        # Uncounted ambiguity: TYP. -> None (must abstain)
        h2 = TagHit(None, dummy_span, (0,0,10,10), qualifier="TYP.")
        self.assertIsNone(h2.count)
        
        # Single element (no qualifier) -> 1
        h3 = TagHit(None, dummy_span, (0,0,10,10), qualifier="")
        self.assertEqual(h3.count, 1)

if __name__ == "__main__":
    unittest.main()
