"""Native model data: schedules exported from Revit (View > Export > Reports > Schedule).

Revit writes a tab-delimited text file: a title line, a header line, an optional blank/grouping
line, then one line per element, with values quoted and inch marks doubled (CSV-style quoting).
When Uppteam authors the model itself, this export is the source of truth for schedule data;
the PDF sheet is what was actually issued. Comparing the two catches sheets issued from an
older model state and manual overrides on sheets.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# Revit parameter name -> header prefix of the issued door schedule. Adjust per office template.
DOOR_COLUMN_MAP = {
    "Mark": "MARK", "Type Mark": "TYPE", "Width": "WIDTH", "Height": "HEIGHT", "Door Material": "MATERIAL",
    "Frame Material": "FRAME", "Fire Rating": "FIRE", "Hardware Set": "HDW", "Spec Section": "SPEC",
}


@dataclass
class NativeSchedule:
    path: Path
    title: str
    headers: list[str]
    rows: list[tuple[int, dict[str, str]]]       # (1-based line number, {header: value})

    @property
    def doc(self) -> str:
        return self.path.name


def read_rows(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    delim = "\t" if "\t" in text.splitlines()[1 if len(text.splitlines()) > 1 else 0] else ","
    return list(csv.reader(text.splitlines(), delimiter=delim, quotechar='"'))


def load_native_schedule(path: str | Path, key: str = "Mark") -> NativeSchedule:
    path = Path(path)
    rows = read_rows(path)
    title = rows[0][0] if rows and rows[0] else path.stem
    h = next(i for i, r in enumerate(rows) if key in r)
    headers = rows[h]
    out = []
    for i, r in enumerate(rows[h + 1:], start=h + 2):
        if len(r) == len(headers) and r[headers.index(key)].strip():
            out.append((i, dict(zip(headers, r))))
    return NativeSchedule(path, title, headers, out)
