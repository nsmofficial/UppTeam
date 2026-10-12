"""Command line.

  aecdi run <folder> [--out DIR] [--llm off|anthropic|replay] [--record]   analyse one project folder
  aecdi review [<out>]                         Streamlit review screen
  aecdi watch <inbox> --out DIR [--once] [--interval S] [--notify-url URL] [--json]
  aecdi acc-post <out> --project ID [--subtype ID] [--token-env APS_TOKEN] [--policy accepted] [--live]
  aecdi feedback <out> <project folder>        turn review decisions into regression cases
  aecdi regress [regression/cases.jsonl]       re-check every regression case
  aecdi score-qclog <findings.json> <qc_log.csv> [--out qc_match.xlsx]   pilot: compare with a real QC log
  aecdi llm-eval [--client mock|anthropic] [--runs 3] [--seeds 0,1,2]    LLM check precision/recall/consistency
  aecdi generate --seed N [--clean] [--metric]  write a synthetic project
  aecdi eval                                   full synthetic benchmark
  aecdi demo                                   regenerate sample, run it, run the benchmark
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _client(mode: str, record: bool, cache: Path):
    if mode == "off":
        return None
    from .llm.semantic import AnthropicClient, RecordingClient, ReplayClient

    if mode == "replay":
        return ReplayClient(cache)
    client = AnthropicClient()
    return RecordingClient(client, cache) if record else client


def cmd_run(folder: Path, out: Path, llm: str = "off", record: bool = False) -> dict:
    from .outputs import write_all
    from .pipeline import Inputs, run

    out.mkdir(parents=True, exist_ok=True)
    o = run(Inputs.discover(folder), out, llm_client=_client(llm, record, ROOT / "data" / "llm_cache"))
    write_all(o, out)
    s = o.result.stats
    print(f"{o.result.project}: {s['findings']} findings ({s['needs_review']} needs review), "
          f"{s['rejected_by_gate']} rejected by evidence gate, {s['anchors_verified']}/{s['anchors_checked']} anchors verified, "
          f"{s['revision_changes']} revision changes, {s.get('markups', 0)} redline markups "
          f"({s.get('markups_not_incorporated', 0)} not incorporated), {s['seconds']} s -> {out}")
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aecdi", description="AEC drawing intelligence prototype")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--clean", action="store_true")
    g.add_argument("--metric", action="store_true")
    g.add_argument("--out", type=Path, default=ROOT / "data" / "synthetic")
    r = sub.add_parser("run")
    r.add_argument("folder", type=Path)
    r.add_argument("--out", type=Path)
    r.add_argument("--llm", choices=["off", "anthropic", "replay"], default="off")
    r.add_argument("--record", action="store_true", help="save live LLM responses for replay")
    sub.add_parser("eval")
    sub.add_parser("demo")
    v = sub.add_parser("review")
    v.add_argument("out", nargs="?", type=Path, default=ROOT / "out")
    w = sub.add_parser("watch")
    w.add_argument("inbox", type=Path)
    w.add_argument("--out", type=Path, required=True)
    w.add_argument("--once", action="store_true")
    w.add_argument("--interval", type=float, default=60)
    w.add_argument("--notify-url")
    w.add_argument("--json", action="store_true", help="print one JSON object per analysed project")
    a = sub.add_parser("acc-post")
    a.add_argument("out", type=Path)
    a.add_argument("--project", required=True, help="ACC project id (with or without the 'b.' prefix)")
    a.add_argument("--subtype", default=os.environ.get("ACC_ISSUE_SUBTYPE_ID", "<ACC issue subtype id>"))
    a.add_argument("--token-env", default="APS_TOKEN", help="environment variable holding a 3-legged token")
    a.add_argument("--policy", choices=["accepted", "accepted+confirmed-draft"], default="accepted")
    a.add_argument("--base-url", default="https://developer.api.autodesk.com")
    a.add_argument("--live", action="store_true", help="actually POST (default is a dry run)")
    fb = sub.add_parser("feedback")
    fb.add_argument("out", type=Path)
    fb.add_argument("project", type=Path)
    fb.add_argument("--cases", type=Path, default=ROOT / "regression" / "cases.jsonl")
    rg = sub.add_parser("regress")
    rg.add_argument("cases", nargs="?", type=Path, default=ROOT / "regression" / "cases.jsonl")
    q = sub.add_parser("score-qclog")
    q.add_argument("findings", type=Path)
    q.add_argument("qc_log", type=Path)
    q.add_argument("--out", type=Path, default=Path("qc_match.xlsx"))
    le = sub.add_parser("llm-eval")
    le.add_argument("--client", choices=["mock", "anthropic"], default="mock")
    le.add_argument("--runs", type=int, default=3)
    le.add_argument("--seeds", default="0,1,2,3,4")
    le.add_argument("--noise", type=float, default=0.0, help="mock only: random error rate")
    args = ap.parse_args(argv)

    if args.cmd == "generate":
        from .synth.render import generate
        print(generate(args.seed, args.out, clean=args.clean, units="metric" if args.metric else "imperial"))
    elif args.cmd == "run":
        cmd_run(args.folder, args.out or ROOT / "out" / args.folder.name, args.llm, args.record)
    elif args.cmd in ("eval", "demo"):
        from .evaluation import run_eval
        from .synth.render import generate
        data = ROOT / "data" / "synthetic"
        if args.cmd == "demo":
            cmd_run(generate(0, data), ROOT / "out")
        s = run_eval(data, ROOT / "eval")
        for k in ("dev", "test", "holdout", "metric", "clean"):
            x = s[k]
            print(f"{k:7s}: sets={x['projects']:2d} defects={x['defects']:3d} detected={x['detected']:3d} "
                  f"shipped={x['shipped']:3d} fp={x['fp']:2d} precision={x['precision']:.3f} recall={x['recall']:.3f}")
        h = s["hallucination_injection"]
        print(f"hallucination injection: {h['fabricated_rejected']}/{h['fabricated']} fabricated conflicts stopped; "
              f"determinism identical={s['determinism']['identical']}; report -> {ROOT / 'eval' / 'report.md'}")
    elif args.cmd == "review":
        app = ROOT / "ui" / "review_app.py"
        sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), "--", str(args.out)]))
    elif args.cmd == "watch":
        from .integrations.watch import watch
        printer = (lambda s: print(json.dumps(s), flush=True)) if args.json else \
            (lambda s: print(f"{s['project']}: {s['status']} {s.get('findings', '')} findings "
                             f"({s.get('high', '')} high) {s.get('error', '')}", flush=True))
        watch(args.inbox, args.out, args.interval, args.notify_url, args.once, on_summary=printer)
    elif args.cmd == "acc-post":
        from .integrations.acc import load_review_log, payloads, post_issues
        from .models import RunResult
        result = RunResult.model_validate_json((args.out / "findings.json").read_text(encoding="utf-8"))
        items = payloads(result.findings, load_review_log(args.out), args.subtype, args.policy)
        token = os.environ.get(args.token_env, "")
        if args.live and not token:
            sys.exit(f"--live needs a 3-legged APS token in ${args.token_env}")
        for res in post_issues(items, args.project, token, args.out, args.base_url, dry_run=not args.live):
            print(json.dumps(res))
        print(f"{len(items)} issue(s) selected by policy '{args.policy}'" + ("" if args.live else " (dry run)"))
    elif args.cmd == "feedback":
        from .feedback import build_cases, save_cases
        cases = build_cases(args.out, args.project)
        total = save_cases(cases, args.cases)
        print(f"{len(cases)} case(s) from this review; {total} in {args.cases}")
    elif args.cmd == "regress":
        from .feedback import regress
        rep = regress(args.cases)
        for c in rep["cases"]:
            print(f"{c['status']:45s} {c['method']:16s} {c['statement'][:80]}")
        print(json.dumps(rep["summary"]))
        if rep["summary"]["regressions"]:
            sys.exit(1)
    elif args.cmd == "score-qclog":
        from .qclog import score_qc_log
        print(json.dumps(score_qc_log(args.findings, args.qc_log, args.out), indent=2))
    elif args.cmd == "llm-eval":
        from .llm_eval import evaluate, labelled_projects, oracle_mock
        from .synth.render import generate
        data = ROOT / "data" / "synthetic"
        projects = labelled_projects([generate(int(s), data) for s in args.seeds.split(",")])
        if args.client == "mock":
            client = oracle_mock(projects, args.noise)
        else:
            from .llm.semantic import AnthropicClient
            client = AnthropicClient()
        print(json.dumps(evaluate(projects, client, args.runs), indent=2))


if __name__ == "__main__":
    main()
