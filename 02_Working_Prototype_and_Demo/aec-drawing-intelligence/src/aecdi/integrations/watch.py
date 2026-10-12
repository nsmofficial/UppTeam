"""Folder watch: run the pipeline whenever a project folder gets a new or changed revision.

    aecdi watch <inbox> --out <out_root> [--once] [--interval 60] [--notify-url URL] [--json]

<inbox> holds one sub-folder per project (or is itself a project folder) synced from ACC Docs,
Dropbox or Google Drive. A project is (re)analysed when the names, sizes or timestamps of its
input files change. Each run writes the normal outputs to <out_root>/<project>/ plus summary.json,
and appends a line to <out_root>/runs.jsonl. With --notify-url the summary is POSTed as JSON
(e.g. to an n8n Webhook node or a Teams/Slack incoming webhook).
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

INPUT_SUFFIXES = {".pdf", ".xlsx", ".txt", ".csv"}


def input_fingerprint(folder: Path) -> str:
    h = hashlib.sha1()
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in INPUT_SUFFIXES:
            st = p.stat()
            h.update(f"{p.name}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()[:16]


def project_folders(inbox: Path) -> list[Path]:
    def is_project(d: Path) -> bool:
        return any("revb" in p.name.lower().replace("_", "").replace("-", "") for p in d.glob("*.pdf"))
    if is_project(inbox):
        return [inbox]
    return [d for d in sorted(inbox.iterdir()) if d.is_dir() and is_project(d)]


def _notify(url: str, payload: dict):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def scan_once(inbox: Path, out_root: Path, notify_url: str | None = None, llm_client=None) -> list[dict]:
    from ..outputs import write_all
    from ..pipeline import Inputs, run

    out_root.mkdir(parents=True, exist_ok=True)
    state_path = out_root / "watch_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    summaries = []
    for folder in project_folders(inbox):
        fp = input_fingerprint(folder)
        if state.get(str(folder)) == fp:
            continue
        out = out_root / folder.name
        try:
            o = run(Inputs.discover(folder), out, llm_client=llm_client)
            write_all(o, out)
            st = o.result.stats
            fs = o.result.findings
            summary = {"project": folder.name, "at": datetime.now().isoformat(timespec="seconds"), "status": "ok",
                       "findings": st["findings"], "needs_review": st["needs_review"],
                       "high": sum(1 for f in fs if f.severity == "high" and f.tier != "needs_review"),
                       "confirmed": sum(1 for f in fs if f.tier == "confirmed"),
                       "rejected_by_gate": st["rejected_by_gate"], "unreadable_pages": st.get("unreadable_pages", 0),
                       "markups_not_incorporated": st.get("markups_not_incorporated", 0),
                       "issue_log": str(out / "QC_Issue_Log.xlsx"), "review_pdf": str(out / f"{o.inputs.rev_b.stem}_REVIEW.pdf"),
                       "seconds": st["seconds"]}
        except Exception as e:  # report the failure, keep watching the other projects
            summary = {"project": folder.name, "at": datetime.now().isoformat(timespec="seconds"),
                       "status": "error", "error": f"{type(e).__name__}: {e}"}
        (out_root / folder.name).mkdir(parents=True, exist_ok=True)
        (out_root / folder.name / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        with (out_root / "runs.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary) + "\n")
        if summary["status"] == "ok":
            state[str(folder)] = fp
        if notify_url:
            try:
                _notify(notify_url, summary)
                summary["notified"] = True
            except Exception as e:
                summary["notified"] = f"failed: {e}"
        summaries.append(summary)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return summaries


def watch(inbox: Path, out_root: Path, interval: float = 60, notify_url: str | None = None, once: bool = False,
          llm_client=None, on_summary=print):
    while True:
        for s in scan_once(inbox, out_root, notify_url, llm_client):
            on_summary(s)
        if once:
            return
        time.sleep(interval)
