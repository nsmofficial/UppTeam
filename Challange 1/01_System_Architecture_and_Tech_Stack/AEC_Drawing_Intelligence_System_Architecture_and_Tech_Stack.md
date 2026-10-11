# AEC Drawing Intelligence Platform
## System Architecture & Technology Stack Specification

**Document ID:** `DOC-AECDI-ARCH-01` | **Revision:** `Rev 1.0` | **Date:** `October 2026`  
**Author:** Sahil Navadiya | **Role:** AI Process Optimization Lead  
**Target Organization:** Uppteam / ISP Global Consulting Pvt. Ltd.  
**Scope:** System Architecture & Technology Stack Only  

---

## 1.0 System Architecture & Execution Pipeline

* **Core Principle:** Extract & Structure → Deterministic Rules First → Bounded Semantic LLM → Anti-Hallucination Evidence Gate → Human Engineer Verification.
* **Zero Hallucinations:** Eliminates black-box PDF prompt chaining. 90%+ of checks execute via deterministic geometry, arithmetic, and cross-discipline graph rules.
* **Physical Provenance:** Every data point retains document name, revision, page number, and sub-millimeter bounding box coordinates `(x0, y0, x1, y1)`.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM ARCHITECTURE PIPELINE                             │
│                                                                                  │
│   Extract & Structure   ──►  Deterministic Rules  ──►  Selective LLM Semantic   │
│   (Vector PDFs, Specs,       (Dimensions, Counts,      (Complex CSI text vs.     │
│    BOQs with bboxes)          Tags, Revisions)          Schedule conflicts)      │
│                                                                  │               │
│                                                                  ▼               │
│   Human Engineer Decides ◄──  Evidence Gate Verification ◄───────┘               │
│   (AOR/EOR Audit Trail)       (Re-checks cited snippet at                        │
│                                exact bbox; rejects hallucination)                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.0 Architectural Decomposition (6 Layers)

### 2.1 Layer 1: Ingestion & Spatial Normalization
* **Vector Drawing Parser:** Extracts vector text spans, fonts, directional vectors, and exact bounding boxes using PyMuPDF (50+ sheets/sec, no OCR latency).
* **Title Block & Index:** Isolates sheet IDs (A-101, M-601), scales, and revision schedules. Reconciles sheet index vs actual sheets.
* **Ruled Table Matrix:** Extracts schedules (doors, windows, equipment, panels) by vector line intersections, mapping headers to cell grids.
* **CSI Spec Parser:** Splits project manuals into CSI MasterFormat sections, parts, articles, and lettered paragraphs with physical bounding boxes.
* **BOQ Parser & Units:** Scans Excel workbooks with openpyxl, preserving cell addresses (`Sheet1!E18`). Converts imperial fractions using exact rational arithmetic.

### 2.2 Layer 2: Multi-Discipline Relational Project Graph
* **Property Graph:** In-memory relational graph linking tags, schedules, specs, and BOQ items with typed edges (`appears_on`, `defined_in`, `governed_by`, `quantifies`, `fed_by`, `supported_by`).

| Entity | Node Key | Relational Connections | Physical Provenance |
|---|---|---|---|
| **Sheet** | `SHEET:A-101` | references A-601, listed_in G-001 | File, Page Index, Title Block BBox |
| **Door Tag** | `DOOR:105` | appears_on A-101, defined_in A-601 | Plan Coordinate (x, y), Tag Shape |
| **Door Schedule** | `DOORTYPE:D1` | is_type DOOR:105, governed_by SPEC:08 14 16 | Table Cell BBox, Schedule Row |
| **Equipment Tag** | `EQUIP:RTU-1` | appears_on M-101, fed_by CKT:HA-1, in BOQ | Plan BBox, Capacity, Weight |
| **Electrical Ckt** | `CKT:HA-1` | feeds EQUIP:RTU-1, on SHEET:E-601 | Panel Name, Breaker Amps, Voltage |
| **CSI Spec** | `SPEC:08 14 16` | governs DOORTYPE:D1, refs SPEC:08 71 00 | Section, Article, Paragraph BBox |
| **BOQ Item** | `BOQ:08-110` | quantifies DOORTYPE:D1, prices EQUIP:RTU-1 | Sheet Name, Excel Row & Cell Address |

