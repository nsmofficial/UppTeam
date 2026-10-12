"""Quantity reconciliation: plan tag counts vs schedule vs BOQ.

Real-world rules encoded here:
* a tag marked "TYP. OF n" represents n elements; "TYP." without a count is unknowable from
  the sheet -> needs_review, never a confirmed mismatch;
* NIC (not in contract) items must not be priced in the BOQ and are excluded from reconciliation.
"""
from __future__ import annotations

from collections import defaultdict

from ..graph import ProjectGraph, _fmt_qty
from . import mk


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def check(g: ProjectGraph):
    out = []
    if g.boq:
        # ---- doors: schedule count by type vs BOQ --------------------------------------------
        by_type: dict[str, list] = defaultdict(list)
        for mark, rows in g.door_rows.items():
            t = rows[0].val("TYPE")
            if t:
                by_type[t].append(rows[0])
        boq_by_type = defaultdict(list)
        for it in g.boq.items:
            if it.door_type:
                boq_by_type[it.door_type].append(it)
        for t in sorted(set(by_type) | set(boq_by_type)):
            rows = sorted(by_type.get(t, []), key=lambda r: r.val("MARK"))
            items = boq_by_type.get(t, [])
            n_sched = len(rows)
            n_boq = sum(i.qty or 0 for i in items)
            if items and n_sched == n_boq:
                continue
            marks = ", ".join(r.val("MARK") for r in rows)
            ev = [g.ev_boq(i, "qty", "BOQ quantity") for i in items]
            ev += [g.ev_cell(r, "TYPE", "schedule row") for r in (rows[:1] + rows[-1:] if len(rows) > 1 else rows)]
            if not items:
                stmt = f"Potential discrepancy: door type {t} has {n_sched} scheduled door(s) ({marks}) but no BOQ line."
            else:
                stmt = (f"Potential discrepancy: door type {t}: {n_sched} door(s) in the schedule ({marks}); "
                        f"BOQ {', '.join(i.item for i in items)} = {_fmt_qty(n_boq)} {items[0].unit}.")
            out.append(mk("quantity_mismatch", "high", "confirmed", stmt,
                          [f"DOORTYPE:{t}"] + [f"BOQ:{i.item}" for i in items], ev, "rule:QTY-001", 0.95,
                          "Counts schedule rows per door type; plan-vs-schedule differences are reported separately "
                          "as undefined/orphan tags.", min_evidence=1))
    # ---- equipment: plan vs schedule vs BOQ --------------------------------------------------
    boq_by_tag = defaultdict(list)
    if g.boq:
        for it in g.boq.items:
            if it.equipment_tag:
                boq_by_tag[it.equipment_tag].append(it)
    for tag in sorted(set(g.equip_rows) | set(boq_by_tag)):
        rows = g.equip_rows.get(tag, [])
        row = rows[0] if rows else None
        hits = g.equip_tags.get(tag, [])
        items = boq_by_tag.get(tag, [])
        nic = (row is not None and "NIC" in row.val("REMARKS").upper()) or any("NIC" in h.qualifier for h in hits)
        sched_qty = _num(row.val("QTY")) if row else None
        boq_qty = sum(i.qty or 0 for i in items) if items else None
        if nic:
            if items and boq_qty:
                ev = [g.ev_boq(i, "qty", "BOQ quantity") for i in items]
                ev += [g.ev_cell(row, "REMARKS", "schedule remarks")] if row else []
                ev += [g.ev_span(h.sheet, h.qual_span, "plan NIC note") for h in hits if h.qual_span]
                out.append(mk("quantity_mismatch", "medium", "confirmed",
                              f"Potential discrepancy: {tag} is marked NIC (not in contract) but BOQ "
                              f"{', '.join(i.item for i in items)} prices {_fmt_qty(boq_qty)} {items[0].unit}.",
                              [f"EQUIP:{tag}"] + [f"BOQ:{i.item}" for i in items], ev, "rule:QTY-003", 0.95))
            continue
        if row is None:
            continue   # BOQ line for an unscheduled tag: reported by MISS-009 when the tag is on a plan
        if g.boq and sched_qty is not None and (boq_qty is None or boq_qty != sched_qty):
            ev = [g.ev_cell(row, "QTY", "schedule quantity")] + [g.ev_boq(i, "qty", "BOQ quantity") for i in items]
            stmt = (f"Potential discrepancy: {tag}: schedule {row.sheet.number} QTY = {_fmt_qty(sched_qty)}, "
                    + (f"BOQ {', '.join(i.item for i in items)} = {_fmt_qty(boq_qty)} {items[0].unit}." if items else "no BOQ line."))
            out.append(mk("quantity_mismatch", "high" if items else "medium", "confirmed", stmt,
                          [f"EQUIP:{tag}"] + [f"BOQ:{i.item}" for i in items], ev, "rule:QTY-002", 0.95))
        if hits and sched_qty is not None:
            counts = [h.count for h in hits]
            if any(c is None for c in counts):
                out.append(mk("quantity_mismatch", "low", "needs_review",
                              f"Plan quantity for {tag} cannot be determined from the sheet: tag is marked "
                              f"'{next(h.qualifier for h in hits if h.count is None)}' without a count. Schedule QTY = "
                              f"{_fmt_qty(sched_qty)}" + (f", BOQ = {_fmt_qty(boq_qty)}" if boq_qty is not None else "")
                              + ". Reviewer to confirm the count.",
                              [f"EQUIP:{tag}"], [g.ev_span(h.sheet, h.span, "plan tag") for h in hits]
                              + [g.ev_span(h.sheet, h.qual_span, "TYP. note") for h in hits if h.qual_span]
                              + [g.ev_cell(row, "QTY", "schedule quantity")], "rule:QTY-004", 0.5,
                              "Abstained: 'TYP.' means the element repeats, but the sheet does not say how many times."))
            elif sum(counts) != sched_qty:
                out.append(mk("quantity_mismatch", "high", "confirmed",
                              f"Potential discrepancy: {tag}: {sum(counts)} on plan "
                              f"({', '.join(h.sheet.number + (' ' + h.qualifier if h.qualifier else '') for h in hits)}) vs "
                              f"schedule QTY {_fmt_qty(sched_qty)}.",
                              [f"EQUIP:{tag}"], [g.ev_span(h.sheet, h.span, "plan tag") for h in hits]
                              + [g.ev_cell(row, "QTY", "schedule quantity")], "rule:QTY-005", 0.9))
    return out
