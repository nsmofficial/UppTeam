"""Dimension checks.

DIM-001  chained dimensions do not sum to the overall dimension (pure arithmetic -> confirmed)
DIM-002  dimension text differs from the drawn length at the stated scale (possible overridden
         dimension). Kept *probable*: sheets say "DO NOT SCALE DRAWINGS" and NTS details exist.
DIM-003  the same grid span is dimensioned differently on different sheets (A vs S, ...)
"""
from __future__ import annotations

from collections import defaultdict

from ..graph import ProjectGraph
from ..units import format_length
from . import mk

TOL_FT = 1 / 96          # 1/8 inch for arithmetic
SCALE_TOL_FT = 0.25      # 3 inches for scaled geometry


def _chains(dims):
    """Yield (overall, [chain dims]) where chain dims tile the overall extent on another dimension line."""
    rows = defaultdict(list)
    for d in dims:
        rows[(d.orient, round(d.pos))].append(d)
    for d in dims:
        for (orient, pos), row in rows.items():
            if orient != d.orient or abs(pos - d.pos) < 1:
                continue
            inside = sorted((c for c in row if c.a0 >= d.a0 - 1 and c.a1 <= d.a1 + 1), key=lambda c: c.a0)
            if len(inside) < 2:
                continue
            ok = abs(inside[0].a0 - d.a0) < 1.5 and abs(inside[-1].a1 - d.a1) < 1.5 and all(
                abs(a.a1 - b.a0) < 1.5 for a, b in zip(inside, inside[1:]))
            if ok:
                yield d, inside


def check(g: ProjectGraph):
    out = []
    by_span = defaultdict(list)
    for sheet in g.drawings.sheets.values():
        for overall, chain in _chains(sheet.dims):
            total = sum(c.value for c in chain)
            if abs(total - overall.value) > TOL_FT:
                ent = [f"GRID:{overall.span}"] if overall.span else [f"DIM:{sheet.number}:{overall.text}"]
                out.append(mk("dimension_conflict", "high", "confirmed",
                              f"Potential discrepancy on {sheet.number}: chained dimensions "
                              f"{' + '.join(c.text for c in chain)} = {format_length(total, sheet.metric)}, but the overall dimension "
                              f"{('(grid ' + overall.span + ') ') if overall.span else ''}reads {overall.text}.",
                              ent, [g.ev_span(sheet, _span(sheet, overall), "overall dimension")]
                              + [g.ev_span(sheet, _span(sheet, c), "chain dimension") for c in chain],
                              "rule:DIM-001", 0.97, min_evidence=2))
        if sheet.scale_ptft:
            for d in sheet.dims:
                measured = (d.a1 - d.a0) / sheet.scale_ptft
                if abs(measured - d.value) > SCALE_TOL_FT:
                    ent = [f"GRID:{d.span}"] if d.span else [f"DIM:{sheet.number}:{d.text}"]
                    out.append(mk("dimension_conflict", "medium", "probable",
                                  f"Potential discrepancy on {sheet.number}: dimension text {d.text}"
                                  f"{' (grid ' + d.span + ')' if d.span else ''} but the drawn length measures about "
                                  f"{format_length(measured, sheet.metric)} at {sheet.scale}. Possible overridden dimension.",
                                  ent, [g.ev_span(sheet, _span(sheet, d), "dimension text")], "rule:DIM-002", 0.75,
                                  "Probable only: drawings say DO NOT SCALE and some views are not to scale; the text "
                                  "may be right and the graphics wrong, or vice versa."))
        for d in sheet.dims:
            if d.span:
                by_span[(d.orient, d.span)].append((sheet, d))
    for (orient, span), items in sorted(by_span.items()):
        values = {round(d.value * 96) for _, d in items}
        sheets = {s.number for s, _ in items}
        if len(values) > 1 and len(sheets) > 1:
            desc = "; ".join(f"{s.number} = {d.text}" for s, d in sorted(items, key=lambda x: x[0].number))
            out.append(mk("dimension_conflict", "high", "confirmed",
                          f"Potential discrepancy: grid {span} is dimensioned differently across sheets: {desc}.",
                          [f"GRID:{span}"], [g.ev_span(s, _span(s, d), "grid dimension") for s, d in items],
                          "rule:DIM-003", 0.95, min_evidence=2))
    return out


def _span(sheet, dim):
    return next(s for s in sheet.spans if s.bbox == dim.bbox)
