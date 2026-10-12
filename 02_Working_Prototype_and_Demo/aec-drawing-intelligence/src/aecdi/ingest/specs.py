"""Project manual (specification) ingestion, organised by CSI MasterFormat section.

Output: sections -> articles -> lettered paragraphs, each paragraph keeping its page and the
bbox of every visual row so a quoted phrase can be located again by the evidence gate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from ..units import normalize_text

SECTION_RE = re.compile(r"^SECTION\s+(\d{2}\s\d{2}\s\d{2}(?:\.\d+)?)\b", re.I)
PART_RE = re.compile(r"^PART\s+(\d)\b", re.I)
ARTICLE_RE = re.compile(r"^(\d\.\d{1,2})\s+(.*)$")
PARA_RE = re.compile(r"^([A-Z])\.$")
HW_SET_RE = re.compile(r"\b(HW-\d+[A-Z]?)\s*:")


@dataclass
class Paragraph:
    id: str                 # "08 14 16 2.1.C"
    section: str
    text: str
    page: int
    rows: list[tuple[str, tuple]] = field(default_factory=list)

    @property
    def bbox(self):
        xs0, ys0, xs1, ys1 = zip(*(b for _, b in self.rows))
        return (min(xs0), min(ys0), max(xs1), max(ys1))


@dataclass
class SpecSection:
    number: str
    title: str
    page: int
    header_bbox: tuple
    paragraphs: list[Paragraph] = field(default_factory=list)

    def text(self) -> str:
        return " ".join(p.text for p in self.paragraphs)


@dataclass
class ProjectManual:
    path: Path
    sections: dict[str, SpecSection]

    @property
    def doc(self) -> str:
        return self.path.name

    def hardware_sets(self) -> dict[str, Paragraph]:
        out = {}
        sec = self.sections.get("08 71 00")
        if sec:
            for p in sec.paragraphs:
                for m in HW_SET_RE.finditer(p.text):
                    out[m.group(1)] = p
        return out


def _rows(page: pymupdf.Page):
    """Visual rows: spans sharing a baseline, left to right."""
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = normalize_text(s["text"])
                if t:
                    spans.append((t, tuple(s["bbox"])))
    spans.sort(key=lambda s: (round(s[1][3]), s[1][0]))
    rows: list[list] = []
    for t, bb in spans:
        if rows and abs(rows[-1][-1][1][3] - bb[3]) < 2.0:
            rows[-1].append((t, bb))
        else:
            rows.append([(t, bb)])
    return rows


def load_project_manual(path: str | Path) -> ProjectManual:
    path = Path(path)
    doc = pymupdf.open(path)
    sections: dict[str, SpecSection] = {}
    cur: SpecSection | None = None
    article = ""
    para: Paragraph | None = None
    for pno, page in enumerate(doc):
        H = page.rect.height
        rows = _rows(page)
        for i, row in enumerate(rows):
            text = " ".join(t for t, _ in row)
            bb = (min(b[0] for _, b in row), min(b[1] for _, b in row), max(b[2] for _, b in row), max(b[3] for _, b in row))
            if bb[1] < 0.07 * H or bb[1] > 0.93 * H:          # running header / footer
                continue
            m = SECTION_RE.match(text)
            if m:
                number = m.group(1)
                title = " ".join(t for t, _ in rows[i + 1]) if i + 1 < len(rows) else ""
                cur = SpecSection(number, title, pno, bb)
                sections[number] = cur
                article, para = "", None
                continue
            if cur is None or text.upper() == cur.title.upper() or text.upper().startswith("END OF SECTION"):
                para = None
                continue
            if PART_RE.match(text):
                para = None
                continue
            am = ARTICLE_RE.match(text)
            if am and not PARA_RE.match(row[0][0]):
                article, para = am.group(1), None
                continue
            if PARA_RE.match(row[0][0]):
                letter = row[0][0][0]
                body = row[1:]
                para = Paragraph(f"{cur.number} {article}.{letter}", cur.number,
                                 " ".join(t for t, _ in body), pno, [(" ".join(t for t, _ in body), bb)])
                cur.paragraphs.append(para)
            elif para is not None:
                para.text = f"{para.text} {text}"
                para.rows.append((text, bb))
    return ProjectManual(path, sections)
