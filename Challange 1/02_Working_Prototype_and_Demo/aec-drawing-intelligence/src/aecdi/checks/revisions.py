"""Revision comparison (Rev A -> Rev B).

Three diff layers, all on vector content (no OCR):
1. Tables (schedules) are diffed by row key (MARK / TAG ...), so an inserted row does not make
   every row below it look "changed".
2. Free text outside tables is matched by position; leftover identical strings that moved by a
   common offset are recognised as a layout shift (informational), not as edits.
3. Geometry: horizontal/vertical line coverage per line, plus rectangles and circles, with the
   same layout-shift compensation.

Each change is tested against the Rev B revision clouds (+ delta tags). Unclouded changes and
sheets whose content changed without a new revision in the title block become findings; clouded
changes go to the delta report.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import pymupdf

from ..graph import ProjectGraph
from ..ingest.drawings import DrawingSet, Sheet, Table, center, contains, overlap
from ..models import Evidence, RevisionChange
from . import mk

CLOUD_PAD = 3.0       # change centre must fall inside the cloud (delta labels are stripped at ingest)
DOOR_RE = re.compile(r"^\d{3}[A-Z]?$")


def _union(boxes):
    xs0, ys0, xs1, ys1 = zip(*boxes)
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def _words(page: pymupdf.Page, sheet: Sheet, exclude: list) -> list[tuple[str, tuple]]:
    out = []
    for w in page.get_text("words"):
        bb = tuple(round(v, 2) for v in w[:4])
        c = center(bb)
        if contains(sheet.tb, c) or any(contains(e, c, 1) for e in exclude):
            continue
        if any(contains(d[1], c, 1) and w[4] == d[0] for d in sheet.deltas):
            continue
        out.append((w[4], bb))
    return out


def _match_table(t: Table, others: list[Table]) -> Table | None:
    return next((o for o in others if o.headers == t.headers), None)


def _table_changes(ta: Table, tb: Table):
    key = 0
    ra = {r[key].text: r for r in ta.rows if r[key].text}
    rb = {r[key].text: r for r in tb.rows if r[key].text}
    out = []
    for k, row in rb.items():
        if k not in ra:
            out.append(("added", k, None, " | ".join(c.text for c in row), _union([c.bbox for c in row if c.bbox]), None))
    for k, row in ra.items():
        if k not in rb:
            out.append(("removed", k, " | ".join(c.text for c in row), None, _union([c.bbox for c in row if c.bbox]), None))
    for k in ra.keys() & rb.keys():
        for ci, (ca, cb) in enumerate(zip(ra[k], rb[k])):
            if ca.text != cb.text and cb.bbox:
                out.append(("changed", k, ca.text, cb.text, cb.bbox, tb.headers[ci] if ci < len(tb.headers) else ""))
    return out


def _intervals(lines):
    """Merge collinear segments: {(orientation, coord): [(a0, a1), ...]}"""
    acc = defaultdict(list)
    for o, segs in lines:
        for c, a0, a1 in segs:
            acc[(o, round(c))].append((a0, a1))
    merged = {}
    for k, segs in acc.items():
        segs.sort()
        m = [list(segs[0])]
        for a0, a1 in segs[1:]:
            if a0 <= m[-1][1] + 0.5:
                m[-1][1] = max(m[-1][1], a1)
            else:
                m.append([a0, a1])
        merged[k] = m
    return merged


def _subtract(a, b):
    """Parts of interval list a not covered by interval list b."""
    out = []
    for a0, a1 in a:
        cur = a0
        for b0, b1 in b:
            if b1 <= cur or b0 >= a1:
                continue
            if b0 > cur:
                out.append((cur, b0))
            cur = max(cur, b1)
        if cur < a1:
            out.append((cur, a1))
    return [(x0, x1) for x0, x1 in out if x1 - x0 > 1.0]


def _geom_changes(sa: Sheet, sb: Sheet, mask: list, shifts: list[tuple[float, float]]):
    def keep(bb):
        c = center(bb)
        return not contains(sb.tb, c) and not any(contains(m, c, 2) for m in mask)

    ia = _intervals([("h", sa.h_lines), ("v", sa.v_lines)])
    ib = _intervals([("h", sb.h_lines), ("v", sb.v_lines)])
    boxes = []
    for src, dst, sign in ((ib, ia, 1), (ia, ib, -1)):
        for (o, c), segs in src.items():
            other = dst.get((o, c), [])
            for x0, x1 in _subtract(segs, other):
                bb = (x0, c - 1, x1, c + 1) if o == "h" else (c - 1, x0, c + 1, x1)
                shifted = False
                for dx, dy in shifts:
                    oc = c - sign * (dy if o == "h" else dx)
                    off = sign * (dx if o == "h" else dy)
                    if _subtract([(x0 - off, x1 - off)], dst.get((o, round(oc)), [])) == []:
                        shifted = True
                if not shifted and keep(bb):
                    boxes.append(bb)
    for kind_a, kind_b in ((sa.boxes + sa.circles, sb.boxes + sb.circles),):
        sa_set = {tuple(round(v) for v in r) for r in kind_a}
        sb_set = {tuple(round(v) for v in r) for r in kind_b}
        for r in sb_set - sa_set:
            if not any((r[0] - dx, r[1] - dy, r[2] - dx, r[3] - dy) in sa_set for dx, dy in shifts) and keep(r):
                boxes.append(r)
        for r in sa_set - sb_set:
            if not any((r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy) in sb_set for dx, dy in shifts) and keep(r):
                boxes.append(r)
    # cluster nearby boxes
    clusters: list[list] = []
    for bb in boxes:
        for cl in clusters:
            u = _union(cl)
            if overlap((u[0] - 15, u[1] - 15, u[2] + 15, u[3] + 15), bb):
                cl.append(bb)
                break
        else:
            clusters.append([bb])
    return [_union(cl) for cl in clusters]


def _clouded(sheet: Sheet, bb) -> bool:
    c = center(bb)
    return any(contains(cl, c, CLOUD_PAD) for cl in sheet.clouds)


def _entities_for(sheet: Sheet, table: Table | None, key: str | None, text: str | None, bb) -> list[str]:
    if table is not None and key:
        h = table.headers[0]
        if h.startswith("MARK"):
            return [f"DOOR:{key}"]
        if h.startswith("TAG"):
            return [f"EQUIP:{key}"]
        return [f"ROW:{sheet.number}:{key}"]
    if text and DOOR_RE.match(text):
        return [f"DOOR:{text}"]
    c = center(bb)
    below = [s for s in sheet.spans if DOOR_RE.match(s.text) and 0 < s.center[1] - c[1] < 15 and abs(s.center[0] - c[0]) < 25
             and not any(contains(b, s.center) for b in sheet.boxes)]
    if below:
        return [f"ROOM:{below[0].text}"]
    return [f"SHEET:{sheet.number}"]


def compare(da: DrawingSet, db: DrawingSet, g: ProjectGraph, overlay_dir: Path | None = None):
    changes: list[RevisionChange] = []
    findings = []
    pa_doc, pb_doc = pymupdf.open(da.path), pymupdf.open(db.path)
    for num, sb in db.sheets.items():
        sa = da.sheets.get(num)
        if sa is None:
            continue
        sheet_changes = []   # (kind, before, after, bbox, entities)
        # 1. tables
        for tb_ in sb.tables:
            ta = _match_table(tb_, sa.tables)
            if ta is None:
                continue
            for kind, key, before, after, bb, col in _table_changes(ta, tb_):
                sheet_changes.append((kind, before, after, bb, _entities_for(sb, tb_, key, None, bb), col))
        # 2. free text
        mask = [t.bbox for t in sa.tables] + [t.bbox for t in sb.tables]
        wa = _words(pa_doc[sa.page], sa, mask)
        wb = _words(pb_doc[sb.page], sb, mask)
        pool = defaultdict(list)
        for w in wa:
            pool[w[0]].append(w)
        added = []
        for t, bb in wb:
            cands = pool.get(t, [])
            hit = next((w for w in cands if abs(w[1][0] - bb[0]) < 2 and abs(w[1][1] - bb[1]) < 2), None)
            if hit:
                cands.remove(hit)
            else:
                added.append((t, bb))
        removed = [w for ws in pool.values() for w in ws]
        # layout shifts: identical text displaced by a common offset
        disp = []
        for t, bb in added:
            for t2, bb2 in removed:
                if t2 == t:
                    disp.append((round(bb[0] - bb2[0]), round(bb[1] - bb2[1])))
        shifts = [d for d, n in Counter(disp).items() if n >= 3 and d != (0, 0)]
        moved = set()
        for t, bb in added:
            for t2, bb2 in removed:
                if t2 == t and (t2, bb2) not in moved and (round(bb[0] - bb2[0]), round(bb[1] - bb2[1])) in shifts:
                    moved.add((t, bb))
                    moved.add((t2, bb2))
                    break
        added = [w for w in added if w not in moved]
        removed = [w for w in removed if w not in moved]
        used = set()
        for t, bb in added:
            pair = next((w for w in removed if w not in used and overlap(
                (w[1][0] - 4, w[1][1] - 2, w[1][2] + 4, w[1][3] + 2), bb)), None)
            if pair:
                used.add(pair)
                sheet_changes.append(("changed", pair[0], t, bb, _entities_for(sb, None, None, t, bb), ""))
            else:
                sheet_changes.append(("added", None, t, bb, _entities_for(sb, None, None, t, bb), ""))
        for w in removed:
            if w not in used:
                sheet_changes.append(("removed", w[0], None, w[1], _entities_for(sb, None, None, w[0], w[1]), ""))
        # 3. geometry
        text_boxes = [c[3] for c in sheet_changes]
        for bb in _geom_changes(sa, sb, mask + [(b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3) for b in text_boxes], shifts):
            sheet_changes.append(("graphic", None, None, bb, _entities_for(sb, None, None, None, bb), ""))
        for kind, before, after, bb, ents, col in sheet_changes:
            changes.append(RevisionChange(sheet=num, kind=kind, before=before, after=after, bbox=tuple(bb),
                                          page_b=sb.page, clouded=_clouded(sb, bb)))
        # findings: unclouded changes
        for kind, before, after, bb, ents, col in sheet_changes:
            if _clouded(sb, bb):
                continue
            what = {"changed": f"'{before}' -> '{after}'" + (f" ({col})" if col else ""),
                    "added": f"added '{after}'", "removed": f"removed '{before}'",
                    "graphic": "graphics changed (no text change)"}[kind]
            if kind == "removed":
                ev = [Evidence(doc=da.doc, sheet=num, rev=sa.rev, page=sa.page, bbox=tuple(bb), snippet=before or "",
                               role="Rev A content")]
            elif kind == "graphic":
                ev = [Evidence(doc=db.doc, sheet=num, rev=sb.rev, page=sb.page, bbox=tuple(bb), snippet="",
                               role="changed graphics (region)", verified=None)]
            else:
                ev = [Evidence(doc=db.doc, sheet=num, rev=sb.rev, page=sb.page, bbox=tuple(bb), snippet=after or "",
                               role="Rev B content")]
                if before:
                    ev.append(Evidence(doc=da.doc, sheet=num, rev=sa.rev, page=sa.page, bbox=tuple(bb), snippet=before,
                                       role="Rev A content"))
            graphic = kind == "graphic"
            findings.append(mk("revision_issue", "medium" if graphic else "high", "probable" if graphic else "confirmed",
                               f"Potential discrepancy: {num} changed between Rev {sa.rev} and Rev {sb.rev} without a "
                               f"revision cloud: {what}.",
                               ents, ev, "rule:REV-001", 0.7 if graphic else 0.95,
                               "Unclouded changes are easy to miss in bid/addendum review; confirm the change is intended "
                               "and cloud it, or revert it.", sheets=[num]))
        # findings: content changed but no new revision in title block
        real = [c for c in sheet_changes]
        if real and sb.rev == sa.rev:
            rev_span = next((s for s in sb.tb_spans if s.text == sb.rev and len(s.text) <= 2), None)
            ev = []
            if rev_span:
                ev.append(g.ev_span(sb, rev_span, "latest revision in title block"))
            first = next((c for c in real if c[2]), None)
            if first:
                ev.append(Evidence(doc=db.doc, sheet=num, rev=sb.rev, page=sb.page, bbox=tuple(first[3]),
                                   snippet=first[2], role="changed content"))
            findings.append(mk("revision_issue", "medium", "confirmed",
                               f"Potential discrepancy: {num} content changed ({len(real)} change(s)) but its title block "
                               f"still shows Rev {sb.rev}; the revision was not issued on this sheet.",
                               [f"SHEET:{num}"], ev, "rule:REV-002", 0.9, sheets=[num]))
        if overlay_dir is not None and sheet_changes:
            _overlay(pa_doc[sa.page], pb_doc[sb.page], overlay_dir / f"{num}_RevA_vs_RevB.png")
    return changes, findings


def _overlay(pa: pymupdf.Page, pb: pymupdf.Page, out: Path, zoom: float = 1.5):
    """Red = only in Rev A (removed), blue = only in Rev B (added), grey = unchanged."""
    out.parent.mkdir(parents=True, exist_ok=True)
    m = pymupdf.Matrix(zoom, zoom)

    def gray(p):
        pix = p.get_pixmap(matrix=m, colorspace=pymupdf.csGRAY)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)

    a, b = gray(pa), gray(pb)
    img = np.full((*a.shape, 3), 255, np.uint8)
    ink_a, ink_b = a < 200, b < 200
    img[ink_a & ink_b] = (150, 150, 150)
    img[ink_a & ~ink_b] = (40, 40, 220)    # BGR red
    img[~ink_a & ink_b] = (220, 90, 0)     # BGR blue
    cv2.imwrite(str(out), img)
