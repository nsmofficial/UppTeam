# aec-drawing-intelligence

Evidence-linked discrepancy detection across construction drawings, specifications, BOQs and Revit model exports.

**Extract and structure → deterministic rules → LLM only where judgment is needed → every citation re-verified → the engineer decides.**

All sample data is synthetic (a fictional clinic project). No client data is included.

## Quick start

```bash
./run_demo.sh            # macOS / Linux / Git Bash: venv, install, 35 tests, analyse sample_project
```

```bat
..\RUN.bat               # Windows: one-click setup, 35 tests, analyse sample_project, launch UI
```

Then open the review screen:

```bash
streamlit run ui/review_app.py -- out
```

## What goes in

Put these files in one project folder; `aecdi run <folder>` finds them by name.

| File | Required | Used for |
|---|---|---|
| `*RevB*.pdf` | yes | Current drawing set (vector PDF from Revit/AutoCAD) |
| `*RevA*.pdf` | no | Previous revision: revision comparison and cloud checks |
| `*Manual*.pdf` / `*Spec*.pdf` | no | Project manual (CSI sections) |
| `*.xlsx` | no | Bill of quantities |
| `*REDLINES*.pdf` | no | Reviewer markups on the previous revision: redline closure check |
| `*Schedule*.txt` / `.csv` | no | Schedule exported from the Revit model: sheet-vs-model check |

## What comes out (`out/`)

- `QC_Issue_Log.xlsx`
- `*_REVIEW.pdf`: markups readable in Bluebeam Revu and Acrobat
- `findings.json`
- `acc_issues.json`
- `markup_closure.json`
- `revision_delta.json`
- `project_graph.json`
- `overlays/`
- `sources/`

## Commands

| Command | Purpose |
|---|---|
| `aecdi run <folder> --out <dir>` | Analyse a project (`--llm anthropic` adds the Claude spec check; needs an API key) |
| `aecdi review <out>` | Review screen: evidence crops, accept/reject with reason, audit log |
| `aecdi watch <inbox> --out <dir> [--notify-url URL]` | Re-run automatically when files change; post a summary to n8n / Teams / Slack |
| `aecdi acc-post <out> --project <id> --subtype <id> [--live]` | Post engineer-accepted findings to Autodesk Construction Cloud (dry run by default) |
| `aecdi feedback <out> <folder>` / `aecdi regress` | Turn review decisions into regression cases and re-check them |
| `aecdi score-qclog <findings.json> <qc_log.csv>` | Pilot: compare against a real QC log (template in `eval_templates/`) |
| `aecdi llm-eval --client mock\|anthropic` | Precision, recall and run-to-run consistency of the LLM check |
| `aecdi eval` | Synthetic benchmark: dev, test, holdout, metric and clean splits |
| `aecdi generate --seed N [--metric] [--clean]` | Write a synthetic project with an answer key |

Run commands as `python -m aecdi.cli ...` with `PYTHONPATH=src`, or `pip install -e .` to get the `aecdi` command.

## Checks (32 rule IDs)

- **Dimensions:** chain vs overall; text vs scaled length; same grid span across sheets (imperial and metric).
- **Quantities:**
  - plan, schedule and BOQ counts
  - `TYP. OF n`
  - `TYP.` with no count → needs review
  - NIC items priced
- **Completeness:**
  - undefined, orphan and duplicate tags
  - door swings without tags
  - blank fields
  - undefined hardware sets
  - missing spec sections
  - missing or unindexed sheets
  - scanned pages (abstain)
- **Cross-discipline:** voltage, missing circuit, breaker smaller than MCA, equipment weight vs structural design weight.
- **Spec patterns:** material, fire rating, refrigerant. The optional LLM check covers the rest.
- **Revisions:** unclouded changes; revision not issued in the title block; reviewer redlines not incorporated.
- **Model:** issued schedule vs Revit export.

## Limits

- Scanned sheets are detected and skipped, not OCR'd.
- Symbols are recognised only for door swings.
- The live Claude path is wired and tested against a stand-in API, but has not been run against the real API.
- ACC posting is tested against a mock server, not a live ACC project.
- Benchmark results are on synthetic data from the same author; real-world accuracy is measured in the pilot.
