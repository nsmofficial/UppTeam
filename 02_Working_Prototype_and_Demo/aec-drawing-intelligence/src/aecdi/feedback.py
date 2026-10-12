"""Reviewer feedback -> regression cases.

    aecdi feedback <out_dir> <project_dir>      add this project's review decisions to regression/cases.jsonl
    aecdi regress [regression/cases.jsonl]      re-run every project and check each case

An accepted finding becomes a case that must keep being found (a recall regression if it
disappears). A rejected finding (except 'duplicate') becomes a known false positive: it is
reported as 'still present' until a rule change removes it, then as 'fixed'. Cases are keyed by
the finding fingerprint (type + rule + entities + sheets), which is stable across runs.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .integrations.acc import load_review_log


def build_cases(out_dir: Path, project_dir: Path) -> list[dict]:
    result = json.loads((Path(out_dir) / "findings.json").read_text(encoding="utf-8"))
    by_fp = {}
    from .models import Finding
    for f in result["findings"]:
        by_fp[Finding(**f).fingerprint()] = f
    cases = []
    for key, e in load_review_log(out_dir).items():
        f = by_fp.get(key) or next((x for x in result["findings"] if x["id"] == e["finding_id"]), None)
        if f is None:
            continue
        fp = Finding(**f).fingerprint()
        if e["decision"] == "reject" and str(e.get("reason", "")).lower().startswith("duplicate"):
            continue
        cases.append({"project": str(Path(project_dir).resolve()), "fingerprint": fp, "type": f["type"],
                      "method": f["method"], "entities": f["entities"], "statement": f["statement"][:160],
                      "expect": "present" if e["decision"] == "accept" else "absent",
                      "reason": e.get("reason"), "reviewer": e.get("reviewer"), "at": e.get("at")})
    return cases


def save_cases(cases: list[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                existing[(c["project"], c["fingerprint"])] = c
    for c in cases:
        existing[(c["project"], c["fingerprint"])] = c
    path.write_text("".join(json.dumps(c) + "\n" for c in existing.values()), encoding="utf-8")
    return len(existing)


def regress(path: Path) -> dict:
    from .pipeline import Inputs, run

    cases = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_project = defaultdict(list)
    for c in cases:
        by_project[c["project"]].append(c)
    rows = []
    for project, cs in by_project.items():
        current = {f.fingerprint() for f in run(Inputs.discover(project)).result.findings}
        for c in cs:
            present = c["fingerprint"] in current
            if c["expect"] == "present":
                status = "pass" if present else "REGRESSION (accepted finding no longer found)"
            else:
                status = "known false positive (still present)" if present else "fixed (no longer reported)"
            rows.append({**c, "status": status})
    summary = {"cases": len(rows),
               "regressions": sum(1 for r in rows if r["status"].startswith("REGRESSION")),
               "accepted_still_found": sum(1 for r in rows if r["status"] == "pass"),
               "known_false_positives": sum(1 for r in rows if r["status"].startswith("known")),
               "false_positives_fixed": sum(1 for r in rows if r["status"].startswith("fixed"))}
    return {"summary": summary, "cases": rows}
