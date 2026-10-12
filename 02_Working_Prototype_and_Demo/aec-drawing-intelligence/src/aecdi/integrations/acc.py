"""Autodesk Construction Cloud (ACC) Issues integration.

Endpoint: POST {base}/construction/issues/v1/projects/{projectId}/issues
  * 3-legged OAuth token with data:write scope (user context), JSON body.
  * projectId is the ACC project id without the Data Management "b." prefix.
  * Required body fields: title, issueSubtypeId, status (draft | open | ...).

Governance: only findings an engineer has accepted in the review screen are posted by default.
Confirmed rule findings can optionally be posted as *draft* issues for triage inside ACC; LLM-based
and probable findings are never posted unless accepted. Posted fingerprints are remembered, so a
re-run does not create duplicates.

Sheet location goes into the description (sheet, page, coordinates). Pushpins on 2D sheets
(linkedDocuments, type TwoDRasterPushpin) need the document URN and version from ACC Docs; that is
optional (include_pushpin) because the create-request shape must be confirmed against the live API.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from ..models import Finding

DEFAULT_BASE = "https://developer.api.autodesk.com"


def load_review_log(out_dir: Path) -> dict[str, dict]:
    """Latest decision per finding fingerprint (falls back to finding id for older logs)."""
    p = Path(out_dir) / "review_log.jsonl"
    latest: dict[str, dict] = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                if e.get("decision") in ("accept", "reject"):
                    latest[e.get("fingerprint") or e["finding_id"]] = e
    return latest


def _decision(f: Finding, log: dict[str, dict]) -> str | None:
    e = log.get(f.fingerprint()) or log.get(f.id)
    return e["decision"] if e else None


def select_for_acc(findings: list[Finding], log: dict[str, dict], policy: str = "accepted") -> list[tuple[Finding, str]]:
    """policy 'accepted': only engineer-accepted findings (status open).
    policy 'accepted+confirmed-draft': also rule-based confirmed findings not yet reviewed, as draft issues."""
    out = []
    for f in findings:
        d = _decision(f, log)
        if d == "accept":
            out.append((f, "open"))
        elif (d is None and policy == "accepted+confirmed-draft" and f.tier == "confirmed"
              and f.method.startswith("rule:")):
            out.append((f, "draft"))
    return out


def _location(f: Finding) -> str:
    lines = []
    for e in f.evidence:
        if e.xlsx_sheet:
            lines.append(f"- {e.doc} {e.xlsx_sheet}!{e.cell}: \"{e.snippet}\" ({e.role})")
        elif e.page is not None and e.bbox:
            x, y = round((e.bbox[0] + e.bbox[2]) / 2), round((e.bbox[1] + e.bbox[3]) / 2)
            lines.append(f"- {e.doc} sheet {e.sheet} (page {e.page + 1}) at x={x}, y={y} pt: \"{e.snippet}\" ({e.role})")
        else:
            lines.append(f"- {e.doc} {e.cell or ''} line {e.row}: \"{e.snippet}\" ({e.role})")
    return "\n".join(lines)


def build_payload(f: Finding, status: str, issue_subtype_id: str, documents: dict[str, dict] | None = None,
                  include_pushpin: bool = False) -> dict:
    body = {
        "title": f"[{f.id}] {f.type.replace('_', ' ')}: {', '.join(f.entities)}"[:100],
        "description": (f"{f.statement}\n\nEvidence:\n{_location(f)}\n\n"
                        f"Source: AEC Drawing Intelligence ({f.method}, tier {f.tier}, confidence {f.confidence:.2f}, "
                        f"fingerprint {f.fingerprint()}). Potential discrepancy for engineer review.")[:10000],
        "status": status,
        "issueSubtypeId": issue_subtype_id,
    }
    pin = next((e for e in f.evidence if e.page is not None and e.bbox and e.doc.lower().endswith(".pdf")), None)
    if include_pushpin and pin and documents and pin.doc in documents:
        doc = documents[pin.doc]
        body["linkedDocuments"] = [{
            "type": "TwoDRasterPushpin", "urn": doc["urn"], "createdAtVersion": doc.get("version", 1),
            "details": {"viewable": {"name": pin.sheet},
                        "position": {"x": round((pin.bbox[0] + pin.bbox[2]) / 2), "y": round((pin.bbox[1] + pin.bbox[3]) / 2), "z": 0}},
        }]
    return body


def payloads(findings: list[Finding], log: dict[str, dict], issue_subtype_id: str = "<ACC issue subtype id>",
             policy: str = "accepted", documents=None, include_pushpin=False) -> list[dict]:
    return [{"fingerprint": f.fingerprint(), "finding_id": f.id,
             "body": build_payload(f, status, issue_subtype_id, documents, include_pushpin)}
            for f, status in select_for_acc(findings, log, policy)]


def post_issues(items: list[dict], project_id: str, token: str, out_dir: Path, base_url: str = DEFAULT_BASE,
                dry_run: bool = True, timeout: float = 30.0) -> list[dict]:
    """POST each payload once. Returns per-item results; remembers posted fingerprints in acc_posted.json."""
    project_id = project_id[2:] if project_id.startswith("b.") else project_id
    state_path = Path(out_dir) / "acc_posted.json"
    posted = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    url = f"{base_url.rstrip('/')}/construction/issues/v1/projects/{project_id}/issues"
    results = []
    for it in items:
        if it["fingerprint"] in posted:
            results.append({"finding_id": it["finding_id"], "status": "skipped (already posted)",
                            "issue_id": posted[it["fingerprint"]]})
            continue
        if dry_run:
            results.append({"finding_id": it["finding_id"], "status": "dry-run", "url": url})
            continue
        req = urllib.request.Request(url, data=json.dumps(it["body"]).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read() or b"{}")
            posted[it["fingerprint"]] = data.get("id")
            results.append({"finding_id": it["finding_id"], "status": "created", "issue_id": data.get("id")})
        except urllib.error.HTTPError as e:
            results.append({"finding_id": it["finding_id"], "status": f"error {e.code}",
                            "detail": e.read().decode(errors="replace")[:300]})
    if not dry_run:
        state_path.write_text(json.dumps(posted, indent=2), encoding="utf-8")
    return results