### 2.3 Layer 3: Deterministic Rule Engines
* **Dimensions (DIM):** `DIM-001`: Chained vs overall sum (tolerance 1/8"). `DIM-002`: Vector length vs scale. `DIM-003`: Cross-sheet grid alignment (A-101 vs S-101).
* **Quantities (QTY):** `QTY-001/2`: Schedule vs BOQ counts. `QTY-003`: Flags NIC (Not In Contract) items in BOQ. `QTY-004`: Abstains on uncounted `TYP.` tags → Needs Review. `QTY-005`: Plan tag multipliers vs schedule.
* **Cross-Discipline (XD):** `XD-001`: Mechanical V/PH vs Electrical panels (120V, 208V, 240V, 480V). `XD-002`: Unpowered equipment. `XD-003`: Breaker sizing vs MCA. `XD-004`: Equipment weight vs structural capacity.
* **Completeness (MISS):** `MISS-001/2`: Undefined / orphan tags. `TAG-001`: Duplicate tags. `MISS-003`: Blank mandatory schedule cells. `MISS-004`: Undefined hardware sets. `MISS-005`: Missing CSI spec sections.
* **Revisions (REV):** `REV-001`: Flags unclouded changes (3-layer diff: tables, text with shift compensation, geometry). `REV-002`: Changed content with unissued revision in title block.

### 2.4 Layer 4: Bounded LLM Semantic Layer (Claude Opus 5.5 / Sonnet)
* **Target Scope:** Reserved exclusively for subtle natural language conflicts between specifications and schedule notes.
* **JSON Schema Enforcement:** Strict schema requires `element`, `attribute`, `schedule_value`, `paragraph_id`, and verbatim `spec_quote`.
* **Guardrails:** Model forbidden from outside assumptions; output tier capped at `Probable`; offline Replay & Mock clients for CI/CD.

### 2.5 Layer 5: Anti-Hallucination Evidence Gate
* **Independent Verification:** Re-opens source PDF/Excel, clips cited bounding box (+1.5pt pad), and verifies normalized snippet.
* **Zero Tolerance:** If snippet is missing or unverified, finding is dropped to rejected log. Shipped findings carry only 100% verified anchors.

### 2.6 Layer 6: Human-in-the-Loop & Enterprise Outputs
* **Annotated Vector PDFs:** Native vector rectangle annotations colored by severity (Red/Orange/Blue) for Bluebeam Revu.
* **Excel QC Issue Log:** Formatted workbook with frozen headers, auto-filters, and dropdown validations (`Open`, `Accepted`, `Rejected`, `Deferred`).
* **Autodesk Construction Cloud:** Formats issues for ACC Issues API with 2D vector centroid pushpins `(x, y)`.
* **Interactive Review App:** Streamlit UI with side-by-side dynamic bounding box crops and append-only audit trail (`review_log.jsonl`).

---

## 3.0 Full Technology Stack Specification

| Architecture Layer | Prototype Technology | Enterprise Target | Technical Role & Selection Rationale |
|---|---|---|---|
| **Runtime / Core** | Python 3.11+ | Python 3.11+ / FastAPI | High throughput, rich scientific computing, robust typing. |
| **Vector PDF Parser** | PyMuPDF (fitz) | PyMuPDF + Azure Doc Intel | 50+ vector sheets/sec. Azure provides fallback OCR for scans. |
| **Table Matrix** | Vector Line Intersection | PyMuPDF Tables + Textract | Deterministic cell extraction eliminates OCR errors on CAD tables. |
| **Computer Vision Diff** | OpenCV (headless) + NumPy | OpenCV + GPU Acceleration | Pixel overlay diffs (Red/Blue/Grey) in < 200ms at 150 DPI. |
| **Spreadsheet Engine** | openpyxl | openpyxl / DuckDB | Preserves exact cell coordinates (`Sheet!E18`) with low memory. |
| **Imperial Math** | Custom Fraction Engine | Custom Fraction Engine | Exact rational arithmetic eliminates floating-point rounding errors. |
| **LLM Semantic Engine** | Claude Opus 5.5 (Anthropic) | Claude 3.5 Sonnet / Llama-3 | Zero Data Retention (ZDR) cloud API; local LLM for strict NDAs. |
| **Workflow Automation** | CLI Pipeline & Python | n8n (Self-Hosted) / Temporal | Event triggers on folder uploads (ACC, Dropbox) automate runs. |
| **Review Dashboard** | Streamlit 1.35+ | React 19 + APS / PDF.js | Instant zero-overhead UI; React provides enterprise scale. |
| **Database & Graph** | JSON / SQLite | PostgreSQL + pgvector | Relational graph storage with ACID guarantees and vector search. |
