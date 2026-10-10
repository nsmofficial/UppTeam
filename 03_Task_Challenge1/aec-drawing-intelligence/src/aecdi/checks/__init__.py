"""Deterministic checks. Each returns Findings with evidence anchors; wording is always
"potential discrepancy" - the engineer of record decides."""
from __future__ import annotations

from ..models import Evidence, Finding


def mk(type_, severity, tier, statement, entities, evidence, method, confidence, rationale="", min_evidence=1,
       sheets=None) -> Finding:
    ev = [e for e in evidence if e is not None]
    sh = sheets or sorted({e.sheet for e in ev if e.sheet and e.doc.lower().endswith(".pdf") and "-" in e.sheet}
                          | ({"BOQ"} if any(e.xlsx_sheet for e in ev) else set()))
    disc = sorted({s.split("-")[0] for s in sh if "-" in s})
    return Finding(type=type_, severity=severity, tier=tier, statement=statement, entities=sorted(set(entities)),
                   sheets=sh, disciplines=disc, evidence=ev, method=method, confidence=confidence,
                   rationale=rationale, min_evidence=min_evidence)


__all__ = ["mk", "Evidence", "Finding"]
