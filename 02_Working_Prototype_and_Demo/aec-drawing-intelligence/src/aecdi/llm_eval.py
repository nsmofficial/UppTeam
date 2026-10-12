"""Evaluation harness for the LLM spec-vs-schedule check (separate from the rule benchmark).

    aecdi llm-eval --client mock --runs 3            harness self-test (scripted answers)
    aecdi llm-eval --client anthropic --runs 3       real model; needs an API key, costs tokens

Labelled cases come from the synthetic answer keys: an element (door or equipment row) is a
positive if a spec_conflict defect was seeded on it, otherwise a negative. For each run the
LLM findings that pass the evidence gate are the predictions. Reported:
  * precision / recall / F1 per run,
  * consistency: share of elements that get the same prediction in every run (the current Claude
    models do not accept a temperature setting, so variation must be measured, not assumed away),
  * gate rejections per run (fabricated or mis-cited claims the gate stopped),
  * the elements behind every error, for prompt or rule follow-up.
Re-run on every model or prompt change before deploying it.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .evidence import EvidenceGate
from .llm.semantic import MockClient, build_requests, run_semantic
from .pipeline import Inputs, run


def labelled_projects(dirs: list[Path]) -> list[dict]:
    out = []
    for d in dirs:
        key = json.loads((d / "answer_key.json").read_text(encoding="utf-8"))
        pos = {e for x in key["defects"] for s in x["accept"] if s["type"] == "spec_conflict" for e in s.get("entities", [])}
        out.append({"dir": d, "positives": pos})
    return out


def oracle_mock(projects: list[dict], noise: float = 0.0, seed: int = 0) -> MockClient:
    """Scripted 'model' for the harness self-test: answers from the answer key, optionally with random
    misses / false alarms so the metrics and consistency maths can be checked."""
    rng = random.Random(seed)
    graphs = {}

    def responder(meta):
        g = graphs[meta["_project"]]
        pos = meta["_positives"]
        req = next(r for r in build_requests(g) if r.section == meta["section"])
        sec = g.manual.sections[meta["section"]]
        conflicts = []
        for el, row in req.rows.items():
            is_pos = el in pos
            if noise and rng.random() < noise:
                is_pos = not is_pos
            if not is_pos:
                continue
            para = sec.paragraphs[0]
            col = row.table.headers[1]
            conflicts.append({"element": el, "attribute": col, "schedule_value": row.cells[1].text,
                              "paragraph_id": para.id, "spec_quote": para.text[:30], "explanation": "mock",
                              "severity": "high", "confidence": 0.8})
        return {"conflicts": conflicts, "unclear": []}

    client = MockClient(responder, "llm:mock-oracle" + (f"-noise{noise}" if noise else ""))
    client._graphs = graphs
    return client


def evaluate(projects: list[dict], client, runs: int = 3) -> dict:
    per_run, preds_by_run = [], []
    for k in range(runs):
        tp = fp = fn = rejected = 0
        preds = {}
        for pr in projects:
            base = run(Inputs.discover(pr["dir"]))
            g = base.graph
            if hasattr(client, "_graphs"):
                client._graphs[str(pr["dir"])] = g
                orig = client.responder
                client.responder = (lambda m, _o=orig, _p=pr: _o({**m, "_project": str(_p["dir"]), "_positives": _p["positives"]}))
            files = {g.drawings.doc: base.inputs.rev_b, g.manual.doc: base.inputs.spec}
            findings, _log = run_semantic(g, client)
            if hasattr(client, "_graphs"):
                client.responder = orig
            shipped, rej, _ = EvidenceGate(files).apply(findings)
            rejected += len(rej)
            predicted = {e for f in shipped if f.tier != "needs_review" for e in f.entities}
            elements = {el for r in build_requests(g) for el in r.rows}
            for el in elements:
                preds[(str(pr["dir"]), el)] = el in predicted
            tp += len(predicted & pr["positives"] & elements)
            fp += len(predicted - pr["positives"])
            fn += len((pr["positives"] & elements) - predicted)
        p = tp / (tp + fp) if tp + fp else 1.0
        r = tp / (tp + fn) if tp + fn else 1.0
        per_run.append({"run": k + 1, "tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3),
                        "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "gate_rejections": rejected})
        preds_by_run.append(preds)
    keys = set().union(*[set(x) for x in preds_by_run])
    stable = sum(1 for key in keys if len({pr.get(key) for pr in preds_by_run}) == 1)
    return {"client": client.name, "projects": len(projects), "runs": per_run,
            "consistency": round(stable / len(keys), 3) if keys else None, "elements": len(keys)}
