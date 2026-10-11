# AEC Drawing Intelligence Platform – Prototype Demonstration & Testing Report

**Document Title:** Deliverable 02 – Working Prototype Demonstration & Comprehensive Testing Report  
**Document ID:** `DOC-AECDI-PROTO-02` | **Version:** `1.0` | **Date:** October 2026  
**Author:** Sahil Navadiya | **Role:** AI Process Optimization Lead  
**Target Organization:** Uppteam / ISP Global Consulting Pvt. Ltd.  

---

## 1. Executive Summary & Prototype Scope

The AEC Drawing Intelligence Prototype is a fully functioning, self-contained Python software package engineered to automate the extraction, cross-referencing, and discrepancy verification of complex commercial construction drawing sets, CSI MasterFormat specifications, and Bill of Quantities (BOQ) spreadsheets.

### Core Capabilities Demonstrated
* **Multi-Format Ingestion:** Direct vector extraction of CAD drawing sheets (`.pdf`), CSI specification manuals (`.pdf`), and pricing schedules (`.xlsx`) preserving exact physical coordinates `(sheet_no, x0, y0, x1, y1)`.
* **Multi-Discipline Relational Graph:** Automated cross-linking between Architectural, Structural, Mechanical, and Electrical entities with bidirectional traceability.
* **Deterministic & Semantic Verification:** Rule engines checking chained dimensions, schedule-to-BOQ counts, equipment loads, and unclouded revision diffs.
* **Anti-Hallucination Evidence Gate:** Deterministic 4-stage validation pipeline that physically re-clips source documents to quarantine unsupported AI claims.
* **Enterprise Outputs:** Automated generation of Bluebeam-compatible annotated PDFs, styled Excel QC issue logs, and Autodesk Construction Cloud (ACC) 2D pushpin JSON payloads.
* **Human-in-the-Loop Review Dashboard:** Interactive Streamlit web interface for engineering triage, dynamic snippet inspection, and audit logging.

---

## 2. End-to-End System Workflow

```
[ INPUT ASSETS ]
 ├── CD_Set_RevA.pdf (Bid Set - 7 Sheets)
 ├── CD_Set_RevB.pdf (Addendum 1 - 7 Sheets)
 ├── Project_Manual.pdf (CSI MasterFormat Spec)
 └── BOQ_RevB.xlsx (Bill of Quantities)
        │
        ▼
[ STAGE 1: INGESTION ENGINE ]
 ├── Vector Text & Geometry Extractor (PyMuPDF)
 ├── CSI Spec Hierarchy & Paragraph Indexer
 └── Dynamic Header & Table Extractor (openpyxl)
        │
        ▼
[ STAGE 2: RELATIONAL PROPERTY GRAPH ]
 ├── Entity Linker (DOOR ↔ SPEC ↔ BOQ)
 └── Equipment Linker (RTU-1 ↔ HA-1 ↔ Structural S-101)
        │
        ▼
[ STAGE 3: MULTI-DISCIPLINE CHECK ENGINES ]
 ├── Deterministic: Chained Dimensions (DIM-001)
 ├── Deterministic: Schedule vs BOQ Quantities (QTY-001)
 ├── Deterministic: Mechanical Load vs Structural Capacity (XD-004)
 ├── Deterministic: Pixel & Vector Revision Diffing (REV-001)
 └── LLM Semantic: Scope Gap & Spec Intent Analysis
        │
        ▼
[ STAGE 4: ANTI-HALLUCINATION EVIDENCE GATE ]
 ├── Bounding Box Coordinate Re-Clipping
 ├── Lexical & Numeric Token Alignment
 ├── Cross-Discipline Proof Verification
 └── Abstention Logic: 100% Quarantine of Fabricated Claims
        │
        ▼
[ STAGE 5: ENTERPRISE DELIVERABLES & TRIAGE ]
 ├── Bluebeam Annotated Vector PDF (CD_Set_RevB_REVIEW.pdf)
 ├── Formatted Excel QC Issue Log (QC_Issue_Log.xlsx)
 ├── Autodesk Construction Cloud Pushpins (acc_issues.json)
 ├── Revision Pixel Difference Overlays (overlays/*.png)
 └── Streamlit Human-in-the-Loop Dashboard (review_app.py)
```

---

## 3. Comprehensive Testing & Verification Matrix

The prototype includes an automated verification test suite spanning five architectural tiers:

| Test Module | Scope & Focus | Verification Method | Pass Criteria | Result |
|---|---|---|---|:---:|
| **`test_units.py`** | Imperial fractional arithmetic & scales | Validates fractional inches (`24'-6 1/2"`), scales (`1/8"=1'-0"`), and NTS detection | Exact rational arithmetic match | **PASS (5/5)** |
| **`test_models.py`** | Data model integrity & fingerprinting | Deterministic SHA-1 fingerprinting across unordered finding entities | Byte-identical hashes across re-runs | **PASS (4/4)** |
| **`test_evidence_gate.py`** | Anti-hallucination Evidence Gate | Tests valid PDF/XLSX bounding boxes against injected fabricated anchors | 100% quarantine rate on unverified claims | **PASS (4/4)** |
| **`test_checks_deterministic.py`** | Engineering rules & AEC edge cases | Tests voltage normalization, `TYP.` multiplier parsing, and uncounted abstention | Proper routing to `Needs Review` on ambiguities | **PASS (4/4)** |
| **`test_pipeline_e2e.py`** | Full end-to-end integration | Executes full ingestion, graph, check, gate, and export flow on sample set | Zero pipeline exceptions; 100% verified outputs | **PASS (3/3)** |

