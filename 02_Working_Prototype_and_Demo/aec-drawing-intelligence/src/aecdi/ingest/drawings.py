"""Drawing-set ingestion from vector PDFs (Revit/AutoCAD exports).

Per page: title block (sheet number, title, scale, revision history), text spans with
coordinates and direction, ruled tables (schedules) with cell boxes, and the geometry needed
by the checks: horizontal/vertical line segments, small closed rectangles (tag boxes),
circles (grid bubbles, callouts) and revision clouds.

Tag styles are configurable (`TagStyle`) because every office's CAD standard differs; in a
pilot this is the first thing tuned to the client's title blocks and tag families.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from ..units import is_metric_scale, normalize_text, parse_feet_inches, parse_length, parse_scale

SHEET_NO_RE = re.compile(r"^[A-Z]{1,2}-\d{3}$")
SHEET_REF_RE = re.compile(r"(?<![A-Z0-9-])([A-Z]{1,2}-\d{3})(?![A-Z0-9])")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{1,2}/\d{1,2}/\d{2,4}$")


@dataclass
class TagStyle:
    door_mark: re.Pattern = re.compile(r"^\d{3}[A-Z]?$")
    equipment: re.Pattern = re.compile(r"^(RTU|AHU|EF|SF|VAV|FCU|CUH|EUH|UH|CU|HP|ERV|DOAS)-\d+[A-Z]?$")
    tag_box_max: tuple[float, float] = (60.0, 20.0)       # max w, h of a tag enclosure (pt)
    door_disciplines: tuple[str, ...] = ("A", "I")         # door tags live on architectural / interiors plans
    equipment_disciplines: tuple[str, ...] = ("M", "P", "E", "FP")


Rect = tuple[float, float, float, float]


def _r(rect) -> Rect:
    return (round(rect[0], 2), round(rect[1], 2), round(rect[2], 2), round(rect[3], 2))


def center(b: Rect) -> tuple[float, float]:
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def contains(outer: Rect, pt: tuple[float, float], pad: float = 0.0) -> bool:
    return outer[0] - pad <= pt[0] <= outer[2] + pad and outer[1] - pad <= pt[1] <= outer[3] + pad


def overlap(a: Rect, b: Rect) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@dataclass
class Span:
    text: str
    bbox: Rect
    size: float
    dir: tuple[float, float]

    @property
    def center(self):
        return center(self.bbox)

    @property
    def vertical(self) -> bool:
        return abs(self.dir[1]) > 0.9


@dataclass
class Cell:
    text: str
    bbox: Rect | None


@dataclass
class Table:
    headers: list[str]
    rows: list[list[Cell]]
    bbox: Rect

    def col(self, *names: str) -> int | None:
        for name in names:
            for i, h in enumerate(self.headers):
                if h.upper().startswith(name.upper()):
                    return i
        return None

    def has(self, *names: str) -> bool:
        return all(self.col(n) is not None for n in names)


@dataclass
class Dim:
    text: str
    value: float          # feet
    bbox: Rect            # text bbox
    orient: str           # "h" or "v"
    a0: float             # extent along the measured axis (pt)
    a1: float
    pos: float            # coordinate of the dimension line
    span: str | None = None   # grid span label, e.g. "1-2" / "A-B"


@dataclass
class Grid:
    label: str
    orient: str           # "v" -> vertical line at x=coord ; "h" -> horizontal line at y=coord
    coord: float
    bubble: Rect


@dataclass
class Sheet:
    number: str
    title: str
    page: int
    doc: str
    revisions: list[tuple[str, str, str]]
    scale: str | None
    scale_ptft: float | None
    tb: Rect
    tb_spans: list[Span]
    spans: list[Span]                 # outside title block
    tables: list[Table]
    h_lines: list[tuple[float, float, float]]   # (y, x0, x1)
    v_lines: list[tuple[float, float, float]]   # (x, y0, y1)
    boxes: list[Rect]                 # small closed rectangles (tag enclosures)
    circles: list[Rect]
    clouds: list[Rect]
    deltas: list[tuple[str, Rect]] = field(default_factory=list)
    arcs: list[Rect] = field(default_factory=list)      # door swing symbols
    raster: bool = False                                # scanned sheet without a usable text layer
    grids: list[Grid] = field(default_factory=list)
    dims: list[Dim] = field(default_factory=list)
    callouts: list[tuple[str, str, Rect, Rect]] = field(default_factory=list)  # (detail, sheet, circle, ref span bbox)

    @property
    def rev(self) -> str | None:
        return self.revisions[-1][0] if self.revisions else None

    @property
    def metric(self) -> bool:
        return is_metric_scale(self.scale)

    @property
    def discipline(self) -> str:
        return self.number.split("-")[0]

    def spans_outside_tables(self) -> list[Span]:
        return [s for s in self.spans if not any(contains(t.bbox, s.center, 1) for t in self.tables)]


@dataclass
class DrawingSet:
    path: Path
    sheets: dict[str, Sheet]

    @property
    def doc(self) -> str:
        return self.path.name


# ----------------------------------------------------------------------------------------------
def _spans(page: pymupdf.Page) -> list[Span]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = normalize_text(s["text"])
                if t:
                    out.append(Span(t, _r(s["bbox"]), round(s["size"], 1), tuple(round(v, 2) for v in line["dir"])))
    return out


def _geometry(page: pymupdf.Page):
    h, v, rects, circles, clouds, triangles, arcs = [], [], [], [], [], [], []
    for path in page.get_drawings():
        items = path["items"]
        n_curves = sum(1 for it in items if it[0] == "c")
        pr = path["rect"]
        if n_curves >= 8 and pr.width > 12 and pr.height > 8:
            clouds.append(_r(pr))
            continue
        if len(items) == 3 and all(it[0] == "l" for it in items) and 6 < pr.width < 24 and 5 < pr.height < 22:
            triangles.append(_r(pr))      # revision delta symbol
            continue
        if n_curves == 4 and abs(pr.width - pr.height) < 2 and 10 < pr.width < 40:
            circles.append(_r(pr))
        if n_curves == 1 and len(items) <= 3 and 12 < max(pr.width, pr.height) < 80:
            arcs.append(_r(pr))           # single quarter-arc: door swing symbol
        for it in items:
            if it[0] == "l":
                p1, p2 = it[1], it[2]
                if abs(p1.y - p2.y) < 0.5 and abs(p1.x - p2.x) > 1:
                    h.append((round(p1.y, 2), round(min(p1.x, p2.x), 2), round(max(p1.x, p2.x), 2)))
                elif abs(p1.x - p2.x) < 0.5 and abs(p1.y - p2.y) > 1:
                    v.append((round(p1.x, 2), round(min(p1.y, p2.y), 2), round(max(p1.y, p2.y), 2)))
            elif it[0] in ("re", "qu"):
                r = it[1] if it[0] == "re" else it[1].rect
                rects.append(_r(r))
    return h, v, rects, circles, clouds, triangles, arcs


def _title_block(page: pymupdf.Page, rects: list[Rect]) -> Rect:
    W, H = page.rect.width, page.rect.height
    cands = [r for r in rects if r[0] > 0.7 * W and (r[3] - r[1]) > 0.5 * H]
    if cands:
        return max(cands, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    return (0.85 * W, 0.0, W, H)


def _parse_title_block(tb_spans: list[Span]):
    number = None
    cands = [s for s in tb_spans if SHEET_NO_RE.match(s.text)]
    if cands:
        number = max(cands, key=lambda s: s.size).text
    by_y = sorted(tb_spans, key=lambda s: (s.bbox[1], s.bbox[0]))

    def label_y(label):
        for s in by_y:
            if s.text.upper().startswith(label):
                return s.bbox[3]
        return None

    t_y, s_y = label_y("SHEET TITLE"), label_y("SCALE")
    title = ""
    if t_y is not None:
        lim = s_y - 10 if s_y and s_y > t_y else t_y + 40
        title = " ".join(s.text for s in by_y if t_y < s.center[1] < lim)
    scale = None
    if s_y is not None:
        nxt = [s for s in by_y if s_y < s.center[1] < s_y + 18]
        scale = nxt[0].text if nxt else None
    revisions = []
    hdr = next((s for s in by_y if s.text.upper() == "REV"), None)
    if hdr:
        rows = [s for s in by_y if s.bbox[1] > hdr.bbox[3] - 1 and abs(s.bbox[0] - hdr.bbox[0]) < 8
                and re.fullmatch(r"[A-Z0-9]{1,2}", s.text)]
        for r in rows:
            same = [s for s in by_y if abs(s.center[1] - r.center[1]) < 2.5 and s is not r]
            date = next((s.text for s in same if DATE_RE.match(s.text)), "")
            desc = " ".join(s.text for s in same if not DATE_RE.match(s.text))
            revisions.append((r.text, date, desc))
    return number, title, scale, revisions


def _strip_deltas(page: pymupdf.Page, cell: Rect, text: str, triangles: list[Rect]) -> str:
    for t in triangles:
        if overlap(cell, t):
            for w in page.get_text("words", clip=pymupdf.Rect(t)):
                if contains(t, center(w[:4]), 1) and len(w[4]) <= 2:
                    toks = text.split()
                    if w[4] in toks:
                        toks.remove(w[4])
                        text = " ".join(toks)
    return text


def _tables(page: pymupdf.Page, tb: Rect, triangles: list[Rect] = ()) -> list[Table]:
    out = []
    try:
        found = page.find_tables()
    except Exception:  # pragma: no cover - table finder is best effort
        return out
    for t in found.tables:
        bbox = _r(t.bbox)
        if contains(tb, center(bbox)):
            continue
        data = t.extract()
        if not data:
            continue
        rows = []
        for ri, row in enumerate(t.rows):
            cells = [Cell(_strip_deltas(page, _r(c), normalize_text(data[ri][ci] or ""), triangles) if c else
                          normalize_text(data[ri][ci] or ""), _r(c) if c else None) for ci, c in enumerate(row.cells)]
            rows.append(cells)
        table = Table([c.text.upper() for c in rows[0]], rows[1:], bbox)
        if _looks_like_schedule(table):
            out.append(table)
    return out


def _looks_like_schedule(t: Table) -> bool:
    """Reject line-grid artefacts (dimension strings, tag boxes) that the table finder picks up on plans."""
    if len(t.headers) < 2 or not t.rows:
        return False
    if any(not h or not re.search(r"[A-Z]{2}", h) or parse_feet_inches(h) is not None for h in t.headers):
        return False
    filled = sum(1 for r in t.rows for c in r if c.text)
    return filled >= 0.4 * len(t.rows) * len(t.headers)


def _grids_and_callouts(sheet: Sheet):
    long_v = [l for l in sheet.v_lines if l[2] - l[1] > 150]
    long_h = [l for l in sheet.h_lines if l[2] - l[1] > 150]
    for c in sheet.circles:
        inside = [s for s in sheet.spans if contains(c, s.center)]
        cx, cy = center(c)
        if len(inside) == 1 and re.fullmatch(r"[A-Z]{1,2}|\d{1,2}(\.\d)?", inside[0].text):
            if any(abs(x - cx) < 1.5 for x, _, _ in long_v):
                sheet.grids.append(Grid(inside[0].text, "v", cx, c))
            elif any(abs(y - cy) < 1.5 for y, _, _ in long_h):
                sheet.grids.append(Grid(inside[0].text, "h", cy, c))
        elif len(inside) == 2:
            top, bot = sorted(inside, key=lambda s: s.center[1])
            if SHEET_NO_RE.match(bot.text):
                sheet.callouts.append((top.text, bot.text, c, bot.bbox))


def _dims(sheet: Sheet):
    metric = sheet.metric
    for s in sheet.spans:
        val = parse_length(s.text, metric)
        if val is None or contains(sheet.tb, s.center):
            continue
        if metric and any(contains(b, s.center) for b in sheet.boxes):
            continue        # a number inside a tag box is a tag, not a dimension
        x0, y0, x1, y1 = s.bbox
        cx, cy = s.center
        if not s.vertical:
            cands = [l for l in sheet.h_lines if y1 - 2 <= l[0] <= y1 + 6 and l[1] - 1 <= cx <= l[2] + 1 and l[2] - l[1] > 15]
            if cands:
                y, a0, a1 = min(cands, key=lambda l: (abs(l[0] - y1), l[2] - l[1]))
                sheet.dims.append(Dim(s.text, val, s.bbox, "h", a0, a1, y))
        else:
            cands = [l for l in sheet.v_lines if x1 - 2 <= l[0] <= x1 + 6 and l[1] - 1 <= cy <= l[2] + 1 and l[2] - l[1] > 15]
            if cands:
                x, a0, a1 = min(cands, key=lambda l: (abs(l[0] - x1), l[2] - l[1]))
                sheet.dims.append(Dim(s.text, val, s.bbox, "v", a0, a1, x))
    vg = sorted((g for g in sheet.grids if g.orient == "v"), key=lambda g: g.coord)
    hg = sorted((g for g in sheet.grids if g.orient == "h"), key=lambda g: g.coord)
    for d in sheet.dims:
        gl = vg if d.orient == "h" else hg
        g0 = next((g for g in gl if abs(g.coord - d.a0) < 2), None)
        g1 = next((g for g in gl if abs(g.coord - d.a1) < 2), None)
        if g0 and g1:
            d.span = f"{g0.label}-{g1.label}"


def load_drawing_set(path: str | Path) -> DrawingSet:
    path = Path(path)
    doc = pymupdf.open(path)
    sheets: dict[str, Sheet] = {}
    for i, page in enumerate(doc):
        spans = _spans(page)
        h, v, rects, circles, clouds, triangles, arcs = _geometry(page)
        # scanned / raster sheet: an image covers most of the page and there is (almost) no text layer
        page_area = page.rect.width * page.rect.height
        img_area = sum(max(0.0, (i["bbox"][2] - i["bbox"][0]) * (i["bbox"][3] - i["bbox"][1])) for i in page.get_image_info())
        raster = len(spans) < 5 and img_area > 0.5 * page_area
        # revision deltas: a short label inside a small triangle. Remove them from the text layer so a
        # delta overlapping a schedule header or note does not corrupt it ("B V/PH").
        deltas = [(s.text, t) for t in triangles for s in spans if contains(t, s.center, 1) and len(s.text) <= 2]
        delta_spans = {id(s) for t in triangles for s in spans if contains(t, s.center, 1) and len(s.text) <= 2}
        spans = [s for s in spans if id(s) not in delta_spans]
        tb = _title_block(page, rects)
        tb_spans = [s for s in spans if contains(tb, s.center)]
        number, title, scale, revisions = _parse_title_block(tb_spans)
        number = number or f"PAGE-{i + 1}"
        boxes = [r for r in rects if (r[2] - r[0]) <= 60 and (r[3] - r[1]) <= 20 and not contains(tb, center(r))]
        sheet = Sheet(number=number, title=title, page=i, doc=path.name, revisions=revisions, scale=scale,
                      scale_ptft=parse_scale(scale) if scale else None, tb=tb, tb_spans=tb_spans,
                      spans=[s for s in spans if not contains(tb, s.center)], tables=_tables(page, tb, triangles),
                      h_lines=h, v_lines=v, boxes=boxes, circles=circles, clouds=clouds, deltas=deltas,
                      arcs=arcs, raster=raster)
        _grids_and_callouts(sheet)
        _dims(sheet)
        sheets[number] = sheet
    return DrawingSet(path, sheets)


# ---- tag helpers --------------------------------------------------------------------------------
def boxed_spans(sheet: Sheet, pattern: re.Pattern, style: TagStyle = TagStyle()) -> list[tuple[Span, Rect]]:
    """Spans matching `pattern` that sit inside a tag enclosure, excluding schedule tables."""
    out = []
    mw, mh = style.tag_box_max
    for s in sheet.spans_outside_tables():
        if not pattern.match(s.text):
            continue
        box = next((b for b in sheet.boxes if contains(b, s.center) and (b[2] - b[0]) <= mw and (b[3] - b[1]) <= mh), None)
        if box:
            out.append((s, box))
    return out


QUAL_RE = re.compile(r"\(?\s*(TYP\.?(?:\s+OF\s+(\d+))?|NIC|SIM\.?)\s*\)?", re.I)


def tag_qualifier(sheet: Sheet, box: Rect) -> tuple[str, Span | None]:
    """Text immediately to the right of a tag box on the same line: TYP. / TYP. OF n / NIC / SIM."""
    cy = (box[1] + box[3]) / 2
    for s in sorted(sheet.spans, key=lambda s: s.bbox[0]):
        if abs(s.center[1] - cy) < 3 and 0 <= s.bbox[0] - box[2] <= 30 and QUAL_RE.fullmatch(s.text):
            return s.text.upper(), s
    return "", None
