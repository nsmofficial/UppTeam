"""End-to-end integration test running the complete pipeline against sample project."""
import unittest
from pathlib import Path
from aecdi.pipeline import Inputs, run

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_project"

class TestPipelineE2E(unittest.TestCase):
    def test_pipeline_run_sample_project(self):
        inputs = Inputs.discover(SAMPLE_DIR)
        output = run(inputs)
        result = output.result
        
        # Verify run stats
        self.assertGreater(result.stats["sheets"], 0)
        self.assertGreater(result.stats["findings"], 0)
        self.assertEqual(result.stats["rejected_by_gate"], 0)
        self.assertEqual(
            result.stats["anchors_verified"], 
            result.stats["anchors_checked"]
        )
        
        # Every shipped finding must have >= min_evidence verified anchors
        for f in result.findings:
            self.assertGreaterEqual(len(f.evidence), f.min_evidence)
            for ev in f.evidence:
                self.assertTrue(ev.verified, f"Unverified anchor shipped in finding {f.id}")
                
        # Must have detected known defects from seed_00
        types = {f.type for f in result.findings}
        self.assertIn("cross_discipline_conflict", types)
        self.assertIn("quantity_mismatch", types)
        self.assertIn("missing_info", types)
        self.assertIn("dimension_conflict", types)
        self.assertIn("revision_issue", types)

if __name__ == "__main__":
    unittest.main()
