"""Cross-discipline coordination: mechanical schedule vs electrical panel schedule vs structure."""
from __future__ import annotations

import re

from ..graph import ProjectGraph
from . import mk

NOMINAL = {115: 120, 120: 120, 200: 208, 208: 208, 230: 240, 240: 240, 265: 277, 277: 277, 460: 480, 480: 480,
           575: 600, 600: 600}


def _vph(s: str):
    m = re.match(r"^\s*(\d{3})\s*/\s*(\d)\s*$", s or "")
    if not m:
        return None
    v = int(m.group(1))
    return NOMINAL.get(v, v), int(m.group(2))


def _int(s: str):
    m = re.search(r"\d[\d,]*", s or "")
    return int(m.group(0).replace(",", "")) if m else None


def check(g: ProjectGraph):
    out = []
    has_panels = bool(g.panel_rows)
    for tag, rows in sorted(g.equip_rows.items()):
        row = rows[0]
        need = _vph(row.val("V/PH"))
        circuits = g.panel_rows.get(tag, [])
        if has_panels and need and not circuits:
            out.append(mk("cross_discipline_conflict", "high", "confirmed",
                          f"Potential discrepancy: {tag} requires {row.val('V/PH')} power ({row.sheet.number}) but no "
                          f"branch circuit serves it on the panel schedules.",
                          [f"EQUIP:{tag}"], [g.ev_cell(row, "TAG", "equipment row"), g.ev_cell(row, "V/PH", "required power")],
                          "rule:XD-002", 0.9, "Checked against every panel schedule in the set."))
        for c in circuits:
            have = _vph(c.val("V/PH"))
            if need and have and need != have:
                out.append(mk("cross_discipline_conflict", "high", "confirmed",
                              f"Potential discrepancy: {tag} is scheduled {row.val('V/PH')} on {row.sheet.number} but is fed "
                              f"{c.val('V/PH')} from panel {c.val('PANEL')} ckt {c.val('CKT')} on {c.sheet.number}.",
                              [f"EQUIP:{tag}"], [g.ev_cell(row, "V/PH", "mechanical V/PH"), g.ev_cell(c, "V/PH", "electrical V/PH"),
                                                 g.ev_cell(c, "LOAD", "panel load")], "rule:XD-001", 0.95, min_evidence=2))
            mca, bkr = _int(row.val("MCA")), _int(c.val("BKR"))
            if mca and bkr and bkr < mca:
                out.append(mk("cross_discipline_conflict", "high", "confirmed",
                              f"Potential discrepancy: {tag} MCA {mca} A ({row.sheet.number}) exceeds the {bkr} A breaker on "
                              f"panel {c.val('PANEL')} ckt {c.val('CKT')} ({c.sheet.number}).",
                              [f"EQUIP:{tag}"], [g.ev_cell(row, "MCA", "MCA"), g.ev_cell(c, "BKR", "breaker"),
                                                 g.ev_cell(c, "LOAD", "panel load")], "rule:XD-003", 0.95, min_evidence=2))
        lim = g.struct_limits.get(tag)
        wt = _int(row.val("WEIGHT"))
        if lim and wt and wt > lim[2]:
            sheet, span, limit = lim
            out.append(mk("cross_discipline_conflict", "high", "confirmed",
                          f"Potential discrepancy: {tag} operating weight {wt:,} LB ({row.sheet.number}) exceeds the "
                          f"{limit:,} LB design weight on {sheet.number}.",
                          [f"EQUIP:{tag}"], [g.ev_cell(row, "WEIGHT", "equipment weight"), g.ev_span(sheet, span, "structural design weight")],
                          "rule:XD-004", 0.95, min_evidence=2))
    return out
