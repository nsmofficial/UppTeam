"""Imperial dimension and drawing-scale parsing.

Handles the forms that appear on U.S. construction documents:
    24'-6"   24'-6 1/2"   24' - 6"   30'-0"   30'   6"   1'-0 3/4"
and architectural scales such as  1/8" = 1'-0"  or  3/16" = 1'-0".
"""
from __future__ import annotations

import re
from fractions import Fraction

_QUOTES = str.maketrans({"′": "'", "’": "'", "″": '"', "”": '"', "–": "-", "—": "-"})

DIM_RE = re.compile(
    r"""^\s*
    (?:(?P<ft>\d+)\s*'\s*(?:-\s*)?)?          # feet
    (?:(?P<inch>\d+)(?:\s+(?P<num>\d+)/(?P<den>\d+))?\s*")?   # inches + optional fraction
    \s*$""",
    re.VERBOSE,
)


def normalize_text(s: str) -> str:
    return " ".join(s.translate(_QUOTES).split())


def parse_feet_inches(text: str) -> float | None:
    """Return the length in decimal feet, or None if `text` is not a dimension string."""
    s = normalize_text(text)
    if not s or not any(c in s for c in "'\""):
        return None
    m = DIM_RE.match(s)
    if not m or (m.group("ft") is None and m.group("inch") is None):
        return None
    feet = int(m.group("ft") or 0)
    inches = Fraction(int(m.group("inch") or 0))
    if m.group("num"):
        den = int(m.group("den"))
        if den == 0:
            return None
        inches += Fraction(int(m.group("num")), den)
    return float(feet + inches / 12)


def is_dimension(text: str) -> bool:
    return parse_feet_inches(text) is not None


def format_feet_inches(feet: float) -> str:
    """24.5 -> 24'-6"   (rounded to the nearest 1/2 inch)."""
    total_half_inches = round(feet * 24)
    ft, rem = divmod(total_half_inches, 24)
    inch, half = divmod(rem, 2)
    return f"{ft}'-{inch} 1/2\"" if half else f"{ft}'-{inch}\""


SCALE_RE = re.compile(
    r"""(?P<paper>\d+(?:/\d+)?|\d+\s+\d+/\d+)\s*"\s*=\s*(?P<real>[\d'\-" /]+)""",
)


RATIO_RE = re.compile(r"^\s*1\s*:\s*(\d+(?:\.\d+)?)\s*$")
MM_RE = re.compile(r"^\d{1,3}(?:[ ,.]?\d{3})$")
MM_PER_FT = 304.8


def is_metric_scale(text: str | None) -> bool:
    return bool(text) and bool(RATIO_RE.match(normalize_text(text).upper().replace("SCALE:", "")))


def parse_mm(text: str) -> float | None:
    """Metric dimension string in millimetres ('7620', '7 620', '7,620') -> feet. Values under 300 mm are
    rejected so room numbers and door marks are never read as dimensions."""
    s = normalize_text(text)
    if not MM_RE.match(s):
        return None
    mm = int(re.sub(r"[ ,.]", "", s))
    return mm / MM_PER_FT if mm >= 300 else None


def parse_length(text: str, metric: bool = False) -> float | None:
    return parse_mm(text) if metric else parse_feet_inches(text)


def format_length(feet: float, metric: bool = False) -> str:
    return str(int(round(feet * MM_PER_FT))) if metric else format_feet_inches(feet)


def parse_scale(text: str) -> float | None:
    """Return PDF points per real foot for a scale note: 1/8" = 1'-0" -> 9.0 ; 1:100 -> 8.64."""
    s = normalize_text(text).upper().replace("SCALE:", "").strip()
    if "NTS" in s or "NOT TO SCALE" in s:
        return None
    r = RATIO_RE.match(s)
    if r:
        return 72.0 / 25.4 * MM_PER_FT / float(r.group(1))
    m = SCALE_RE.search(s)
    if not m:
        return None
    paper_in = float(sum(Fraction(p) for p in m.group("paper").split()))
    real_ft = parse_feet_inches(m.group("real").strip())
    if not real_ft:
        return None
    return paper_in * 72.0 / real_ft
