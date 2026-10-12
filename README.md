# Challenge 1 — AI-Powered AEC Drawing Intelligence

**Candidate:** Sahil Navadiya | **Role:** AI Process Optimization Lead (Construction & Architecture)  
**Organization:** Uppteam / ISP Global Consulting Pvt. Ltd. | **Version:** 1.2

---

## 1. Project Overview & Core Understanding

AEC coordination errors happen *across* documents—when a floor-plan tag, a schedule row, a CSI specification section, an Excel BOQ item, an electrical panel circuit, a client redline markup, or the native Revit model disagree.

Connecting a raw LLM directly to drawing PDFs fails in engineering workflows because LLMs misread dense tables, make arithmetic errors on architectural fractions (`24'-6 1/2"`), and hallucinate citations.

### Core Design Principle
```text
Extract & Structure  →  Project Graph  →  32 Deterministic Rules (+ Optional LLM)  →  Evidence Gate  →  Engineer Decides
```

| Principle | Implementation |
|---|---|
| **Structure before AI** | Vector PDF text/tables/geometry (`PyMuPDF`), CSI spec hierarchy, Excel BOQ cells (`openpyxl`), and Revit schedule exports parsed with exact coordinates. |
| **Rules first, LLM second** | **32 deterministic rules** handle dimension arithmetic, tag counts, breaker/load checks, and revision diffs; **optional Claude Opus 5.5** checks only spec-vs-schedule wording. |
| **Zero-hallucination gate** | Independent **Evidence Gate** re-opens source PDFs, BOQs, and model exports to verify every cited snippet at its exact bounding box (`[x0, y0, x1, y1]`) or cell before any finding ships. |
| **Calibrated uncertainty** | Findings are tiered into **Confirmed** (deterministic), **Probable** (interpretive / LLM, capped at `≤ 0.85`), and **Needs Review** (abstention on bare `TYP.` or scanned/raster sheets). |
| **Engineering accountability** | The tool flags *potential discrepancies*; the Engineer of Record decides (**Accept / Reject / Comment**) in an append-only audit log (`review_log.jsonl`). |

---

## 2. Repository Structure

```text
UppTeam/
├── README.md                                           # Master overview & deliverable index
├── 01_System_Architecture_and_Tech_Stack/
│   ├── System_Architecture.pdf                         # 1-page end-to-end architecture & data-flow diagram
│   └── Technology_Stack.pdf                            # 1-page prototype vs. production stack comparison
├── 02_Working_Prototype_and_Demo/
│   ├── RUN.bat                                         # One-click Windows launcher (setup, 35 tests, run, UI)
│   ├── README.md                                       # Prototype quick-start & command guide
│   └── aec-drawing-intelligence/                       # Python package (src/aecdi, tests, sample_project, ui, n8n, out)
├── 03_Evaluation_Plan_and_Hallucination_Detection/
│   ├── Evaluation_Plan.pdf                             # 1-page 6-layer evaluation plan, 76-set results & pilot protocol
│   ├── Hallucination_Detection.pdf                     # 1-page 6 anti-hallucination controls & adversarial test results
│   └── benchmark_data/                                 # Raw v1.2 benchmark report.md and results.json
└── 04_Roadmap_Cost_and_ROI/
    ├── Roadmap_and_Costing.pdf                         # 1-page 30-day pilot plan, costs, staffing & NDA sizing
    └── ROI_Analysis.pdf                                # 1-page dual-view ROI scenarios, Second Eye economics & gates
```

---

## 3. All 4 Deliverables in Brief

