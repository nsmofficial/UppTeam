"""Missing information and tag consistency: undefined/orphan tags, duplicate tags, blank required
schedule fields, undefined hardware sets, missing spec sections, missing/unindexed sheets."""
from __future__ import annotations

from ..graph import ProjectGraph
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
    return out
