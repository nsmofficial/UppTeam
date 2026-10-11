"""Command line.

  aecdi demo                         generate the dev set, run it, write all outputs, run the evaluation
  aecdi generate --seed 3 [--clean]  write a synthetic project to data/synthetic/
  aecdi run <folder> [--llm off|anthropic|replay] [--record]   analyse a folder (RevA/RevB PDFs, manual, BOQ)
  aecdi eval                         full evaluation (dev + 20 test seeds + 5 negative controls)
  aecdi review [<out folder>]        open the Streamlit review screen
"""
from __future__ import annotations

import argparse
import json
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
          f"{s['revision_changes']} revision changes, {s['seconds']} s -> {out}")
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aecdi", description="AEC drawing intelligence prototype")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--clean", action="store_true")
    g.add_argument("--out", type=Path, default=ROOT / "data" / "synthetic")
    r = sub.add_parser("run")
    r.add_argument("folder", type=Path)
    r.add_argument("--out", type=Path)
    r.add_argument("--llm", choices=["off", "anthropic", "replay"], default="off")
    r.add_argument("--record", action="store_true", help="save live LLM responses for replay")
    sub.add_parser("eval")
    sub.add_parser("demo")
    v = sub.add_parser("review")
    v.add_argument("out", nargs="?", type=Path, default=ROOT / "out" / "seed_00")
    a = ap.parse_args(argv)

    if a.cmd == "generate":
        from .synth.render import generate
        print(generate(a.seed, a.out, clean=a.clean))
    elif a.cmd == "run":
        cmd_run(a.folder, a.out or ROOT / "out" / a.folder.name, a.llm, a.record)
    elif a.cmd in ("eval", "demo"):
        from .evaluation import run_eval
        from .synth.render import generate
        data = ROOT / "data" / "synthetic"
        if a.cmd == "demo":
            cmd_run(generate(0, data), ROOT / "out" / "seed_00")
        s = run_eval(data, ROOT / "eval")
        for k in ("dev", "test", "holdout", "clean"):
            x = s[k]
            print(f"{k:5s}: sets={x['projects']:2d} defects={x['defects']:3d} detected={x['detected']:3d} "
                  f"shipped={x['shipped']:3d} fp={x['fp']:2d} precision={x['precision']:.3f} recall={x['recall']:.3f}")
        h = s["hallucination_injection"]
        print(f"hallucination injection: {h['fabricated_rejected']}/{h['fabricated']} fabricated conflicts stopped; "
              f"determinism identical={s['determinism']['identical']}; report -> {ROOT / 'eval' / 'report.md'}")
    elif a.cmd == "review":
        app = ROOT / "ui" / "review_app.py"
        sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), "--", str(a.out)]))


if __name__ == "__main__":
    main()
