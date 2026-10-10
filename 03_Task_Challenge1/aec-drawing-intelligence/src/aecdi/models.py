"""Core data model: facts with provenance, and evidence-linked findings."""
from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, Field

FindingType = Literal[
    "missing_info",
    "quantity_mismatch",
    "dimension_conflict",
    "cross_discipline_conflict",
    "spec_conflict",
    "revision_issue",
    "tag_conflict",
]
Tier = Literal["confirmed", "probable", "needs_review"]
Severity = Literal["high", "medium", "low"]

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
TIER_ORDER = {"confirmed": 0, "probable": 1, "needs_review": 2}


class Evidence(BaseModel):
    """One anchor in a source document. Every finding needs at least one that verifies."""

    doc: str                      # file name, e.g. CD_Set_RevB.pdf / Spec_Book.pdf / BOQ.xlsx
    snippet: str                  # text that must be re-found at this location
    role: str = ""                # e.g. "plan tag", "schedule row", "BOQ line"
    # PDF anchors
    sheet: str | None = None      # drawing sheet number (A-101) or spec section (08 14 16)
    rev: str | None = None
    page: int | None = None       # 0-based page index in `doc`
    bbox: tuple[float, float, float, float] | None = None
    # Spreadsheet anchors
    xlsx_sheet: str | None = None
    row: int | None = None
    cell: str | None = None
    # Filled by the evidence gate
    verified: bool | None = None


class Finding(BaseModel):
    id: str = ""
    type: FindingType
    severity: Severity
    tier: Tier
    statement: str                               # "potential discrepancy" language, never "error"
    entities: list[str] = Field(default_factory=list)   # normalized keys: DOOR:105, EQUIP:RTU-1, GRID:2-3, SHEET:A-501
    sheets: list[str] = Field(default_factory=list)
    disciplines: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    method: str                                  # rule id or llm model id
    confidence: float
    rationale: str = ""                          # why this tier / what the reviewer should check
    min_evidence: int = 1
    status: Literal["open", "accepted", "rejected"] = "open"
    reviewer: str | None = None
    review_comment: str | None = None

    def fingerprint(self) -> str:
        key = "|".join([self.type, self.method, *sorted(self.entities), *sorted(self.sheets)])
        return hashlib.sha1(key.encode()).hexdigest()[:10]


class RevisionChange(BaseModel):
    """Informational delta-report item (not a finding by itself)."""

    sheet: str
    kind: Literal["added", "removed", "changed", "moved", "graphic"]
    before: str | None = None
    after: str | None = None
    bbox: tuple[float, float, float, float]
    page_b: int
    clouded: bool


class RunResult(BaseModel):
    project: str
    findings: list[Finding]
    rejected: list[Finding] = Field(default_factory=list)   # dropped by the evidence gate
    revision_changes: list[RevisionChange] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)
