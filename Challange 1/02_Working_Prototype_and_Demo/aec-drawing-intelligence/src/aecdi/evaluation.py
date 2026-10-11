"""Evaluation harness.

* Detection: each seeded defect lists the finding signatures that count as a correct detection
  (type + entity + sheet). Precision is over shipped findings (confirmed + probable); recall is over
  seeded defects. needs_review items are reported separately (abstentions, not claims).
* Localisation: a detected defect is localised when a matching finding has an evidence anchor on
  the ground-truth page overlapping the ground-truth bbox (or the ground-truth BOQ row).
* Negative controls: sets with zero seeded defects; every shipped finding is a false positive.
* Determinism: the same inputs run twice must give byte-identical findings.
* Hallucination injection: a mock LLM returns correct conflicts plus fabricated ones (invented
  quotes, elements, values, paragraph ids, altered numbers); we measure how many the evidence gate stops.
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path

from .llm.semantic import MockClient, build_requests
from .models import Finding
from .pipeline import Inputs, run
from .synth.render import generate

TYPES = ["missing_info", "quantity_mismatch", "dimension_conflict", "cross_discipline_conflict", "spec_conflict",
         "revision_issue", "tag_conflict"]


def _sig_match(f: Finding, sig: dict) -> bool:
    return (f.type == sig["type"] and set(f.entities) & set(sig["entities"])
            and (not sig.get("sheets") or set(f.sheets) & set(sig["sheets"])))


def _overlap_frac(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])) or 1.0
    return inter / area


def _localised(f: Finding, gts: list[dict]) -> bool:
    for gt in gts:
        for e in f.evidence:
            if gt.get("row") is not None and e.xlsx_sheet and e.row == gt["row"]:
                return True
            if gt.get("bbox") and e.bbox and e.doc == gt["doc"] and e.page == gt["page"] and _overlap_frac(e.bbox, gt["bbox"]) >= 0.5:
                return True
    return False


def score_project(findings: list[Finding], key: dict) -> dict:
    shipped = [f for f in findings if f.tier != "needs_review"]
    review = [f for f in findings if f.tier == "needs_review"]
    defects = key["defects"]
    f_match = {f.id: [d["id"] for d in defects if any(_sig_match(f, s) for s in d["accept"])] for f in findings}
    detected = {d["id"]: [f for f in shipped if d["id"] in f_match[f.id]] for d in defects}
    per_type = defaultdict(lambda: {"tp": 0, "fp": 0, "defects": 0, "detected": 0})
    for f in shipped:
        per_type[f.type]["tp" if f_match[f.id] else "fp"] += 1
    for d in defects:
        t = d["accept"][0]["type"]
        per_type[t]["defects"] += 1
        per_type[t]["detected"] += bool(detected[d["id"]])
    loc_total = loc_ok = 0
    for d in defects:
        if detected[d["id"]] and any(g.get("bbox") or g.get("row") for g in d["gt"]):
            loc_total += 1
            loc_ok += any(_localised(f, d["gt"]) for f in detected[d["id"]])
    trap_entities = {t["entity"] for t in key.get("traps", [])}
    return {
        "shipped": len(shipped),
        "tp": sum(1 for f in shipped if f_match[f.id]),
        "fp": [f"{f.id} {f.method} {f.statement[:120]}" for f in shipped if not f_match[f.id]],
        "defects": len(defects),
        "detected": sum(1 for v in detected.values() if v),
        "missed": [f"{d['id']} {d['kind']}: {d['description']}" for d in defects if not detected[d["id"]]],
        "by_tier": {t: {"n": sum(1 for f in shipped if f.tier == t),
                        "tp": sum(1 for f in shipped if f.tier == t and f_match[f.id])} for t in ("confirmed", "probable")},
        "per_type": dict(per_type),
        "localisation": {"detected_with_gt": loc_total, "localised": loc_ok},
        "needs_review": {"n": len(review),
                         "on_trap": sum(1 for f in review if set(f.entities) & trap_entities),
                         "on_defect": sum(1 for f in review if f_match[f.id])},
        "trap_violations": [f.statement[:120] for f in shipped if set(f.entities) & trap_entities and not f_match[f.id]],
    }


def _prf(tp, fp, detected, defects):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = detected / defects if defects else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f1, 3)


def hallucination_injection(project_dir: Path) -> dict:
    """Mock LLM = correct conflicts (taken from verified rule findings) + 5 fabrications per request."""
    base = run(Inputs.discover(project_dir))
    g = base.graph
    honest_by_sec = defaultdict(list)
    for f in base.result.findings:
        if f.type != "spec_conflict" or not f.method.startswith("rule:"):
            continue
        cell = next(e for e in f.evidence if e.doc.endswith(".pdf") and e.sheet and "-" in e.sheet)
        para_ev = next(e for e in f.evidence if e.doc == g.manual.doc)
        row = (g.door_rows.get(f.entities[0].split(":")[1]) or g.equip_rows.get(f.entities[0].split(":")[1]))[0]
        attr = next(h for h, c in zip(row.table.headers, row.cells) if c.bbox == cell.bbox)
        para = next(p for p in g.manual.sections[para_ev.sheet].paragraphs if para_ev.snippet in p.text)
        honest_by_sec[para_ev.sheet].append({"element": f.entities[0], "attribute": attr, "schedule_value": cell.snippet,
                                             "paragraph_id": para.id, "spec_quote": para_ev.snippet,
                                             "explanation": "honest", "severity": "high", "confidence": 0.8})
    injected_total = 0

    def responder(meta):
        nonlocal injected_total
        sec = meta["section"]
        honest = honest_by_sec.get(sec, [])
        req = next(r for r in build_requests(g) if r.section == sec)
        el = sorted(req.rows)[0]
        row = req.rows[el]
        sec_obj = g.manual.sections[sec]
        p0 = sec_obj.paragraphs[-1]
        h0, c0 = row.table.headers[1], row.cells[1]
        m = re.search(r"\d+", p0.text)
        if m:
            altered = (p0.text[:m.start()] + str(int(m.group(0)) + 7) + p0.text[m.end():])[: max(60, m.end() + 5)]
        else:
            altered = p0.text.replace(" ", " not ", 1)
        fakes = [
            {"element": el, "attribute": h0, "schedule_value": c0.text, "paragraph_id": p0.id,
             "spec_quote": "shall be rated 90 minutes minimum", "explanation": "fabricated quote"},
            {"element": "DOOR:999" if el.startswith("DOOR") else "EQUIP:XX-9", "attribute": h0, "schedule_value": c0.text,
             "paragraph_id": p0.id, "spec_quote": p0.text[:40], "explanation": "nonexistent element"},
            {"element": el, "attribute": h0, "schedule_value": c0.text + "X", "paragraph_id": p0.id,
             "spec_quote": p0.text[:40], "explanation": "wrong schedule value"},
            {"element": el, "attribute": h0, "schedule_value": c0.text, "paragraph_id": f"{sec} 9.9.Z",
             "spec_quote": p0.text[:40], "explanation": "invented paragraph id"},
            {"element": el, "attribute": h0, "schedule_value": c0.text, "paragraph_id": p0.id,
             "spec_quote": altered, "explanation": "altered number in quote"},
        ]
        for fk in fakes:
            fk.update({"severity": "high", "confidence": 0.9})
        injected_total += len(fakes)
        # real quote + real value, but the claimed conflict is not supported by them (misattribution).
        unsupported = {"element": el, "attribute": h0, "schedule_value": c0.text, "paragraph_id": p0.id,
                       "spec_quote": p0.text[:40], "explanation": "UNSUPPORTED: real citation, false claim",
                       "severity": "high", "confidence": 0.9}
        return {"conflicts": honest + fakes + [unsupported], "unclear": []}

    out = run(Inputs.discover(project_dir), llm_client=MockClient(responder, "llm:mock-adversarial"))
    st = out.result.stats
    honest_n = sum(len(v) for v in honest_by_sec.values())
    rejected = [f for f in out.result.rejected if f.method == "llm:mock-adversarial" and "UNSUPPORTED" not in f.statement]
    fabricated_shipped = [f for f in out.result.findings if f.method == "llm:mock-adversarial" and "UNSUPPORTED" not in f.statement]
    unsupported_shipped = [f for f in out.result.findings if "UNSUPPORTED" in f.statement]
    return {"requests": len(build_requests(g)), "honest_conflicts": honest_n, "fabricated": injected_total,
            "fabricated_rejected": len(rejected), "fabricated_shipped": len(fabricated_shipped),
            "honest_corroborated": sum(1 for f in out.result.findings if "Corroborated by llm:mock-adversarial" in f.rationale),
            "catch_rate": round(len(rejected) / injected_total, 3) if injected_total else None,
            "unsupported_injected": len(build_requests(g)), "unsupported_shipped": len(unsupported_shipped),
            "unsupported_tier": sorted({f.tier for f in unsupported_shipped}),
            "llm_stats": {k: v for k, v in st.items() if k.startswith("llm")},
            "rejection_reasons": sorted({f.rationale.split("REJECTED by evidence gate: ")[-1][:90] for f in rejected})[:6]}


DEFAULT_SPLITS = {
    "dev": (range(0, 1), False),         # built and debugged against this one
    "test": (range(1, 21), False),       # first-run scores recorded, then used for error analysis
    "holdout": (range(21, 41), False),   # never inspected before the final run
    "clean": (range(1, 6), True),        # negative controls: zero seeded defects
}


def run_eval(data_dir: Path, out_dir: Path, splits: dict | None = None, dev_seed: int = 0) -> dict:
    splits = splits or DEFAULT_SPLITS
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {k: {} for k in splits}
    timings = []
    for split, (seeds, clean) in splits.items():
        for s in seeds:
            pdir = generate(s, data_dir, clean=clean)
            key = json.loads((pdir / "answer_key.json").read_text(encoding="utf-8"))
            t0 = time.perf_counter()
            o = run(Inputs.discover(pdir))
            timings.append(time.perf_counter() - t0)
            sc = score_project(o.result.findings, key)
            sc["gate"] = {k: o.result.stats.get(k) for k in ("anchors_checked", "anchors_verified", "rejected_by_gate")}
            results[split][pdir.name] = sc

    def agg(split):
        rs = results[split].values()
        tot = {k: sum(r[k] for r in rs) for k in ("shipped", "tp", "defects", "detected")}
        fp = sum(len(r["fp"]) for r in rs)
        p, r_, f1 = _prf(tot["tp"], fp, tot["detected"], tot["defects"])
        per_type = {}
        for t in TYPES:
            tp = sum(r["per_type"].get(t, {}).get("tp", 0) for r in rs)
            fpt = sum(r["per_type"].get(t, {}).get("fp", 0) for r in rs)
            dd = sum(r["per_type"].get(t, {}).get("defects", 0) for r in rs)
            de = sum(r["per_type"].get(t, {}).get("detected", 0) for r in rs)
            per_type[t] = dict(zip(("precision", "recall", "f1"), _prf(tp, fpt, de, dd))) | {"defects": dd, "detected": de, "fp": fpt}
        tiers = {t: {"n": sum(r["by_tier"][t]["n"] for r in rs), "tp": sum(r["by_tier"][t]["tp"] for r in rs)} for t in ("confirmed", "probable")}
        for t in tiers.values():
            t["precision"] = round(t["tp"] / t["n"], 3) if t["n"] else None
        loc = {k: sum(r["localisation"][k] for r in rs) for k in ("detected_with_gt", "localised")}
        gate = {k: sum(r["gate"][k] or 0 for r in rs) for k in ("anchors_checked", "anchors_verified", "rejected_by_gate")}
        nr = {k: sum(r["needs_review"][k] for r in rs) for k in ("n", "on_trap", "on_defect")}
        return {"projects": len(results[split]), **tot, "fp": fp, "precision": p, "recall": r_, "f1": f1,
                "per_type": per_type, "tiers": tiers, "localisation": loc,
                "localisation_rate": round(loc["localised"] / loc["detected_with_gt"], 3) if loc["detected_with_gt"] else None,
                "gate": gate, "needs_review": nr,
                "trap_violations": sum(len(r["trap_violations"]) for r in rs),
                "missed": [m for k, r in results[split].items() for m in [f"{k}: {x}" for x in r["missed"]]],
                "fp_list": [m for k, r in results[split].items() for m in [f"{k}: {x}" for x in r["fp"]]]}

    summary = {k: agg(k) for k in splits}
    # determinism
    d0 = data_dir / f"seed_{dev_seed:02d}"
    a = run(Inputs.discover(d0)).result
    b = run(Inputs.discover(d0)).result
    dump = lambda r: json.dumps([f.model_dump() for f in r.findings], sort_keys=True)
    summary["determinism"] = {"runs": 2, "identical": dump(a) == dump(b), "findings": len(a.findings)}
    summary["hallucination_injection"] = hallucination_injection(d0)
    summary["timing"] = {"sets": len(timings), "mean_seconds": round(sum(timings) / len(timings), 2),
                         "max_seconds": round(max(timings), 2)}
    (out_dir / "results.json").write_text(json.dumps({"summary": summary, "per_project": results}, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render_report(summary), encoding="utf-8")
    return summary


def render_report(s: dict) -> str:
    L = ["# Evaluation report", "",
         "All documents are synthetic (fictional project). Seed 0 = development set (all 24 defect kinds, used while "
         "building the rules). Seeds 1-20 = test sets generated with randomised defects, targets, numbering and bay sizes "
         "(same generator family, so this measures robustness to variation, not to unseen drafting styles). "
         "Clean sets = negative controls with zero seeded defects.", ""]
    splits = [k for k in ("dev", "test", "holdout", "clean") if k in s]
    L += ["## Headline", "", "| Split | Sets | Seeded defects | Detected | Shipped findings | False positives | Precision | Recall | F1 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k in splits:
        a = s[k]
        L.append(f"| {k} | {a['projects']} | {a['defects']} | {a['detected']} | {a['shipped']} | {a['fp']} | "
                 f"{a['precision']:.3f} | {a['recall'] if a['defects'] else '-'} | {a['f1'] if a['defects'] else '-'} |")
    main = "holdout" if "holdout" in s else "test"
    t = s[main]
    L += ["", f"## {main.capitalize()} split by finding type", "", "| Type | Defects | Detected | Recall | FP | Precision |", "|---|---|---|---|---|---|"]
    for ty, m in t["per_type"].items():
        L.append(f"| {ty} | {m['defects']} | {m['detected']} | {m['recall']:.3f} | {m['fp']} | {m['precision']:.3f} |")
    L += ["", f"## Calibration by tier ({main} split)", "", "| Tier | Findings | Correct | Precision |", "|---|---|---|---|"]
    for tier, m in t["tiers"].items():
        L.append(f"| {tier} | {m['n']} | {m['tp']} | {m['precision']} |")
    L += ["", "## Evidence and hallucination controls", "",
          f"- Evidence localisation ({main}): {t['localisation']['localised']}/{t['localisation']['detected_with_gt']} detected defects "
          f"have an evidence anchor on the ground-truth location ({t['localisation_rate']}).",
          f"- Citation verification (all splits): every shipped finding carries only re-verified anchors; anchors checked "
          f"{sum(s[k]['gate']['anchors_checked'] for k in splits)}, verified "
          f"{sum(s[k]['gate']['anchors_verified'] for k in splits)}, findings rejected by the gate "
          f"{sum(s[k]['gate']['rejected_by_gate'] for k in splits)}.",
          f"- Negative controls: {s['clean']['shipped']} shipped findings on {s['clean']['projects']} clean sets "
          f"(every one would be a false positive).",
          f"- Abstentions (needs_review, {main}): {t['needs_review']['n']} items, {t['needs_review']['on_trap']} on deliberate "
          f"ambiguity traps ('TYP.' without a count). Trap violations (confident claims on traps): {t['trap_violations']}.",
          f"- Determinism: {s['determinism']['runs']} runs on the dev set, identical output = {s['determinism']['identical']}.",
          ]
    h = s["hallucination_injection"]
    L += [f"- Hallucination injection (mock LLM on dev set): {h['fabricated']} fabricated conflicts injected across "
          f"{h['requests']} spec-section requests; {h['fabricated_rejected']} stopped by the evidence gate, "
          f"{h['fabricated_shipped']} shipped (catch rate {h['catch_rate']}). {h['honest_corroborated']}/{h['honest_conflicts']} "
          f"correct conflicts passed and corroborated the rule findings.",
          f"- Known limit, measured: {h['unsupported_injected']} *real* quotes attached to *false* claims were also injected; "
          f"{h['unsupported_shipped']} passed the gate (as tier {', '.join(h['unsupported_tier']) or '-'}). The gate proves a citation "
          f"exists where cited; it cannot prove the citation supports the claim. That is why LLM findings are never 'confirmed' "
          f"and are routed to an engineer, and why the reviewer reject rate is tracked in production.", "",
          f"Mean run time per set: {s['timing']['mean_seconds']} s (max {s['timing']['max_seconds']} s, {s['timing']['sets']} sets).", ""]
    for k in splits:
        if s[k]["missed"]:
            L += [f"## Missed defects ({k})", ""] + [f"- {m}" for m in s[k]["missed"]] + [""]
        if s[k]["fp_list"]:
            L += [f"## False positives ({k})", ""] + [f"- {m}" for m in s[k]["fp_list"]] + [""]
    return "\n".join(L)
