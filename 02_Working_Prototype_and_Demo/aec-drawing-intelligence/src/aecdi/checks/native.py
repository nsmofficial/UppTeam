"""NATIVE-001: issued PDF schedule vs the Revit model export.

A difference means the sheet was issued from an older model state, or a value was overridden on
the sheet. Confirmed: both values are read directly from the two sources and cited.
"""
from __future__ import annotations

from ..graph import ProjectGraph
from ..ingest.native import DOOR_COLUMN_MAP, NativeSchedule
from ..models import Evidence
from ..units import normalize_text, parse_feet_inches
from . import mk


def _norm(v: str) -> str:
    v = normalize_text(v or "")
    ft = parse_feet_inches(v)
    return f"{ft:.4f}ft" if ft is not None else v.upper()


def _ev_native(native: NativeSchedule, line: int, col: str, value: str) -> Evidence:
    return Evidence(doc=native.doc, row=line, cell=col, snippet=value, role="model export (Revit)")


def check(g: ProjectGraph, native: NativeSchedule | None):
    if native is None or not g.door_rows:
        return []
    out = []
    model = {r["Mark"].strip(): (line, r) for line, r in native.rows if r.get("Mark", "").strip()}
    for mark, (line, r) in sorted(model.items()):
        rows = g.door_rows.get(mark)
        if not rows:
            out.append(mk("model_mismatch", "medium", "confirmed",
                          f"Potential discrepancy: door {mark} exists in the model export ({native.doc}) but not on the issued "
                          f"door schedule ({', '.join(g.door_schedule_sheets)}).",
                          [f"DOOR:{mark}"], [_ev_native(native, line, "Mark", mark)], "rule:NATIVE-001", 0.9,
                          "The issued sheet may predate this model change."))
            continue
        row = rows[0]
        diffs, ev = [], []
        for col, pdf_col in DOOR_COLUMN_MAP.items():
            if col not in r or col == "Mark":
                continue
            cell = row.get(pdf_col)
            if cell is None:
                continue
            if _norm(cell.text) != _norm(r[col]):
                diffs.append(f"{row.table.headers[row.table.col(pdf_col)]}: sheet '{cell.text or '(blank)'}' vs model '{r[col] or '(blank)'}'")
                ev.append(g.ev_cell(row, pdf_col, "issued schedule value"))
                ev.append(_ev_native(native, line, col, r[col]))
        if diffs:
            out.append(mk("model_mismatch", "medium", "confirmed",
                          f"Potential discrepancy: door {mark} on {row.sheet.number} differs from the model export: "
                          + "; ".join(diffs) + ".", [f"DOOR:{mark}"], ev, "rule:NATIVE-001", 0.95,
                          "Sheet issued from an older model state, or a value overridden on the sheet.", min_evidence=2))
    for mark, rows in sorted(g.door_rows.items()):
        if mark not in model:
            out.append(mk("model_mismatch", "medium", "confirmed",
                          f"Potential discrepancy: door {mark} is on the issued schedule ({rows[0].sheet.number}) but not in "
                          f"the model export ({native.doc}).", [f"DOOR:{mark}"],
                          [g.ev_cell(rows[0], "MARK", "issued schedule row")], "rule:NATIVE-001", 0.9))
    return out
