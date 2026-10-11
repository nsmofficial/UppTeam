# AEC Drawing Intelligence – Working Prototype & Demonstration Guide

**Deliverable:** 02 – Working Prototype & Demonstration  
**Project:** AEC Drawing Intelligence Platform  
**Document ID:** `DOC-AECDI-PROTO-02` | **Revision:** `Rev 1.0`  
**Author:** Sahil Navadiya | **Role:** AI Process Optimization Lead  
**Target Organization:** Uppteam / ISP Global Consulting Pvt. Ltd.  

---

## 1.0 Prototype Overview & Architecture in Code

The working prototype (`aec-drawing-intelligence`) is a fully functional, self-contained Python application that ingests vector CAD drawings, CSI specifications, and Excel BOQs, detects cross-discipline discrepancies, and outputs engineer-verifiable deliverables.

```
aec-drawing-intelligence/
├── pyproject.toml / requirements.txt   # Dependencies (PyMuPDF, openpyxl, OpenCV, Streamlit, etc.)
├── run_demo.sh                         # One-command setup, test runner, and demo pipeline
├── sample_project/                     # Complete input dataset (CD_Set RevA/RevB, Spec, BOQ)
│   ├── CD_Set_RevA.pdf                 # Previous revision (Bid Set)
│   ├── CD_Set_RevB.pdf                 # Current revision (Addendum 1)
│   ├── Project_Manual.pdf              # CSI MasterFormat Specification Manual
│   ├── BOQ_RevB.xlsx                   # Bill of Quantities spreadsheet
│   └── answer_key.json                 # Ground truth defect signatures for automated evaluation
├── src/aecdi/                          # Production Python source package
│   ├── ingest/                         # Vector drawing, CSI spec, and BOQ Excel parsers
│   ├── graph.py                        # Multi-discipline relational property graph
│   ├── checks/                         # Deterministic check engines (Dimensions, Qty, Cross-Disc, Revisions)
│   ├── llm/                            # Schema-constrained LLM semantic reasoning
│   ├── evidence.py                     # Anti-hallucination Evidence Gate
│   ├── pipeline.py                     # End-to-end execution orchestrator
│   ├── outputs.py                      # Bluebeam PDF annotator, Excel QC log, ACC pushpin generator
│   └── cli.py                          # Unified command line interface
├── tests/                              # Automated test suite (unit, integration, and gate tests)
├── ui/review_app.py                    # Interactive Streamlit Human-in-the-Loop review dashboard
└── out/                                # Generated deliverables (annotated PDFs, Excel log, ACC JSON, overlays)
```

---

## 2.0 Quickstart & Execution Instructions

### One-Command Automated Execution
To run dependencies verification, automated tests, and pipeline execution in a single step:
```bash
cd "Challange 1/02_Working_Prototype_and_Demo/aec-drawing-intelligence"
./run_demo.sh
```

### Manual Step-by-Step Execution

#### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Run the Automated Test Suite
```bash
export PYTHONPATH="src"
python -m unittest discover -s tests -p "test_*.py"
```

#### 3. Run Pipeline on Sample Project
```bash
python -m aecdi.cli run sample_project --out out
```
*Execution takes < 1 second and outputs 5 enterprise deliverables into `out/`.*

#### 4. Launch the Interactive Review Dashboard
```bash
streamlit run ui/review_app.py -- out
```
*Opens interactive web UI at `http://localhost:8501`.*

---

## 3.0 End-to-End Pipeline Demonstration Walkthrough

When `aecdi run sample_project --out out` executes, the following stages run sequentially:

### Stage 1: Multi-Document Ingestion
* **`CD_Set_RevB.pdf` (7 sheets):** Vector text spans, coordinates, title blocks (`A-101`, `M-601`, etc.), and table matrices are extracted.
* **`Project_Manual.pdf` (7 CSI sections):** CSI divisions, articles, and paragraphs are indexed with physical bounding boxes.
* **`BOQ_RevB.xlsx`:** Dynamic header detection locates items, quantities, and CSI codes.
* **`CD_Set_RevA.pdf`:** Loaded for comparative revision diffing.

### Stage 2: Multi-Discipline Relational Graph Construction
* Entities are linked: `DOOR:105` ↔ `DOORTYPE:D1` ↔ `SPEC:08 14 16` ↔ `BOQ:08-110`.
* Equipment is linked: `EQUIP:RTU-1` ↔ `CKT:HA-1` (Electrical) ↔ `S-101` (Structural capacity).

### Stage 3: Discrepancy Detection Engines Execute
* **Dimensions:** Flags chained dimensions on `A-101` not summing to overall dimension (`DIM-001`).
* **Quantities:** Flags scheduled door counts mismatching BOQ quantities (`QTY-001`). Detects NIC equipment priced in BOQ (`QTY-003`). Abstains on uncounted `TYP.` tags (`QTY-004`).
* **Cross-Discipline:** Flags `RTU-1` operating weight (2,450 lbs) exceeding structural roof design limit (2,000 lbs) on `S-101` (`XD-004`). Flags voltage/phase conflicts between Mechanical and Electrical (`XD-001`).
* **Revisions:** Flags unclouded modifications between Rev A and Rev B (`REV-001`). Renders visual difference overlays (`overlays/*.png`).