### Deliverable 01 — System Architecture & Technology Stack
- **Files:** [System_Architecture.pdf](01_System_Architecture_and_Tech_Stack/System_Architecture.pdf) · [Technology_Stack.pdf](01_System_Architecture_and_Tech_Stack/Technology_Stack.pdf)
- **What it covers:**
  - **5-Stage Pipeline:** Multi-format ingestion → Multi-relational Project Graph (`102` typed edges) → 32 deterministic rules + optional LLM semantic check → Independent Evidence Gate → Engineer Review UI & AEC outputs.
  - **Workflow Loop:** Folder watcher / `n8n` triggers analysis on new revisions; reviewer Accept/Reject decisions feed back into fingerprinted CI regression cases (`aecdi feedback` / `aecdi regress`).
  - **Prototype vs. Production Stack:** Maps every prototype module (`PyMuPDF`, `openpyxl`, `Pydantic`, `OpenCV`, `Streamlit`, `JSONL`, `Claude Opus 5.5`) to its production target (`FastAPI` + job queue, commercial `PyMuPDF` + OCR branch, `IfcOpenShell`/pyRevit, `React` + APS Viewer with SSO, `PostgreSQL`, and local GPU fallback for strict-NDA clients).

### Deliverable 02 — Working Prototype & Demo
- **Files:** [RUN.bat](02_Working_Prototype_and_Demo/RUN.bat) · [Prototype Guide](02_Working_Prototype_and_Demo/README.md) · [Source Package](02_Working_Prototype_and_Demo/aec-drawing-intelligence/)
- **What it covers:**
  - **32 Rule IDs across 7 Check Modules:**
    - *Dimensions (`DIM-001`–`003`):* Chained sub-dims vs. overall (`1/8"` tol.), text vs. scaled geometry, cross-sheet grid spans (`A-101` vs. `S-101`), imperial & metric (`mm` @ `1:100`).
    - *Quantities (`QTY-001`–`005`):* Plan tags (`TYP. OF n`) ↔ schedules ↔ Excel BOQ, `NIC` items priced in BOQ, bare `TYP.` abstention.
    - *Completeness (`MISS-001`–`011`, `TAG-001`–`002`, `ING-001`):* Unscheduled/orphan/duplicate tags, untagged door swing arcs, blank cells, undefined hardware sets, missing CSI specs/sheets, raster scan detection.
    - *Cross-Discipline (`XD-001`–`004`):* Mechanical (`M-601`) vs. Electrical (`E-601`) voltage/phase, missing branch circuits, breaker `< MCA`, RTU weight `>` structural limit (`S-101`).
    - *Specifications (`SPEC-001`–`003` + optional `LLM-SEM-*`):* Door material, fire rating, equipment refrigerant, and structured LLM wording comparison.
    - *Revisions & Redlines (`REV-001`–`002`, `MARKUP-001`):* 3-layer structural Rev A → Rev B diff (row-key table diff, layout-shift text compensation, collinear line subtraction), unclouded changes, un-incremented title blocks, and client `*_REDLINES.pdf` closure.
    - *BIM Model vs. Sheet (`NATIVE-001`):* Issued PDF Door Schedule vs. native Revit schedule export (`.txt`/`.csv`).
  - **Sample Project Run (`sample_project/`):** Detects `27/27` seeded defects (`33` total findings: `23` confirmed, `9` probable, `1` needs review), `73/73` anchors verified, `0` false positives in `~1.3 s`.
  - **Outputs & Integrations:** Bluebeam/Acrobat annotated `*_REVIEW.pdf`, styled `QC_Issue_Log.xlsx`, 7-tab `Streamlit` Review UI, Autodesk Construction Cloud (`ACC`) issue exporter (accepted findings only), and 2 tested `n8n` workflows.
  - **Automated Tests:** `35` unit & end-to-end tests (`unittest`), all passing.

