"""ACC posting (against a local mock server), folder watch with webhook notify, n8n workflow files."""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from aecdi.integrations.acc import payloads, post_issues, select_for_acc
from aecdi.integrations.watch import scan_once
from aecdi.outputs import write_all
from aecdi.pipeline import Inputs, run

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_project"


class Capture(BaseHTTPRequestHandler):
    received: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        Capture.received.append({"path": self.path, "headers": dict(self.headers), "body": body})
        out = json.dumps({"id": f"issue-{len(Capture.received)}"}).encode()
        self.send_response(201)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


class TestIntegrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Capture)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.tmp = Path(tempfile.mkdtemp())
        cls.out = cls.tmp / "out"
        cls.o = run(Inputs.discover(SAMPLE), cls.out)
        write_all(cls.o, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        Capture.received.clear()

    def test_policy_never_sends_unreviewed_probable_or_llm(self):
        fs = self.o.result.findings
        self.assertEqual(select_for_acc(fs, {}, "accepted"), [])
        drafts = select_for_acc(fs, {}, "accepted+confirmed-draft")
        self.assertTrue(drafts)
        self.assertTrue(all(f.tier == "confirmed" and f.method.startswith("rule:") and s == "draft" for f, s in drafts))
        prob = next(f for f in fs if f.tier == "probable")
        log = {prob.fingerprint(): {"decision": "accept"}}
        sel = select_for_acc(fs, log, "accepted")
        self.assertEqual([(f.id, s) for f, s in sel], [(prob.id, "open")])

    def test_post_live_to_mock_acc_and_idempotent(self):
        fs = self.o.result.findings
        log = {fs[0].fingerprint(): {"decision": "accept"}, fs[1].fingerprint(): {"decision": "accept"}}
        items = payloads(fs, log, issue_subtype_id="sub-123")
        res = post_issues(items, "b.proj-42", "tok", self.out, base_url=self.base, dry_run=False)
        self.assertEqual([r["status"] for r in res], ["created", "created"])
        self.assertEqual(len(Capture.received), 2)
        req = Capture.received[0]
        self.assertEqual(req["path"], "/construction/issues/v1/projects/proj-42/issues")   # "b." prefix removed
        self.assertEqual(req["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(req["body"]["status"], "open")
        self.assertEqual(req["body"]["issueSubtypeId"], "sub-123")
        self.assertIn("Evidence:", req["body"]["description"])
        res2 = post_issues(items, "proj-42", "tok", self.out, base_url=self.base, dry_run=False)
        self.assertTrue(all(r["status"].startswith("skipped") for r in res2))
        self.assertEqual(len(Capture.received), 2)

    def test_watch_runs_once_per_change_and_notifies(self):
        inbox = self.tmp / "inbox"
        shutil.copytree(SAMPLE, inbox / "clinic")
        outs = self.tmp / "watch_out"
        s1 = scan_once(inbox, outs, notify_url=self.base + "/webhook/aecdi-run")
        self.assertEqual(len(s1), 1)
        self.assertEqual(s1[0]["status"], "ok")
        self.assertTrue((outs / "clinic" / "QC_Issue_Log.xlsx").exists())
        self.assertEqual(Capture.received[-1]["body"]["project"], "clinic")
        self.assertEqual(scan_once(inbox, outs), [])                       # unchanged -> nothing to do
        time.sleep(0.05)
        p = inbox / "clinic" / "BOQ_RevB.xlsx"
        os.utime(p, None)
        self.assertEqual(len(scan_once(inbox, outs)), 1)                   # changed -> re-run
        self.assertEqual(len((outs / "runs.jsonl").read_text(encoding="utf-8").splitlines()), 2)

    def test_n8n_workflows_are_well_formed(self):
        for wf in sorted((ROOT / "n8n").glob("*.json")):
            data = json.loads(wf.read_text(encoding="utf-8"))
            names = {n["name"] for n in data["nodes"]}
            self.assertEqual(len(names), len(data["nodes"]), wf.name)
            for src, conn in data["connections"].items():
                self.assertIn(src, names)
                for branch in conn["main"]:
                    for link in branch:
                        self.assertIn(link["node"], names)
            self.assertTrue(all(n["type"].startswith("n8n-nodes-base.") for n in data["nodes"]))


if __name__ == "__main__":
    unittest.main()
