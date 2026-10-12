"""Reviewer feedback -> regression loop, QC-log scoring, LLM evaluation harness, live Claude client wiring."""
import json
import os
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from aecdi.feedback import build_cases, regress, save_cases
from aecdi.llm_eval import evaluate, labelled_projects, oracle_mock
from aecdi.outputs import write_all
from aecdi.pipeline import Inputs, run
from aecdi.qclog import score_qc_log

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_project"


class TestFeedbackAndQcLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.out = cls.tmp / "out"
        cls.o = run(Inputs.discover(SAMPLE), cls.out)
        write_all(cls.o, cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_feedback_to_regression_cases(self):
        fs = self.o.result.findings
        acc, rej, dup = fs[0], fs[1], fs[2]
        with (self.out / "review_log.jsonl").open("w", encoding="utf-8") as fh:
            for f, d, reason in ((acc, "accept", None), (rej, "reject", "Not a discrepancy (design intent)"),
                                 (dup, "reject", "Duplicate of another finding")):
                fh.write(json.dumps({"finding_id": f.id, "fingerprint": f.fingerprint(), "decision": d,
                                     "reason": reason, "reviewer": "t"}) + "\n")
        cases = build_cases(self.out, SAMPLE)
        self.assertEqual(len(cases), 2)                                    # duplicates are not regression cases
        path = self.tmp / "cases.jsonl"
        self.assertEqual(save_cases(cases, path), 2)
        self.assertEqual(save_cases(cases, path), 2)                       # idempotent
        rep = regress(path)
        self.assertEqual(rep["summary"]["accepted_still_found"], 1)
        self.assertEqual(rep["summary"]["known_false_positives"], 1)
        self.assertEqual(rep["summary"]["regressions"], 0)

    def test_qc_log_scoring(self):
        res = score_qc_log(self.out / "findings.json", ROOT / "eval_templates" / "example_qc_log_sample_project.csv",
                           self.tmp / "match.xlsx")
        self.assertEqual(res["covered"], 27)                               # 2 issues marked not covered
        self.assertGreaterEqual(res["provisional_recall"], 0.9)
        self.assertTrue((self.tmp / "match.xlsx").exists())


class TestLlmEvalHarness(unittest.TestCase):
    def test_metrics_and_consistency(self):
        projects = labelled_projects([SAMPLE])
        perfect = evaluate(projects, oracle_mock(projects), runs=2)
        self.assertEqual(perfect["consistency"], 1.0)
        self.assertTrue(all(r["precision"] == 1.0 and r["recall"] == 1.0 for r in perfect["runs"]))
        noisy = evaluate(projects, oracle_mock(projects, noise=0.3, seed=1), runs=3)
        self.assertLess(noisy["consistency"], 1.0)


class FakeAnthropic(BaseHTTPRequestHandler):
    seen: list = []
    reply: dict = {}

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        FakeAnthropic.seen.append({"path": self.path, "headers": dict(self.headers), "body": body})
        out = json.dumps({"id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                          "content": [{"type": "text", "text": json.dumps(FakeAnthropic.reply["json"])}],
                          "stop_reason": FakeAnthropic.reply.get("stop", "end_turn"), "stop_sequence": None,
                          "usage": {"input_tokens": 10, "output_tokens": 5}}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


class TestAnthropicClientWiring(unittest.TestCase):
    """The live client against a local stand-in for the Messages API: request shape and response handling.
    It does not test the model; that needs an API key (aecdi llm-eval --client anthropic)."""

    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeAnthropic)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.env = {k: os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")}
        os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
        os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        for k, v in cls.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_request_shape_and_parse(self):
        from aecdi.llm.semantic import SCHEMA, SYSTEM, AnthropicClient
        FakeAnthropic.reply = {"json": {"conflicts": [], "unclear": []}}
        out = AnthropicClient().complete_json(SYSTEM, "rows...", SCHEMA, {})
        self.assertEqual(out, {"conflicts": [], "unclear": []})
        req = FakeAnthropic.seen[-1]
        self.assertTrue(req["path"].startswith("/v1/messages"))
        self.assertEqual(req["body"]["model"], "claude-opus-5-5")
        self.assertEqual(req["body"]["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(req["body"]["fallbacks"], "default")
        self.assertIn("server-side-fallback", req["headers"].get("anthropic-beta", ""))

    def test_refusal_abstains_and_truncation_raises(self):
        from aecdi.llm.semantic import SCHEMA, SYSTEM, AnthropicClient
        FakeAnthropic.reply = {"json": {}, "stop": "refusal"}
        out = AnthropicClient().complete_json(SYSTEM, "x", SCHEMA, {})
        self.assertEqual(out["conflicts"], [])
        self.assertTrue(out["unclear"])
        FakeAnthropic.reply = {"json": {}, "stop": "max_tokens"}
        with self.assertRaises(RuntimeError):
            AnthropicClient().complete_json(SYSTEM, "x", SCHEMA, {})

    def test_end_to_end_semantic_run_through_gate(self):
        """A full pipeline run with the live client: the stand-in returns one correct and one invented citation."""
        from aecdi.llm.semantic import AnthropicClient
        FakeAnthropic.reply = {"json": {"conflicts": [
            {"element": "DOOR:101", "attribute": "FIRE RATING", "schedule_value": "90 MIN", "paragraph_id": "08 14 16 2.1.C",
             "spec_quote": "rated 20, 45 and 60 minutes", "explanation": "x", "severity": "high", "confidence": 0.8},
            {"element": "DOOR:101", "attribute": "FIRE RATING", "schedule_value": "90 MIN", "paragraph_id": "08 14 16 2.1.C",
             "spec_quote": "wood doors shall be rated 90 minutes", "explanation": "x", "severity": "high", "confidence": 0.8}],
            "unclear": []}}
        r = run(Inputs.discover(SAMPLE), llm_client=AnthropicClient()).result
        self.assertGreaterEqual(r.stats["llm_rejected_by_gate"], 1)        # the invented quote never ships
        door101 = next(f for f in r.findings if f.method == "rule:SPEC-002")
        self.assertIn("Corroborated by llm:claude-opus-5-5", door101.rationale)


if __name__ == "__main__":
    unittest.main()