### Deliverable 03 — Evaluation Plan & Hallucination Detection
- **Files:** [Evaluation_Plan.pdf](03_Evaluation_Plan_and_Hallucination_Detection/Evaluation_Plan.pdf) · [Hallucination_Detection.pdf](03_Evaluation_Plan_and_Hallucination_Detection/Hallucination_Detection.pdf) · [Benchmark Report](03_Evaluation_Plan_and_Hallucination_Detection/benchmark_data/report.md)
- **What it covers:**
  - **76-Set Synthetic Benchmark (5 Splits):**
    - `dev` (1 set, 27 defects), `test` (40 sets, 560 defects), untouched `holdout` (20 sets, 270 defects), `metric` (10 sets, 143 defects), `clean` negative controls (5 sets, 0 defects).
    - **Score:** `Precision = 1.000`, `Recall = 1.000`, `Severity-Weighted Recall = 1.000`, `0` false positives on holdout (`270/270`) and clean sets (`0/5`), `2,754/2,754` citations verified.
  - **Adversarial Hallucination Tests:**
    - `25/25` injected fabrications (fake quotes, wrong cell values, non-existent tags/paragraphs, altered numbers) **blocked (`100%` catch rate)** by the Evidence Gate.
    - **Measured Limitation:** `5` injected "real verbatim quote + real cell + false conflict claim" cases passed the gate as `Probable` (`0` falsely corroborated rules)—demonstrating why LLM findings are capped at `Probable` and require human acceptance.
  - **Real-Project Pilot Tooling:** Historical QC-log matcher (`aecdi score-qclog` + `eval_templates/qc_log_template.csv`) and multi-run LLM consistency harness (`aecdi llm-eval`).

### Deliverable 04 — 30-Day Roadmap, Costing & ROI Analysis
- **Files:** [Roadmap_and_Costing.pdf](04_Roadmap_Cost_and_ROI/Roadmap_and_Costing.pdf) · [ROI_Analysis.pdf](04_Roadmap_Cost_and_ROI/ROI_Analysis.pdf)
- **What it covers:**
  - **30-Day Pilot Plan:** Week 1 (Baseline QC hours/RFIs & NDA sign-off) → Week 2 (Adapt CAD templates & back-test on 3–5 completed projects via `score-qclog`) → Week 3 (Live shadow pilot on 2 projects) → Week 4 (Calibrate via `feedback`/`regress` & Go/No-Go decision).
  - **Costs (at `₹88/$`):** **`$2,769` one-time pilot cost** (mostly existing staff allocation; `$150` cash cloud/API outlay) and **`$691/month` steady-state running cost** (`$134.50` Cloud + Claude API for 30 sets + `$556.82` for 20% AI Lead & 10% QC Specialist).
  - **Dual-View ROI Model (`30 sets/mo × 12 QC hrs/set = 360 hrs/mo`):**
    - **View A — Internal Cost Savings (`$5.81/hr` India QC CTC):** Break-even requires `~21%` QC time cut; Base Case (`25%` cut / `135 hrs/mo` saved) nets `+$93/mo` (`29.7-month` payback).
    - **View B — Redeployed Billable Capacity (`$22/hr` rate):** When freed QC hours handle additional fixed-fee AOP sets or billable work, Base Case nets **`+$2,279/mo`** (**`1.2-month` payback**, **`887%` Year-1 ROI**).
    - **Second Eye QC Upside:** `$300/set` price vs. `$156.87/set` full cost = **`$143.13/set` (`48%` margin)**, adding `+$4,294/yr` per 30 sets.
  - **Week-4 Go/No-Go Gates:** Real-project `Recall ≥ 80%`, `Precision ≥ 85%`, `QC time cut ≥ 30%`, `100%` verified citations, and an agreed capacity-redeployment plan.

---

## 4. Quick Start (Run the Prototype)

### Option A — One-Click Windows Launcher
Double-click **`02_Working_Prototype_and_Demo\RUN.bat`** (auto-configures Python, runs all `35` tests, analyzes `sample_project/`, and opens the Streamlit Review UI at `http://localhost:8501`).

### Option B — Command Line
```bash
cd "02_Working_Prototype_and_Demo/aec-drawing-intelligence"
./run_demo.sh                                  # Installs deps, runs 35 tests, analyses sample_project -> out/
streamlit run ui/review_app.py -- out          # Launches Engineer Review UI at http://localhost:8501
```