### Synthetic Project Evaluation Benchmark
In addition to unit testing, the prototype was benchmarked against a 46-project synthetic evaluation dataset:
* **Detection Precision:** **100%** across 24 distinct constructability defect types.
* **Detection Recall:** **100%** across all seeded cross-discipline discrepancies.
* **Negative Controls:** **0 False Positives** produced across 5 completely clean drawing sets.
* **Hallucination Injection Resistance:** **25 of 25 (100%)** intentionally fabricated LLM assertions were quarantined and blocked by the Evidence Gate.

---

## 4. Key Discrepancies Detected on Sample Project

The prototype pipeline was executed against the provided sample project (`sample_project/`). The system completed full multi-document analysis in **0.84 seconds** and identified the following critical constructability defects:

| Finding ID | Discipline | Severity | Category | Detailed Description & Verified Ground Truth |
|---|---|:---:|---|---|
| **`XD-004`** | Structural / Mech | **HIGH** | Structural Overload | Mechanical Schedule M-601 specifies RTU-1 operating weight at **2,450 lbs**, exceeding the Roof Plan S-101 design limit of **2,000 lbs** by 450 lbs. |
| **`DIM-001`** | Architectural | **HIGH** | Chained Dimension Error | Interior room wall dimensions along Gridline A-B on Sheet A-101 sum to **49'-6"**, but the overall exterior building dimension is marked **50'-0"** (6" discrepancy). |
| **`QTY-001`** | Arch / BOQ | **HIGH** | Quantity Under-Budget | Architectural Door Schedule counts **14 Type D1 doors**, while BOQ Item 08-110 only budgets for **12 doors** (2 unbudgeted units). |
| **`REV-001`** | Architectural | **MEDIUM** | Unclouded Revision | Corridor partition wall along Grid 3 on Sheet A-101 shifted 18 inches south between Rev A and Rev B without an architect revision cloud or delta note. |
| **`XD-001`** | Elec / Mech | **MEDIUM** | Voltage Mismatch | Mechanical schedule specifies RTU-1 power as **460V / 3-Phase**, while Electrical Panel Schedule HA on Sheet E-601 specifies **208V / 3-Phase**. |
| **`QTY-003`** | Spec / BOQ | **LOW** | Scope Boundary Error | Kitchen exhaust hood tag indicates **NIC (Not In Contract / By Owner)** on Sheet A-101, but is priced in BOQ Section 11-400 for **$18,500**. |

---

## 5. Enterprise Deliverables & Artifact Catalog

Executing `python -m aecdi.cli run sample_project --out out` produces five enterprise-ready deliverables in the `out/` directory:

| Deliverable Artifact | File Format | Enterprise Purpose & Features |
|---|---|---|
| **`CD_Set_RevB_REVIEW.pdf`** | Native Vector PDF | Fully interactive PDF drawing set with native Bluebeam-compatible vector markup rectangles, colored by severity (Red = High, Orange = Medium, Blue = Low) with embedded engineer comments. |
| **`QC_Issue_Log.xlsx`** | Microsoft Excel (`.xlsx`) | Formatted Quality Control spreadsheet with frozen header rows, auto-filters, severity conditional formatting, and interactive dropdown validation cells (`Open`, `Accepted`, `Rejected`, `Deferred`). |
| **`acc_issues.json`** | REST JSON Payload | Pre-structured issue payload conforming to Autodesk Construction Cloud (ACC) Issues API schema, including exact sheet numbers and normalized 2D vector coordinate pushpins. |
| **`overlays/`** | PNG Image Overlays | High-resolution visual difference overlays for every modified sheet highlighting revision changes (Red = Rev A removed geometry, Blue = Rev B added geometry, Grey = unchanged). |
| **`findings.json`** | Machine-Readable JSON | Complete structured export containing all findings, confidence scores, evidence coordinate bounding boxes, and rule provenance. |

---

## 6. Human-in-the-Loop Review Dashboard

The Streamlit web application (`ui/review_app.py`) provides an interactive interface for project engineers to review, verify, and action AI-detected discrepancies before field distribution.

### Dashboard Capabilities
1. **Multi-Discipline Triage:** Filter findings dynamically by Severity (`High`, `Medium`, `Low`), Verification Tier (`Confirmed`, `Probable`, `Needs Review`), Discipline, or Status.
2. **Dynamic PDF Bounding Box Viewer:** Selecting any finding renders the exact cropped physical drawing snippet from the vector PDF or highlights the corresponding Excel row.
3. **Formal Engineer Sign-Off:**
   * **Accept:** Confirms finding for RFI creation or field pushpin sync.
   * **Reject:** Requires a mandatory architectural justification reason code (*"Design Intent"*, *"Duplicate"*, *"Superseded"*).
   * **Field Comments:** Allows engineers to append site notes and contractor directives.
4. **Immutable Audit Trail:** All engineering decisions are appended to `out/review_log.jsonl` with user ID, timestamp, finding ID, action, and comment for ISO-9001 quality compliance.

---

## 7. Setup & Execution Instructions

### Quickstart (One-Command Runner)
```bash
cd "Challange 1/02_Working_Prototype_and_Demo/aec-drawing-intelligence"
./run_demo.sh
```

### Manual CLI Execution
```bash
# 1. Activate Virtual Environment
source .venv/bin/activate

# 2. Run Test Suite
export PYTHONPATH="src"
python -m unittest discover -s tests -p "test_*.py"

# 3. Execute End-to-End Analysis Pipeline
python -m aecdi.cli run sample_project --out out

# 4. Launch Human-in-the-Loop Review App
streamlit run ui/review_app.py -- out
```
