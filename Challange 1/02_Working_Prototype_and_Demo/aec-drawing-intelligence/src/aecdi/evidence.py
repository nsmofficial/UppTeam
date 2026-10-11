"""Evidence gate (anti-hallucination).

Every evidence anchor is re-checked against the source file, independently of whichever rule or
model produced it:
  * PDF anchors: the snippet must be found (whitespace/case-normalised) in the text inside the
    cited bbox on the cited page; an empty snippet asserts the region holds no text (blank cell).
  * Spreadsheet anchors: the cited cell must contain the snippet.
A finding that ends up with fewer verified anchors than its `min_evidence` is dropped and logged
in `rejected` with the reason. No finding ships without verified evidence.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf
from openpyxl import load_workbook

from .models import Finding
from .units import normalize_text


def _norm(s: str) -> str:
    return normalize_text(str(s)).lower().replace(" ", "")


class EvidenceGate:
    def __init__(self, files: dict[str, Path]):
        self.files = files
        self._pdf: dict[str, pymupdf.Document] = {}
        self._xlsx = {}

    def _page(self, doc: str, page: int):
        if doc not in self._pdf:
            self._pdf[doc] = pymupdf.open(self.files[doc])
        return self._pdf[doc][page]

    def verify_one(self, ev) -> tuple[bool, str]:
        if ev.doc not in self.files:
            return False, f"unknown document {ev.doc}"
        try:
            if ev.xlsx_sheet:
                if ev.doc not in self._xlsx:
                    self._xlsx[ev.doc] = load_workbook(self.files[ev.doc], data_only=False)
                ws = self._xlsx[ev.doc][ev.xlsx_sheet]
                val = ws[ev.cell].value if ev.cell else None
                cell = "" if val is None else (str(int(val)) if isinstance(val, float) and val.is_integer() else str(val))
                ok = _norm(ev.snippet) in _norm(cell) if ev.snippet else cell.strip() == ""
                return ok, "" if ok else f"cell {ev.cell} holds {cell!r}, not {ev.snippet!r}"
            if ev.page is None or ev.bbox is None:
                return False, "missing page/bbox"
            page = self._page(ev.doc, ev.page)
            clip = pymupdf.Rect(ev.bbox) + (-1.5, -1.5, 1.5, 1.5)
            text = page.get_text("text", clip=clip)
            if ev.snippet == "":
                if ev.role.startswith("changed graphics"):
                    drawn = any(pymupdf.Rect(d["rect"]).intersects(clip) for d in page.get_drawings())
                    return drawn, "" if drawn else "no graphics in cited region"
                ok = text.strip() == ""
                return ok, "" if ok else f"region expected blank but holds {text.strip()[:40]!r}"
            ok = _norm(ev.snippet) in _norm(text)
            return ok, "" if ok else f"snippet {ev.snippet[:40]!r} not found at cited location"
        except (KeyError, IndexError, ValueError) as e:
            return False, f"lookup failed: {e}"

    def apply(self, findings: list[Finding]) -> tuple[list[Finding], list[Finding], dict]:
        shipped, rejected = [], []
        n_ev = n_ok = 0
        for f in findings:
            reasons = []
            for ev in f.evidence:
                ok, why = self.verify_one(ev)
                ev.verified = ok
                n_ev += 1
                n_ok += ok
                if not ok:
                    reasons.append(why)
            verified = sum(1 for e in f.evidence if e.verified)
            if verified >= max(1, f.min_evidence):
                dropped = len(f.evidence) - verified
                f.evidence = [e for e in f.evidence if e.verified]     # shipped findings carry verified anchors only
                if dropped:
                    f.rationale = (f.rationale + " | " if f.rationale else "") + \
                        f"{dropped} anchor(s) failed verification and were removed: " + "; ".join(reasons)
                shipped.append(f)
            else:
                f.rationale = (f.rationale + " | " if f.rationale else "") + "REJECTED by evidence gate: " + "; ".join(reasons)
                rejected.append(f)
        return shipped, rejected, {"anchors_checked": n_ev, "anchors_verified": n_ok}
