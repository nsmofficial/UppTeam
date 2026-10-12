"""Spec-vs-schedule semantic check with an LLM.

One request per governing spec section: the section's paragraphs (with ids) and every schedule
row that cites it. The model returns structured JSON (schema-constrained) naming the element,
the schedule value, the paragraph id and a verbatim spec quote. Those become evidence anchors;
the evidence gate then re-finds each one in the PDF. Anything the model invents - an element
that does not exist, a quote that is not in the spec, a value that is not in the schedule cell -
fails the gate and is logged as rejected, never shown to the engineer as a finding.

Clients:
  AnthropicClient  live Claude call (needs ANTHROPIC_API_KEY or an `ant auth login` profile)
  ReplayClient     returns responses recorded by a previous live run (reproducible demos/evals)
  MockClient       scripted responses for tests and hallucination-injection experiments
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from ..checks import mk
from ..graph import ProjectGraph, Row
from ..models import Evidence, Finding

MODEL = "claude-opus-5-5"

SYSTEM = (
    "You review U.S. construction documents for potential discrepancies between schedules and the "
    "specification section that governs them. Report a conflict only when a schedule value contradicts an "
    "explicit requirement in the provided spec text. Quote the spec verbatim (copy the exact words) and give the "
    "schedule value exactly as it appears in the row. If the spec text is silent or ambiguous about a value, "
    "do not report a conflict; list it under 'unclear' instead. Never use outside knowledge of products or codes "
    "as the basis for a conflict."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "element": {"type": "string", "description": "element key exactly as given, e.g. DOOR:101"},
                    "attribute": {"type": "string", "description": "schedule column name exactly as given"},
                    "schedule_value": {"type": "string"},
                    "paragraph_id": {"type": "string"},
                    "spec_quote": {"type": "string"},
                    "explanation": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "confidence": {"type": "number"},
                },
                "required": ["element", "attribute", "schedule_value", "paragraph_id", "spec_quote", "explanation",
                             "severity", "confidence"],
                "additionalProperties": False,
            },
        },
        "unclear": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"element": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["element", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["conflicts", "unclear"],
    "additionalProperties": False,
}


class LLMClient(Protocol):
    name: str

    def complete_json(self, system: str, user: str, schema: dict, meta: dict) -> dict: ...


def request_key(system: str, user: str, schema: dict) -> str:
    return hashlib.sha256(json.dumps([system, user, schema], sort_keys=True).encode()).hexdigest()[:24]


class AnthropicClient:
    """Live call. Uses schema-constrained output (output_config.format) and server-side refusal fallbacks."""

    def __init__(self, model: str = MODEL, effort: str = "high"):
        import anthropic   # optional dependency

        self.anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.name = f"llm:{model}"

    def complete_json(self, system: str, user: str, schema: dict, meta: dict) -> dict:
        resp = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            return {"conflicts": [], "unclear": [{"element": "*", "reason": "model declined the request"}]}
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("LLM response truncated (max_tokens)")
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)


class RecordingClient:
    def __init__(self, inner: LLMClient, cache_dir: Path):
        self.inner, self.cache_dir, self.name = inner, cache_dir, inner.name
        cache_dir.mkdir(parents=True, exist_ok=True)

    def complete_json(self, system, user, schema, meta):
        out = self.inner.complete_json(system, user, schema, meta)
        (self.cache_dir / f"{request_key(system, user, schema)}.json").write_text(
            json.dumps({"meta": meta, "model": self.name, "response": out}, indent=2), encoding="utf-8")
        return out


class ReplayClient:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.name = "llm:replay"

    def complete_json(self, system, user, schema, meta):
        p = self.cache_dir / f"{request_key(system, user, schema)}.json"
        if not p.exists():
            raise FileNotFoundError(f"no recorded LLM response for {meta.get('section')} ({p.name}); run once with --llm anthropic --record")
        rec = json.loads(p.read_text(encoding="utf-8"))
        self.name = rec.get("model", self.name) + " (replay)"
        return rec["response"]


class MockClient:
    def __init__(self, responder: Callable[[dict], dict], name: str = "llm:mock"):
        self.responder, self.name = responder, name

    def complete_json(self, system, user, schema, meta):
        return self.responder(meta)


@dataclass
class SemanticRequest:
    section: str
    user: str
    rows: dict[str, Row]          # element key -> schedule row


def build_requests(g: ProjectGraph) -> list[SemanticRequest]:
    if not g.manual:
        return []
    by_sec: dict[str, dict[str, Row]] = defaultdict(dict)
    for mark, rows in g.door_rows.items():
        by_sec[rows[0].val("SPEC")][f"DOOR:{mark}"] = rows[0]
    for tag, rows in g.equip_rows.items():
        by_sec[rows[0].val("SPEC")][f"EQUIP:{tag}"] = rows[0]
    reqs = []
    for sec_no in sorted(by_sec):
        sec = g.manual.sections.get(sec_no)
        if not sec:
            continue
        rows = by_sec[sec_no]
        lines = [f"SPEC SECTION {sec.number} - {sec.title}"]
        lines += [f"[{p.id}] {p.text}" for p in sec.paragraphs]
        lines.append("")
        lines.append("SCHEDULE ROWS CITING THIS SECTION:")
        for key in sorted(rows):
            r = rows[key]
            cells = " | ".join(f"{h}={c.text or '(blank)'}" for h, c in zip(r.table.headers, r.cells))
            lines.append(f"[{key}] (sheet {r.sheet.number}) {cells}")
        lines.append("")
        lines.append("Return every schedule value that contradicts an explicit requirement of this section.")
        reqs.append(SemanticRequest(sec_no, "\n".join(lines), rows))
    return reqs


def run_semantic(g: ProjectGraph, client: LLMClient) -> tuple[list[Finding], list[dict]]:
    findings, log = [], []
    for req in build_requests(g):
        meta = {"section": req.section, "elements": sorted(req.rows)}
        try:
            resp = client.complete_json(SYSTEM, req.user, SCHEMA, meta)
        except Exception as e:   # network / cache miss: abstain, never guess
            log.append({"section": req.section, "error": str(e)})
            continue
        log.append({"section": req.section, "response": resp})
        sec = g.manual.sections[req.section]
        paras = {p.id: p for p in sec.paragraphs}
        for c in resp.get("conflicts", []):
            row = req.rows.get(c.get("element", ""))
            para = paras.get(c.get("paragraph_id", ""))
            ev: list[Evidence] = []
            if row is not None:
                col = next((h for h in row.table.headers if h.upper() == str(c.get("attribute", "")).upper()), None)
                cell = row.get(col) if col else None
                if cell is not None and cell.bbox:
                    ev.append(Evidence(doc=g.drawings.doc, sheet=row.sheet.number, rev=row.sheet.rev, page=row.sheet.page,
                                       bbox=cell.bbox, snippet=str(c.get("schedule_value", "")), role="schedule value (LLM-cited)"))
            if para is not None:
                ev.append(g.ev_para(para, str(c.get("spec_quote", "")), "spec quote (LLM-cited)"))
            else:
                ev.append(Evidence(doc=g.manual.doc, sheet=req.section, page=None, bbox=None,
                                   snippet=str(c.get("spec_quote", "")), role=f"spec quote, unknown paragraph {c.get('paragraph_id')}"))
            f = mk("spec_conflict", c.get("severity", "medium"), "probable",
                   f"Potential discrepancy: {c.get('element')} {c.get('attribute')} = '{c.get('schedule_value')}' vs "
                   f"Section {req.section}: \"{c.get('spec_quote')}\". {c.get('explanation', '')}".strip(),
                   [c.get("element", "?")], ev, client.name, min(float(c.get("confidence", 0.7)), 0.85),
                   "LLM judgment; both citations re-verified against the source by the evidence gate.", min_evidence=2)
            findings.append(f)
        for u in resp.get("unclear", []):
            row = req.rows.get(u.get("element", ""))
            if row is None:
                continue
            findings.append(mk("spec_conflict", "low", "needs_review",
                               f"Needs review: {u.get('element')} vs Section {req.section}: {u.get('reason')}",
                               [u["element"]], [Evidence(doc=g.drawings.doc, sheet=row.sheet.number, rev=row.sheet.rev,
                                                         page=row.sheet.page, bbox=row.cells[0].bbox, snippet=row.cells[0].text,
                                                         role="schedule row")],
                               client.name, 0.4, "Model could not decide from the spec text; routed to a person."))
    return findings, log