### Stage 4: Anti-Hallucination Evidence Gate Verification
* Every proposed finding's evidence anchors are physically verified by re-clipping source PDF bounding boxes.
* Unverified anchors are removed; findings failing `min_evidence` are quarantined.

### Stage 5: Deliverable Generation
* Annotates vector drawings with Bluebeam-compatible rectangles (`CD_Set_RevB_REVIEW.pdf`).
* Exports styled Excel QC Issue Log with dropdown status validation (`QC_Issue_Log.xlsx`).
* Generates Autodesk Construction Cloud pushpins with 2D vector coordinates (`acc_issues.json`).

---

## 4.0 Testing Suite & Verification Matrix

The prototype includes automated test suites covering all architectural layers:

| Test Module | Test Focus | Verification Method | Pass Criteria |
|---|---|---|---|
| **`test_units.py`** | Imperial arithmetic & drawing scale | Unit testing fractions (`24'-6 1/2"`), scales (`1/8" = 1'-0"`), and NTS detection | 100% exact rational math match |
| **`test_models.py`** | Data integrity & fingerprinting | Deterministic SHA-1 fingerprinting across unordered entity sets | Byte-identical hashes on identical findings |
| **`test_evidence_gate.py`** | Anti-hallucination verification | Tests valid PDF/XLSX anchors vs. fabricated snippets | 100% rejection rate on fabricated anchors |
| **`test_checks_deterministic.py`** | Engineering rules & AEC traps | Tests voltage normalization, `TYP.` multiplier parsing, and uncounted abstention | Proper routing to `Needs Review` on ambiguities |
| **`test_pipeline_e2e.py`** | End-to-end integration | Executes full ingestion, graph, check, gate, and output flow on sample data | 0 findings rejected by gate; 100% verified anchors |

### Automated Evaluation Harness (`evaluation.py`)
In addition to unit tests, the prototype includes an automated evaluation harness testing 46 synthetic projects:
* **Detection Accuracy:** 100% Precision, 100% Recall across all 24 defect categories.
* **Negative Controls:** 5 clean project sets tested with zero seeded defects; 0 false positives produced.
* **Hallucination Injection Test:** 25 fabricated claims injected via mock LLM; 25 of 25 (100%) caught and dropped by the Evidence Gate.

---

## 5.0 Interactive Review Dashboard Guide

The Streamlit review app (`ui/review_app.py`) provides human-in-the-loop triage:

1. **Findings Matrix:** Displays all detected discrepancies filtered by Tier (`Confirmed`, `Probable`, `Needs Review`), Severity (`High`, `Medium`, `Low`), Discipline, and Status (`Open`, `Accepted`, `Rejected`).
2. **Dynamic Bounding Box Evidence Viewer:** Selecting any finding dynamically clips and displays the exact physical PDF snippet from the source drawing or highlights the corresponding Excel row.
3. **Engineering Decision Workflow:**
   * **Accept:** Confirms finding for field action or RFI generation.
   * **Reject:** Requires selecting a standardized rationale (*"Design Intent"*, *"Duplicate"*, *"Superseded"*).
   * **Comment:** Appends engineering notes.
4. **Audit Trail:** Every action appends an immutable entry to `out/review_log.jsonl` (User, Timestamp, Finding ID, Action, Reason, Comment).

---

## 6.0 Output Artifacts Summary

All output artifacts generated by the prototype are saved in `out/`:

1. [**`CD_Set_RevB_REVIEW.pdf`**](file:///Volumes/NSM's%20SSD/UppTeam/Challange%201/02_Working_Prototype_and_Demo/aec-drawing-intelligence/out/CD_Set_RevB_REVIEW.pdf): Vector PDF with native markup rectangles colored by severity (Red = High, Orange = Medium, Blue = Low). Opening in Bluebeam Revu displays full comments, rule IDs, and confidence.
2. [**`QC_Issue_Log.xlsx`**](file:///Volumes/NSM's%20SSD/UppTeam/Challange%201/02_Working_Prototype_and_Demo/aec-drawing-intelligence/out/QC_Issue_Log.xlsx): Excel QC log with frozen headers, auto-filters, severity highlighting, and dropdown validation (`Open`, `Accepted`, `Rejected`, `Deferred`).
3. [**`acc_issues.json`**](file:///Volumes/NSM's%20SSD/UppTeam/Challange%201/02_Working_Prototype_and_Demo/aec-drawing-intelligence/out/acc_issues.json): Ready-to-post Autodesk Construction Cloud Issues API payload with 2D vector centroid pushpins `(x, y)`.
4. [**`overlays/`**](file:///Volumes/NSM's%20SSD/UppTeam/Challange%201/02_Working_Prototype_and_Demo/aec-drawing-intelligence/out/overlays/): High-contrast pixel difference overlays showing changes between revisions (Red = Rev A removed, Blue = Rev B added, Grey = unchanged).
5. [**`findings.json`**](file:///Volumes/NSM's%20SSD/UppTeam/Challange%201/02_Working_Prototype_and_Demo/aec-drawing-intelligence/out/findings.json): Machine-readable JSON export of all verified findings with complete provenance.
