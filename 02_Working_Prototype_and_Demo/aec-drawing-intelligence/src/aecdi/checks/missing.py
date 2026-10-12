"""Missing information and tag consistency: undefined/orphan tags, duplicate tags, blank required
schedule fields, undefined hardware sets, missing spec sections, missing/unindexed sheets."""
from __future__ import annotations

import math
import re

from ..graph import ProjectGraph
from ..models import Evidence
from ..units import parse_feet_inches
from . import mk

DOOR_REQUIRED = ["TYPE", "WIDTH", "HEIGHT", "MATERIAL", "FRAME", "FIRE", "HDW", "SPEC"]


def check(g: ProjectGraph):
    out = []
    sched = ", ".join(g.door_schedule_sheets) or "door schedule"
    if g.door_rows:
        for mark, hits in sorted(g.door_tags.items()):
            if mark not in g.door_rows:
                out.append(mk("missing_info", "medium", "confirmed",
                              f"Potential discrepancy: door tag {mark} on {', '.join(sorted({h.sheet.number for h in hits}))} "
                              f"has no row in the door schedule ({sched}).",
                              [f"DOOR:{mark}"], [g.ev_span(h.sheet, h.span, "plan tag") for h in hits], "rule:MISS-001", 0.95,
                              "Every door tag on a plan should resolve to exactly one schedule row."))
        for mark, rows in sorted(g.door_rows.items()):
            if mark not in g.door_tags:
                out.append(mk("missing_info", "low", "probable",
                              f"Potential discrepancy: door {mark} is scheduled on {rows[0].sheet.number} but is not tagged on any plan in this set.",
                              [f"DOOR:{mark}"], [g.ev_cell(rows[0], "MARK", "schedule row")], "rule:MISS-002", 0.85,
                              "Probable rather than confirmed: the door may be on a plan sheet that is not part of this set."))
    for mark, hits in sorted(g.door_tags.items()):
        if len(hits) > 1:
            out.append(mk("tag_conflict", "medium", "confirmed",
                          f"Potential discrepancy: door number {mark} is tagged {len(hits)} times on the plans; door numbers must be unique.",
                          [f"DOOR:{mark}"], [g.ev_span(h.sheet, h.span, "plan tag") for h in hits], "rule:TAG-001", 0.95,
                          min_evidence=2))
    for mark, rows in sorted(g.door_rows.items()):
        r = rows[0]
        blanks = [c for c in DOOR_REQUIRED if r.get(c) is not None and r.val(c) == ""]
        if blanks:
            names = [r.table.headers[r.table.col(c)] for c in blanks]
            ev = [g.ev_cell(r, "MARK", "schedule row")] + [g.ev_cell(r, c, f"blank {n}") for c, n in zip(blanks, names)]
            out.append(mk("missing_info", "medium", "confirmed",
                          f"Potential discrepancy: door {mark} on {r.sheet.number} has no value for {', '.join(names)} "
                          f"(non-rated / not applicable is shown as '-', blank means missing).",
                          [f"DOOR:{mark}"], ev, "rule:MISS-003", 0.95))
        if len(rows) > 1:
            out.append(mk("tag_conflict", "medium", "confirmed",
                          f"Potential discrepancy: door {mark} has {len(rows)} rows in the door schedule.",
                          [f"DOOR:{mark}"], [g.ev_cell(x, "MARK", "schedule row") for x in rows], "rule:TAG-002", 0.95))
    # hardware sets
    if g.manual and "08 71 00" in g.manual.sections:
        defined = g.manual.hardware_sets()
        for mark, rows in sorted(g.door_rows.items()):
            hw = rows[0].val("HDW", "HARDWARE")
            if hw and hw not in ("-", "N/A") and hw not in defined:
                out.append(mk("missing_info", "medium", "confirmed",
                              f"Potential discrepancy: door {mark} calls for hardware set {hw}, which is not defined in "
                              f"Section 08 71 00 (defined: {', '.join(sorted(defined)) or 'none'}).",
                              [f"DOOR:{mark}", f"HW:{hw}"],
                              [g.ev_cell(rows[0], ("HDW", "HARDWARE"), "schedule hardware set"), g.ev_section_header("08 71 00")],
                              "rule:MISS-004", 0.95))
    # spec sections referenced but not in the project manual
    if g.manual:
        for sec, evs in sorted(g.spec_refs.items()):
            if sec not in g.manual.sections:
                evs = [e for e in evs if e is not None]
                out.append(mk("missing_info", "medium", "confirmed",
                              f"Potential discrepancy: Section {sec} is referenced {len(evs)} time(s) (schedules / BOQ / notes) "
                              f"but is not included in the project manual.",
                              [f"SPEC:{sec}"], evs[:4], "rule:MISS-005", 0.95))
    # sheets: referenced or indexed but not in the set; in the set but not indexed
    in_set = set(g.drawings.sheets)
    missing: dict[str, list] = {}
    for sheet, ref, span, bbox in g.sheet_refs:
        if ref not in in_set and span is not None:
            missing.setdefault(ref, []).append(g.ev_span(sheet, span, "sheet reference"))
    for num, row in g.index_rows.items():
        if num not in in_set:
            missing.setdefault(num, []).append(g.ev_cell(row, "SHEET", "sheet index"))
    for num, evs in sorted(missing.items()):
        out.append(mk("missing_info", "medium", "confirmed",
                      f"Potential discrepancy: sheet {num} is referenced/listed but is not included in the drawing set.",
                      [f"SHEET:{num}"], evs, "rule:MISS-006", 0.95))
    if g.index_rows:
        idx_sheet = next(iter(g.index_rows.values())).sheet
        for num, s in sorted(g.drawings.sheets.items()):
            if num not in g.index_rows and not num.startswith("PAGE-"):
                ev = [e for e in (g.ev_span(s, sp, "title block sheet number") for sp in s.tb_spans if sp.text == num)][:1]
                last = list(g.index_rows.values())[-1]
                ev += [g.ev_cell(last, "SHEET", "sheet index (last entry)")]
                out.append(mk("missing_info", "low", "confirmed",
                              f"Potential discrepancy: sheet {num} is in the set but missing from the sheet index on {idx_sheet.number}.",
                              [f"SHEET:{num}"], ev, "rule:MISS-007", 0.9, sheets=[idx_sheet.number, num]))
    # equipment tags
    if g.equip_rows:
        esched = ", ".join(g.equip_schedule_sheets)
        for tag, hits in sorted(g.equip_tags.items()):
            if tag not in g.equip_rows:
                out.append(mk("missing_info", "medium", "confirmed",
                              f"Potential discrepancy: equipment tag {tag} on {', '.join(sorted({h.sheet.number for h in hits}))} "
                              f"is not in the equipment schedule ({esched}).",
                              [f"EQUIP:{tag}"], [g.ev_span(h.sheet, h.span, "plan tag") for h in hits], "rule:MISS-009", 0.95))
        for tag, rows in sorted(g.equip_rows.items()):
            if tag not in g.equip_tags:
                out.append(mk("missing_info", "low", "probable",
                              f"Potential discrepancy: {tag} is scheduled on {rows[0].sheet.number} but not shown on any plan in this set.",
                              [f"EQUIP:{tag}"], [g.ev_cell(rows[0], "TAG", "schedule row")], "rule:MISS-010", 0.8,
                              "The equipment may be shown on a plan that is not part of this set."))
    out += untagged_doors(g)
    out += unreadable_sheets(g, out)
    return out


