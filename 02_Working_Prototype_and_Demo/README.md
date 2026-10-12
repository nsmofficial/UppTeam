# AEC Drawing Intelligence – Working Prototype

A system that checks a construction document set for discrepancies between drawings, specifications, the bill of quantities, reviewer redlines and the BIM model. Every finding points to the exact place in its source document, and an engineer accepts or rejects it.

All sample documents are synthetic (a fictional 7-sheet clinic project). No real project data is included.

```
02_Working_Prototype_and_Demo/
├── RUN.bat                     one-click setup and run (Windows)
├── README.md                   this file
└── aec-drawing-intelligence/   the complete system: source, tests, sample project, review screen
```

---

## 1. Run with the batch file (Windows 10 / 11)

1. Double-click **`RUN.bat`**.
2. Wait. The first run takes about 2–5 minutes and needs an internet connection; later runs take seconds.
3. Your browser opens the review screen at `http://localhost:8501`, and the output folder opens in Explorer.
4. To stop, close the black console window, or press `Ctrl+C` in it.

**What `RUN.bat` does:**

| Step | What happens |
|---|---|
| 1. Python | Uses Python 3.12–3.14 if the PC has it. If not, it downloads a private portable Python 3.12 into `aec-drawing-intelligence\.runtime`. No admin rights are needed and nothing is installed system-wide. |
| 2. Packages | Installs the exact tested package versions (`requirements.txt`). Details go to `setup_log.txt`. |
| 3. Tests | Runs the 35 automated tests. Results go to `test_log.txt`. |
| 4. Analysis | Analyses `sample_project` and writes the results to `aec-drawing-intelligence\out`. |
| 5. Review screen | Starts the review screen and opens it in the browser. |

**Options** (run from a command prompt in this folder):
- `RUN.bat eval`: also runs the full synthetic benchmark (about 3 minutes).
- `RUN.bat nobrowser`: setup, tests and analysis only.

Tested on Windows 11 in both cases: with Python already installed, and with no Python at all (the portable Python is downloaded).

---

## 2. Run without the batch file

Requires Python 3.12, 3.13 or 3.14 and an internet connection for the first install.

**Windows (Command Prompt):**

```bat
cd aec-drawing-intelligence
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set PYTHONPATH=src
python -m unittest discover -s tests -p "test_*.py"
python -m aecdi.cli run sample_project --out out
python -m streamlit run ui\review_app.py -- out
```

**macOS / Linux:**

```bash
cd aec-drawing-intelligence
./run_demo.sh                                   # venv, install, tests, analysis
source .venv/bin/activate
export PYTHONPATH=src
python -m streamlit run ui/review_app.py -- out
```

Open `http://localhost:8501` if the browser does not open by itself.

---

## 3. How the system works

| Step | What happens |
|---|---|
| Inputs | Drawing set (current and previous revision, vector PDF), reviewer redlines on the previous revision, project manual, bill of quantities (Excel), schedule exported from the BIM model |
| 1. Ingest | Reads title blocks, text with exact coordinates, schedules as tables, grids, dimensions, revision clouds and door swings; splits the specification into paragraphs; reads BOQ cells and model rows. Scanned pages are detected and set aside for review. |
| 2. Link | Builds a project graph: tag ↔ schedule row ↔ spec section ↔ BOQ item ↔ electrical circuit ↔ sheet. Every fact keeps where it came from. |
| 3. Check | 32 deterministic rules: dimensions, quantities, missing information, cross-discipline conflicts (power, breakers, structural loads), spec conflicts, unclouded revisions, redlines not incorporated, model vs issued sheet. An optional AI check compares specification wording with schedules. |
| 4. Verify | The evidence gate re-finds every cited value in its source file. Anything it cannot verify is not shown. |
| 5. Decide | The engineer reviews each finding with its evidence and accepts or rejects it. Only accepted findings are sent on to the issue tracker. |

Findings come in three tiers:
- **Confirmed:** a rule on clear data.
- **Probable:** depends on interpretation.
- **Needs review:** the system abstains, for example a tag marked "TYP." with no count.

---

## 4. How to use it

**The review screen** (opens in the browser):

| Tab | Use |
|---|---|
| Findings | Filter by tier, severity, type, discipline or status. Click a finding to see its evidence cropped from the drawing, specification, BOQ or model export, then **Accept**, **Reject** (with a reason) or **Comment**. Every decision is saved in `out\review_log.jsonl`. |
| Revision delta | Every change between revisions, whether it was clouded, and visual overlays. |
| Redline closure | Each reviewer markup on the previous revision, and whether the new revision addresses it. |
| Blocked by evidence gate | Anything the system proposed but could not prove. |
| ACC issues | What would be posted to the issue tracker (accepted findings only). |
| Evaluation, Exports | The benchmark report; download the outputs. |

**Output files** (`aec-drawing-intelligence\out`):

| File | Contents |
|---|---|
| `QC_Issue_Log.xlsx` | All findings as an Excel QC log |
| `CD_Set_RevB_REVIEW.pdf` | The drawing set with every finding marked up; opens in Bluebeam or Acrobat |
| `markup_closure.json` | Redline status |
| `acc_issues.json` | Issue-tracker payloads |
| `findings.json` | Everything, machine-readable |

**Run it on your own project:** put the files in one folder, named so the system can recognise them:

| File | Name pattern | Required |
|---|---|---|
| Current drawing set | `*RevB*.pdf` | Yes |
| Previous drawing set | `*RevA*.pdf` | No |
| Project manual | `*Manual*.pdf` or `*Spec*.pdf` | No |
| Bill of quantities | `*.xlsx` | No |
| Reviewer markups | `*REDLINES*.pdf` | No |
| Model schedule export | `*Schedule*.txt` | No |

Then run:

```bat
cd aec-drawing-intelligence
set PYTHONPATH=src
.venv\Scripts\python -m aecdi.cli run "C:\path\to\project" --out "C:\path\to\results"
.venv\Scripts\python -m streamlit run ui\review_app.py -- "C:\path\to\results"
```

If `RUN.bat` installed the portable Python, use `.runtime\python\python.exe` instead of `.venv\Scripts\python`; `PYTHONPATH` is then not needed.

**Other commands** (same Python, `-m aecdi.cli <command>`):

| Command | Purpose |
|---|---|
| `watch <inbox> --out <dir>` | Re-run automatically whenever a project's files change |
| `acc-post <out> --project <id> --subtype <id>` | Post accepted findings to the issue tracker (dry run unless `--live`) |
| `feedback <out> <project>` then `regress` | Turn review decisions into regression tests and re-check them |
| `score-qclog <findings.json> <qc_log.csv>` | Compare results with a real QC log |
| `eval` | Full synthetic benchmark |

The technical reference is `aec-drawing-intelligence\README.md`.

---

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| "Could not download Python" or packages fail | Check the internet connection or proxy; details are in `aec-drawing-intelligence\setup_log.txt`. Run `RUN.bat` again; finished steps are skipped. |
| Windows SmartScreen warns about `RUN.bat` | Click *More info* → *Run anyway*. The file is plain text and can be opened in Notepad to inspect. |
| Port 8501 is already in use | Close the other program, or run `set AECDI_PORT=8502` and then `RUN.bat` in the same command prompt. |
| Start again from scratch | Delete `aec-drawing-intelligence\.venv` and `aec-drawing-intelligence\.runtime`, then run `RUN.bat`. |
