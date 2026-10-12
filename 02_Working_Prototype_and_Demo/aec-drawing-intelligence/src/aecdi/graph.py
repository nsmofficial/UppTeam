"""Project graph: links every tag, schedule row, spec section, BOQ line and sheet reference,
each fact carrying its provenance. Checks query these indexes; `to_json()` exports the graph
(nodes + typed edges + evidence) for traceability and for the review UI."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

import pymupdf

from .ingest.boq import Boq, BoqItem
from .ingest.drawings import (QUAL_RE, SHEET_REF_RE, Cell, DrawingSet, Sheet, Span, Table, TagStyle, boxed_spans,
                              tag_qualifier)
from .ingest.specs import Paragraph, ProjectManual
from .models import Evidence

RTU_LIMIT_RE = re.compile(r"\b((?:RTU|AHU|DOAS)-\d+)\b.*?WEIGHT\s+([\d,]+)\s*LB", re.I)
SPEC_NO_RE = re.compile(r"\b(\d{2}\s\d{2}\s\d{2})\b")


@dataclass
class Row:
    sheet: Sheet
    table: Table
    cells: list[Cell]

    def get(self, *names: str) -> Cell | None:
        i = self.table.col(*names)
        return self.cells[i] if i is not None and i < len(self.cells) else None

    def val(self, *names: str) -> str:
        c = self.get(*names)
        return c.text if c else ""


@dataclass
class TagHit:
    sheet: Sheet
    span: Span
    box: tuple
    qualifier: str = ""
    qual_span: Span | None = None

    @property
    def count(self) -> int | None:
        """Number of physical elements represented; None = unknown (TYP. without a count)."""
        m = QUAL_RE.fullmatch(self.qualifier) if self.qualifier else None
        if not m:
            return 1
        if m.group(2):
            return int(m.group(2))
        return None if m.group(1).upper().startswith("TYP") else 1


@dataclass
class ProjectGraph:
    drawings: DrawingSet
    manual: ProjectManual | None
    boq: Boq | None
    style: TagStyle = field(default_factory=TagStyle)
    door_tags: dict[str, list[TagHit]] = field(default_factory=lambda: defaultdict(list))
    door_rows: dict[str, list[Row]] = field(default_factory=lambda: defaultdict(list))
    equip_tags: dict[str, list[TagHit]] = field(default_factory=lambda: defaultdict(list))
    equip_rows: dict[str, list[Row]] = field(default_factory=lambda: defaultdict(list))
    panel_rows: dict[str, list[Row]] = field(default_factory=lambda: defaultdict(list))
    index_rows: dict[str, Row] = field(default_factory=dict)
    sheet_refs: list[tuple[Sheet, str, Span | None, tuple]] = field(default_factory=list)
    struct_limits: dict[str, tuple[Sheet, Span, int]] = field(default_factory=dict)
    spec_refs: dict[str, list[Evidence]] = field(default_factory=lambda: defaultdict(list))
    edges: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def door_schedule_sheets(self) -> list[str]:
        return sorted({r.sheet.number for rows in self.door_rows.values() for r in rows})

    @property
    def equip_schedule_sheets(self) -> list[str]:
        return sorted({r.sheet.number for rows in self.equip_rows.values() for r in rows})

    # ---- evidence constructors ----------------------------------------------------------------
    def ev_span(self, sheet: Sheet, span: Span, role: str) -> Evidence:
        return Evidence(doc=self.drawings.doc, sheet=sheet.number, rev=sheet.rev, page=sheet.page, bbox=span.bbox,
                        snippet=span.text, role=role)

    def ev_cell(self, row: Row, col: str | tuple, role: str) -> Evidence | None:
        cell = row.get(*(col if isinstance(col, tuple) else (col,)))
        if cell is None or cell.bbox is None:
            return None
        return Evidence(doc=self.drawings.doc, sheet=row.sheet.number, rev=row.sheet.rev, page=row.sheet.page,
                        bbox=cell.bbox, snippet=cell.text, role=role)

    def ev_para(self, para: Paragraph, quote: str | None, role: str) -> Evidence:
        bbox = para.bbox
        snippet = quote or para.rows[0][0]
        if quote and self.manual:
            page = pymupdf.open(self.manual.path)[para.page]
            hits = page.search_for(quote, clip=pymupdf.Rect(bbox) + (-2, -2, 2, 2))
            if hits:
                r = hits[0]
                for h in hits[1:]:
                    r |= h
                bbox = tuple(round(v, 2) for v in r)
        return Evidence(doc=self.manual.doc if self.manual else "", sheet=para.section, page=para.page,
                        bbox=bbox, snippet=snippet, role=role)

    def ev_section_header(self, number: str) -> Evidence | None:
        sec = self.manual.sections.get(number) if self.manual else None
        if not sec:
            return None
        return Evidence(doc=self.manual.doc, sheet=number, page=sec.page, bbox=sec.header_bbox,
                        snippet=f"SECTION {number}", role="spec section")

    def ev_boq(self, item: BoqItem, col: str, role: str) -> Evidence:
        snippet = {"qty": _fmt_qty(item.qty), "item": item.item, "desc": item.desc, "spec": item.spec or ""}[col]
        return Evidence(doc=self.boq.doc, xlsx_sheet=item.sheet, row=item.row, cell=item.cols.get(col),
                        snippet=snippet, role=role)


def _fmt_qty(q) -> str:
    if q is None:
        return ""
    return str(int(q)) if float(q).is_integer() else str(q)


def build_graph(drawings: DrawingSet, manual: ProjectManual | None, boq: Boq | None,
                style: TagStyle | None = None) -> ProjectGraph:
    g = ProjectGraph(drawings, manual, boq, style or TagStyle())
    st = g.style
    for sheet in drawings.sheets.values():
        # tags on plans
        doors_here = sheet.discipline in st.door_disciplines
        equip_here = sheet.discipline in st.equipment_disciplines
        for span, box in boxed_spans(sheet, st.door_mark, st) if doors_here else []:
            g.door_tags[span.text].append(TagHit(sheet, span, box))
            g.edges.append((f"DOOR:{span.text}", "appears_on", f"SHEET:{sheet.number}"))
        for span, box in boxed_spans(sheet, st.equipment, st) if equip_here else []:
            q, qs = tag_qualifier(sheet, box)
            g.equip_tags[span.text].append(TagHit(sheet, span, box, q, qs))
            g.edges.append((f"EQUIP:{span.text}", "appears_on", f"SHEET:{sheet.number}"))
        # schedules by header signature
        for t in sheet.tables:
            if t.has("MARK", "TYPE") and t.col("FIRE", "HDW", "HARDWARE") is not None:
                for cells in t.rows:
                    r = Row(sheet, t, cells)
                    mark = r.val("MARK")
                    if mark:
                        g.door_rows[mark].append(r)
                        g.edges.append((f"DOOR:{mark}", "defined_in", f"SHEET:{sheet.number}"))
                        if r.val("TYPE"):
                            g.edges.append((f"DOOR:{mark}", "is_type", f"DOORTYPE:{r.val('TYPE')}"))
                        for s in SPEC_NO_RE.findall(r.val("SPEC")):
                            g.spec_refs[s].append(g.ev_cell(r, "SPEC", "door schedule"))
                            g.edges.append((f"DOORTYPE:{r.val('TYPE')}", "governed_by", f"SPEC:{s}"))
            elif t.has("TAG", "QTY"):
                for cells in t.rows:
                    r = Row(sheet, t, cells)
                    tag = r.val("TAG")
                    if tag:
                        g.equip_rows[tag].append(r)
                        g.edges.append((f"EQUIP:{tag}", "defined_in", f"SHEET:{sheet.number}"))
                        for s in SPEC_NO_RE.findall(r.val("SPEC")):
                            g.spec_refs[s].append(g.ev_cell(r, "SPEC", "equipment schedule"))
                            g.edges.append((f"EQUIP:{tag}", "governed_by", f"SPEC:{s}"))
            elif t.has("CKT", "LOAD"):
                for cells in t.rows:
                    r = Row(sheet, t, cells)
                    load = r.val("LOAD")
                    m = st.equipment.match(load.split()[0]) if load else None
                    key = m.group(0) if m else load
                    g.panel_rows[key].append(r)
                    if m:
                        g.edges.append((f"EQUIP:{key}", "fed_by", f"CKT:{r.val('PANEL')}-{r.val('CKT')}"))
            elif t.has("SHEET") and t.col("SHEET TITLE", "TITLE") is not None:
                for cells in t.rows:
                    r = Row(sheet, t, cells)
                    num = r.val("SHEET")
                    if num:
                        g.index_rows[num] = r
                        g.edges.append((f"SHEET:{num}", "listed_in_index", f"SHEET:{sheet.number}"))
        # sheet references: callouts + notes ("SEE A-601")
        for detail, ref, circle, ref_bbox in sheet.callouts:
            span = next((s for s in sheet.spans if s.bbox == ref_bbox), None)
            g.sheet_refs.append((sheet, ref, span, ref_bbox))
            g.edges.append((f"SHEET:{sheet.number}", "references", f"SHEET:{ref}"))
        callout_boxes = {c[3] for c in sheet.callouts}
        for span in sheet.spans_outside_tables():
            if span.bbox in callout_boxes:
                continue
            for m in SHEET_REF_RE.finditer(span.text):
                if m.group(1) != sheet.number:
                    g.sheet_refs.append((sheet, m.group(1), span, span.bbox))
                    g.edges.append((f"SHEET:{sheet.number}", "references", f"SHEET:{m.group(1)}"))
            for s in SPEC_NO_RE.findall(span.text) if "SECTION" in span.text.upper() else []:
                g.spec_refs[s].append(g.ev_span(sheet, span, "drawing note"))
            lm = RTU_LIMIT_RE.search(span.text)
            if lm:
                g.struct_limits[lm.group(1)] = (sheet, span, int(lm.group(2).replace(",", "")))
                g.edges.append((f"EQUIP:{lm.group(1)}", "supported_by", f"SHEET:{sheet.number}"))
    if boq:
        for it in boq.items:
            if it.spec:
                g.spec_refs[it.spec].append(g.ev_boq(it, "spec", "BOQ line"))
            if it.door_type:
                g.edges.append((f"BOQ:{it.item}", "quantifies", f"DOORTYPE:{it.door_type}"))
            if it.equipment_tag:
                g.edges.append((f"BOQ:{it.item}", "quantifies", f"EQUIP:{it.equipment_tag}"))
    return g


def to_json(g: ProjectGraph) -> dict:
    nodes: dict[str, dict] = {}

    def node(key, **attrs):
        n = nodes.setdefault(key, {"id": key, "kind": key.split(":")[0], "evidence": []})
        n.update({k: v for k, v in attrs.items() if v is not None})
        return n

    for s in g.drawings.sheets.values():
        node(f"SHEET:{s.number}", title=s.title, rev=s.rev, page=s.page)
    for mark, hits in g.door_tags.items():
        n = node(f"DOOR:{mark}")
        n["evidence"] += [g.ev_span(h.sheet, h.span, "plan tag").model_dump(exclude_none=True) for h in hits]
    for mark, rows in g.door_rows.items():
        n = node(f"DOOR:{mark}", type=rows[0].val("TYPE"), material=rows[0].val("MATERIAL"),
                 fire_rating=rows[0].val("FIRE"), hardware=rows[0].val("HDW", "HARDWARE"))
        n["evidence"] += [e.model_dump(exclude_none=True) for r in rows if (e := g.ev_cell(r, "MARK", "schedule row"))]
    for tag, hits in g.equip_tags.items():
        n = node(f"EQUIP:{tag}")
        n["evidence"] += [g.ev_span(h.sheet, h.span, f"plan tag {h.qualifier}".strip()).model_dump(exclude_none=True) for h in hits]
    for tag, rows in g.equip_rows.items():
        node(f"EQUIP:{tag}", qty=rows[0].val("QTY"), volts=rows[0].val("V/PH"), weight=rows[0].val("WEIGHT"))
    if g.manual:
        for num, sec in g.manual.sections.items():
            node(f"SPEC:{num}", title=sec.title, paragraphs=len(sec.paragraphs))
    if g.boq:
        for it in g.boq.items:
            node(f"BOQ:{it.item}", desc=it.desc, qty=it.qty, unit=it.unit)
    for a, _, b in g.edges:
        node(a)
        node(b)
    seen, edges = set(), []
    for e in g.edges:
        if e not in seen:
            seen.add(e)
            edges.append({"source": e[0], "rel": e[1], "target": e[2]})
    return {"nodes": list(nodes.values()), "edges": edges}