def _door_leaves(g: ProjectGraph, mark: str) -> int:
    """Pairs have two leaves: scheduled width >= 5'-0" (or 'PAIR' in the type description)."""
    rows = g.door_rows.get(mark)
    if not rows:
        return 1
    w = parse_feet_inches(rows[0].val("WIDTH") or "")
    return 2 if (w and w >= 5.0) or "PAIR" in rows[0].val("REMARKS").upper() else 1


def untagged_doors(g: ProjectGraph, radius: float = 50.0):
    """MISS-011: door swing symbols on architectural plans with no door tag nearby.

    Greedy nearest-first assignment of swing arcs to tags; a tag serves one leaf, or two for a pair.
    Probable only: the symbol may be a cased opening, an existing door, or a door tagged on another view."""
    out = []
    for sheet in g.drawings.sheets.values():
        if sheet.discipline not in g.style.door_disciplines or not sheet.arcs:
            continue
        tags = [(mark, h) for mark, hits in g.door_tags.items() for h in hits if h.sheet is sheet]
        cap = {i: _door_leaves(g, m) for i, (m, _) in enumerate(tags)}
        cand = []
        for ai, a in enumerate(sheet.arcs):
            ac = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
            for ti, (_, h) in enumerate(tags):
                tc = h.span.center
                d = math.dist(ac, tc)
                if d <= radius:
                    cand.append((d, ai, ti))
        assigned = set()
        for d, ai, ti in sorted(cand):
            if ai in assigned or cap[ti] <= 0:
                continue
            assigned.add(ai)
            cap[ti] -= 1
        for ai, a in enumerate(sheet.arcs):
            if ai in assigned:
                continue
            cx, cy = round((a[0] + a[2]) / 2), round((a[1] + a[3]) / 2)
            ev = Evidence(doc=g.drawings.doc, sheet=sheet.number, rev=sheet.rev, page=sheet.page, bbox=a, snippet="",
                          role="graphic: door swing without tag")
            out.append(mk("missing_info", "medium", "probable",
                          f"Potential discrepancy on {sheet.number}: a door swing at about ({cx}, {cy}) has no door tag, so the "
                          f"door cannot be matched to the door schedule.",
                          [f"SYMBOL:{sheet.number}:{cx},{cy}"], [ev], "rule:MISS-011", 0.75,
                          "Probable: the symbol may be a cased opening, an existing door, or a door tagged on another view."))
    return out


GATED = {"rule:MISS-001", "rule:MISS-002", "rule:MISS-009", "rule:MISS-010", "rule:MISS-005"}


def unreadable_sheets(g: ProjectGraph, findings):
    """ING-001: scanned pages without a text layer are not analysed. Completeness findings that could be
    explained by content on an unreadable page are downgraded from confirmed to probable."""
    raster = [s for s in g.drawings.sheets.values() if s.raster]
    if not raster:
        return []
    for f in findings:
        if f.method in GATED and f.tier == "confirmed":
            f.tier = "probable"
            f.confidence = min(f.confidence, 0.7)
            f.rationale = ((f.rationale + " | " if f.rationale else "")
                           + f"Downgraded: {len(raster)} page(s) could not be read and may contain the missing information.")
    out = []
    for s in raster:
        ev = Evidence(doc=g.drawings.doc, sheet=s.number, page=s.page, bbox=(0, 0, 200, 200), snippet="",
                      role="graphic: scanned page (no text layer)")
        out.append(mk("missing_info", "low", "needs_review",
                      f"Page {s.page + 1} of {g.drawings.doc} is a scanned image without a text layer. It was not analysed; "
                      f"run OCR or obtain the vector PDF.", [f"PAGE:{s.page + 1}"], [ev], "rule:ING-001", 0.5,
                      "Abstained: no machine-readable text on this page.", sheets=[s.number]))
    return out
