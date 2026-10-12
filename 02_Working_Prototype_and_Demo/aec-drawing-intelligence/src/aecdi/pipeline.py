"""End-to-end run: ingest -> project graph -> rule checks (+ optional LLM) -> evidence gate -> findings."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .checks import crossdisc, dimensions, missing, native, quantities, revisions, spec_rules
from .evidence import EvidenceGate
from .graph import build_graph
from .ingest.boq import load_boq
from .ingest.drawings import load_drawing_set
from .ingest.native import load_native_schedule
from .ingest.specs import load_project_manual
from .models import SEVERITY_ORDER, TIER_ORDER, Finding, RunResult


@dataclass
class Inputs:
    rev_b: Path
    rev_a: Path | None = None
    spec: Path | None = None
    boq: Path | None = None
    redlines: Path | None = None      # reviewer markups on the previous revision (PDF annotations)
    native: Path | None = None        # schedule exported from the Revit model (.txt / .csv)

    @classmethod
    def discover(cls, folder: str | Path) -> "Inputs":
        folder = Path(folder)
        pdfs = sorted(folder.glob("*.pdf"))
        markup_words = ("redline", "markup", "comments")
        sets = [p for p in pdfs if not any(w in p.name.lower() for w in markup_words)]

        def pick(*keys, pool=sets):
            return next((p for p in pool if any(k in p.name.lower() for k in keys)), None)

        rev_b = pick("revb", "rev_b", "rev-b", "current")
        rev_a = pick("reva", "rev_a", "rev-a", "previous")
        spec = pick("manual", "spec")
        redlines = next((p for p in pdfs if any(w in p.name.lower() for w in markup_words)), None)
        boq = next(iter(sorted(folder.glob("*.xlsx"))), None)
        native = next((p for p in sorted(folder.glob("*.txt")) + sorted(folder.glob("*.csv"))
                       if "schedule" in p.name.lower()), None)
        if rev_b is None:
            raise FileNotFoundError(f"no current drawing set (*RevB*.pdf) in {folder}")
        return cls(rev_b=rev_b, rev_a=rev_a, spec=spec, boq=boq, redlines=redlines if rev_a else None, native=native)


def _same_anchor(a, b) -> bool:
    return (a.doc == b.doc and a.page == b.page and a.bbox is not None and b.bbox is not None
            and a.bbox[0] < b.bbox[2] and b.bbox[0] < a.bbox[2] and a.bbox[1] < b.bbox[3] and b.bbox[1] < a.bbox[3])


def _merge_llm(rule: list[Finding], llm: list[Finding]) -> list[Finding]:
    """An LLM finding corroborates a rule finding only if it is about the same element AND cites the
    same schedule cell; a real quote attached to a different attribute is not corroboration."""
    kept = []
    for f in llm:
        twin = next((r for r in rule if r.type == f.type and set(r.entities) & set(f.entities)
                     and r.tier != "needs_review"
                     and any(_same_anchor(a, b) for a in f.evidence for b in r.evidence
                             if a.sheet and "-" in a.sheet)), None)    # drawing-sheet anchors (A-601), not spec text
        if twin is not None and f.tier != "needs_review":
            twin.rationale = (twin.rationale + " | " if twin.rationale else "") + f"Corroborated by {f.method}."
            twin.confidence = min(0.97, twin.confidence + 0.05)
        else:
            kept.append(f)
    return rule + kept


@dataclass
class RunOutput:
    result: RunResult
    graph: object
    llm_log: list
    inputs: Inputs


def run(inputs: Inputs, out_dir: Path | None = None, llm_client=None) -> RunOutput:
    t0 = time.perf_counter()
    ds_b = load_drawing_set(inputs.rev_b)
    ds_a = load_drawing_set(inputs.rev_a) if inputs.rev_a else None
    manual = load_project_manual(inputs.spec) if inputs.spec else None
    boq = load_boq(inputs.boq) if inputs.boq else None
    native_sched = load_native_schedule(inputs.native) if inputs.native else None
    g = build_graph(ds_b, manual, boq)
    t_ingest = time.perf_counter() - t0

    findings: list[Finding] = []
    for mod in (missing, quantities, dimensions, crossdisc, spec_rules):
        findings += mod.check(g)
    findings += native.check(g, native_sched)
    changes, markups = [], []
    if ds_a:
        changes, rev_findings = revisions.compare(ds_a, ds_b, g, overlay_dir=(out_dir / "overlays") if out_dir else None)
        findings += rev_findings
        if inputs.redlines:
            markups, markup_findings = revisions.markup_closure(inputs.redlines, ds_a, ds_b, changes)
            findings += markup_findings

    files = {ds_b.doc: inputs.rev_b}
    if ds_a:
        files[ds_a.doc] = inputs.rev_a
    if manual:
        files[manual.doc] = inputs.spec
    if boq:
        files[boq.doc] = inputs.boq
    if inputs.redlines:
        files[inputs.redlines.name] = inputs.redlines
    if native_sched:
        files[native_sched.doc] = inputs.native
    gate = EvidenceGate(files)
    shipped, rejected, gate_stats = gate.apply(findings)

    llm_log, llm_stats = [], {}
    if llm_client is not None:
        from .llm.semantic import run_semantic

        llm_findings, llm_log = run_semantic(g, llm_client)
        llm_shipped, llm_rejected, s = gate.apply(llm_findings)
        llm_stats = {"llm_findings_raw": len(llm_findings), "llm_shipped": len(llm_shipped),
                     "llm_rejected_by_gate": len(llm_rejected), "llm_model": llm_client.name}
        shipped = _merge_llm(shipped, llm_shipped)
        rejected += llm_rejected
        gate_stats = {k: gate_stats[k] + s[k] for k in gate_stats}

    # de-duplicate identical findings, stable ordering, ids
    uniq: dict[str, Finding] = {}
    for f in shipped:
        uniq.setdefault(f.fingerprint(), f)
    ordered = sorted(uniq.values(), key=lambda f: (TIER_ORDER[f.tier] == 2, SEVERITY_ORDER[f.severity], TIER_ORDER[f.tier],
                                                   f.type, f.entities, f.sheets))
    for i, f in enumerate(ordered, 1):
        f.id = f"F-{i:03d}"
    for i, f in enumerate(rejected, 1):
        f.id = f"R-{i:03d}"

    stats = {
        "sheets": len(ds_b.sheets), "spec_sections": len(manual.sections) if manual else 0,
        "boq_items": len(boq.items) if boq else 0, "door_tags": sum(len(v) for v in g.door_tags.values()),
        "door_rows": len(g.door_rows), "equipment_tags": sum(len(v) for v in g.equip_tags.values()),
        "equipment_rows": len(g.equip_rows), "dimensions": sum(len(s.dims) for s in ds_b.sheets.values()),
        "graph_edges": len(set(g.edges)), "revision_changes": len(changes),
        "markups": len(markups), "markups_not_incorporated": sum(1 for m in markups if not m["incorporated"]),
        "native_rows": len(native_sched.rows) if native_sched else 0,
        "unreadable_pages": sum(1 for s in ds_b.sheets.values() if s.raster),
        "findings": len(ordered), "needs_review": sum(1 for f in ordered if f.tier == "needs_review"),
        "rejected_by_gate": len(rejected), **gate_stats, **llm_stats,
        "seconds": round(time.perf_counter() - t0, 2), "ingest_seconds": round(t_ingest, 2),
    }
    result = RunResult(project=inputs.rev_b.parent.name, findings=ordered, rejected=rejected,
                       revision_changes=changes, markups=markups, stats=stats)
    return RunOutput(result, g, llm_log, inputs)
