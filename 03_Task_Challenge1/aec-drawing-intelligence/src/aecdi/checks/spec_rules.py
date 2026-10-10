"""Spec-vs-schedule checks, deterministic version (no LLM).

These encode a few high-value requirement patterns (material implied by the governing section,
permitted fire ratings, required refrigerant). They are deliberately narrow: anything they cannot
parse is left to the LLM semantic checker (llm/semantic.py), whose output passes the same
evidence gate. Tier is *probable*: a spec can be superseded by an addendum the tool has not seen.
"""
from __future__ import annotations

import re

from ..graph import ProjectGraph
from . import mk

MATERIAL_BY_TITLE = [("WOOD", "WD"), ("HOLLOW METAL", "HM"), ("ALUMINUM", "ALUM"), ("STEEL", "STL")]
RATING_RE = re.compile(r"rated\s+((?:\d+\s*,\s*)*\d+(?:,)?\s*(?:and|or)\s*\d+|\d+)\s+minutes", re.I)
NOT_PERMITTED_RE = re.compile(r"[^.]*\bnot permitted\b[^.]*\.?", re.I)
REFRIG_REQ_RE = re.compile(r"Refrigerant:\s*(R-\d+[A-Z]?)", re.I)
REFRIG_ANY_RE = re.compile(r"\bR-\d{2,3}[A-Z]?\b")


def _minutes(s: str) -> int | None:
    m = re.search(r"(\d+)\s*(MIN|HR|HOUR)", s.upper())
    if not m:
        return None
    return int(m.group(1)) * (60 if m.group(2) != "MIN" else 1)


def check(g: ProjectGraph):
    out = []
    if not g.manual:
        return out
    for mark, rows in sorted(g.door_rows.items()):
        r = rows[0]
        sec_no = r.val("SPEC")
        sec = g.manual.sections.get(sec_no)
        if not sec:
            continue
        expected = next((code for kw, code in MATERIAL_BY_TITLE if kw in sec.title.upper()), None)
        mat = r.val("MATERIAL").upper()
        if expected and mat and mat != expected:
            para = next((p for p in sec.paragraphs if p.id.split()[-1].startswith("2.")), sec.paragraphs[0])
            quote = _phrase(para.text, sec.title.split()[-2:]) or para.text[:60]
            out.append(mk("spec_conflict", "high", "probable",
                          f"Potential discrepancy: door {mark} is governed by Section {sec_no} ({sec.title}) but its "
                          f"scheduled material is {mat}.",
                          [f"DOOR:{mark}"], [g.ev_cell(r, "MATERIAL", "schedule material"), g.ev_cell(r, "SPEC", "schedule spec ref"),
                                             g.ev_para(para, quote, "governing spec paragraph")],
                          "rule:SPEC-001", 0.85, "Material implied by the governing section title.", min_evidence=2))
        fire = r.val("FIRE")
        mins = _minutes(fire)
        if mins:
            for p in sec.paragraphs:
                m = RATING_RE.search(p.text)
                if not m:
                    continue
                allowed = {int(x) for x in re.findall(r"\d+", m.group(1))}
                if mins not in allowed:
                    np_ = NOT_PERMITTED_RE.search(p.text)
                    quote = np_.group(0).strip() if np_ else m.group(0)
                    out.append(mk("spec_conflict", "high", "probable",
                                  f"Potential discrepancy: door {mark} is scheduled {fire} but Section {sec_no} permits "
                                  f"{', '.join(str(a) for a in sorted(allowed))} minute ratings for this door type.",
                                  [f"DOOR:{mark}"], [g.ev_cell(r, "FIRE", "schedule fire rating"),
                                                     g.ev_para(p, m.group(0), "spec permitted ratings"),
                                                     g.ev_para(p, quote, "spec restriction") if np_ else None],
                                  "rule:SPEC-002", 0.85, min_evidence=2))
                break
    for tag, rows in sorted(g.equip_rows.items()):
        r = rows[0]
        sec = g.manual.sections.get(r.val("SPEC"))
        if not sec:
            continue
        req = next(((p, m.group(1)) for p in sec.paragraphs if (m := REFRIG_REQ_RE.search(p.text))), None)
        if not req:
            continue
        para, required = req
        found = REFRIG_ANY_RE.findall(r.val("REMARKS"))
        for ref in found:
            if ref != required:
                out.append(mk("spec_conflict", "high", "probable",
                              f"Potential discrepancy: {tag} remarks list refrigerant {ref}; Section {sec.number} requires {required}.",
                              [f"EQUIP:{tag}"], [g.ev_cell(r, "REMARKS", "schedule remarks"),
                                                 g.ev_para(para, f"Refrigerant: {required}", "spec requirement")],
                              "rule:SPEC-003", 0.85, min_evidence=2))
    return out


def _phrase(text: str, words: list[str]) -> str | None:
    """Shortest sentence fragment containing the section's key words, used as a verifiable quote."""
    for sent in re.split(r"(?<=[.;:])\s+", text):
        if all(w.lower().rstrip("s") in sent.lower() for w in words):
            return sent.strip().rstrip(".")
    return None
