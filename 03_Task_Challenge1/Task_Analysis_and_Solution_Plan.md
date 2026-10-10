# Challenge 1: AI-Powered AEC Drawing Intelligence – Analysis & Solution Plan

Task sheet image: `Challenge1_Task_Sheet.webp` (this folder)
Prepared: 10 Oct 2026

---

## 1. The task (transcribed)

**Domain:** Architecture, Engineering & Construction

**Business problem:** AEC teams work with architectural, structural and MEP drawings, specifications, BOQs and revised documents. Identifying discrepancies manually is time-consuming and can lead to costly errors.

**Assignment – design an AI solution that can:**
1. Read and interpret drawings, specifications and BOQs.
2. Compare revisions and identify discrepancies across disciplines.
3. Flag missing information, conflicting dimensions and quantity mismatches.
4. Provide evidence-linked findings that engineers can verify.
5. Integrate into an existing AEC team's workflow.

**Deliverables:**
- Proposed system architecture and technology stack.
- A working prototype or demonstration using sample documents.
- An evaluation plan to measure accuracy and detect hallucinations.
- A 30-day implementation roadmap, including cost and expected ROI.

**Key evaluation:** *Can the candidate handle real-world document complexity, cross-document relationships, uncertainty, and engineering accountability rather than simply connecting an LLM to PDFs?*

---

## 2. What they are really testing

The last line is the whole test. They want to see that you do **not** just upload PDFs to ChatGPT. Build every part of the submission around one principle:

> **Extract → Structure → Check with rules → Use the LLM only where judgment is needed → Human verifies.**
> The system finds a discrepancy and proves it with evidence; the engineer decides.

| Key-evaluation phrase | How the solution answers it |
|---|---|
| Real-world document complexity | Vector-PDF extraction with coordinates, OCR fallback, title blocks, schedules, imperial units, abbreviations (TYP, SIM, NIC, AFF, EQ) |
| Cross-document relationships | A project graph linking tags ↔ schedules ↔ spec sections ↔ BOQ items ↔ sheet references |
| Uncertainty | Confidence on every fact; three tiers (Confirmed / Probable / Needs review); abstain instead of guessing |
| Engineering accountability | Evidence gate, human accept/reject, audit trail, tool never modifies drawings or "approves" |

**Why "LLM on PDFs" fails (put this on one slide):**
1. No coordinates, so findings can't be linked to the exact spot on a sheet.
2. Unreliable counting of tags and quantities.
3. Invents or misreads dimensions.
4. No revision awareness (Rev A vs Rev B, clouds, deltas).
5. No audit trail or accountability.

---

## 3. What to deliver (one email, four items + summary)

| Their deliverable | What you send |
|---|---|
| Architecture & tech stack | 10–12 page PDF report or 12-slide deck with an architecture diagram |
| Working prototype | GitHub repo with README (one-command run) + 4–5 minute demo video |
| Evaluation plan | Eval section with **real measured numbers** from the sample set |
| 30-day roadmap, cost, ROI | Week-by-week plan, cost table, ROI under three scenarios |

Put a **one-page executive summary** on top (the reader may be in Admin/operations).

---

## 4. System architecture

```
Inputs: drawing PDFs (Rev A, Rev B) · spec book (PDF) · BOQ (Excel)
   │
1. INGEST & UNDERSTAND
   • Sheet split + title-block parse (A-101, S-201, M-301, rev no., date)
   • Vector text with coordinates (PyMuPDF); OCR only for scans
   • Tables: door/window/equipment schedules, BOQ rows
   • Units parsed: 12'-6" → 3810 mm; abbreviations (TYP, NIC, AFF, EQ)
   │
2. PROJECT GRAPH  (every fact stores doc · rev · page · bbox · method · confidence)
   Tags (D-03, RTU-1) ↔ schedule rows ↔ spec sections (CSI) ↔ BOQ items ↔ sheet refs (3/A-501)
   │
3. CHECKS: rules first, LLM second
   • Revision diff: text-object diff + visual overlay; flag "changed but NOT clouded"
   • Cross-discipline: same tag/room/grid across A/S/M; equipment vs electrical panel
   • Quantities: plan tag count vs schedule vs BOQ
   • Missing info: undefined tags, blank schedule fields, refs to non-existent sheets
   • Dimensions: chained dimensions ≠ overall dimension
   • LLM only for meaning-level conflicts (spec "solid-core wood" vs schedule "HM"),
     with structured JSON output and mandatory citations
   │
4. EVIDENCE GATE: anti-hallucination
   Every quoted snippet is re-found in the source at that page/bbox.
   Not found → finding is dropped or downgraded. No finding without evidence.
   │
5. HUMAN REVIEW: Confirmed · Probable · Needs review → Accept / Reject / Comment → audit log
   │
6. INTEGRATION: annotated PDF markups (open in Bluebeam) · Excel issue log ·
   Autodesk Construction Cloud (ACC) Issues API · n8n trigger on new revision upload
```

### 4.1 Layer details

**Ingestion & understanding**
- Most Revit/AutoCAD exports are **vector PDFs**: extract text spans with exact coordinates (PyMuPDF), no OCR needed. OCR (PaddleOCR / Azure Document Intelligence) only for scanned sheets.
- Sheet classification by sheet number prefix (A, S, M, E, P, FP) per U.S. National CAD Standard.
- Title block parsing: sheet number, title, revision number/date; detect revision clouds and deltas.
- Table extraction for schedules (door, window, equipment, panel) and BOQ (pandas/openpyxl).
- Spec parsing by CSI MasterFormat section (e.g., 08 14 16 Flush Wood Doors), Part 1/2/3 structure.
- Dimension strings normalized with a unit library (pint).
- A vision-language model is used **selectively** (callouts, legends, ambiguous regions), always returning structured JSON with a bbox reference.

**Project graph (the core idea)**
- Entities: Sheet, Revision, Grid, Level, Room, Door/Window tag, Equipment tag (AHU-1, RTU-2), Structural mark, Spec section, BOQ item, Dimension.
- Relationships: tag *appears on* sheet at bbox; tag *defined in* schedule row; spec section *governs* element type; BOQ item *quantifies* element type; callout *references* detail sheet; equipment *fed by* electrical circuit.
- Every fact carries provenance: document, revision, page, bbox, extraction method, confidence.

**Detection engines (deterministic first)**
- *Revision comparison:* match sheets by number; diff text objects spatially (added/removed/changed tags, dimensions, notes); raster overlay diff (render both at same DPI, align, difference image); flag **changed but not clouded** areas.
- *Cross-discipline consistency:* same equipment/room/grid across A/S/M; equipment capacity on plan vs schedule; MEP equipment missing from electrical panel schedule; grid mismatch between A and S.
- *Quantity reconciliation:* tag count on plans vs schedule rows vs BOQ quantity (e.g., door type D3: 14 on plans, 12 in schedule, 12 in BOQ).
- *Missing information:* tags with no schedule entry; schedule rows with blank required fields (fire rating, hardware set); callouts to sheets not in the set; spec sections referenced but missing; BOQ items with no spec section.
- *Dimension conflicts:* chained dimension sum ≠ overall dimension; same span dimensioned differently on two sheets.
- *LLM-assisted semantic checks:* spec vs schedule/note conflicts, with retrieved evidence pairs and mandatory citations.

**Real-world traps to show you understand**
- **"TYP." / "SIM."**: one tag can represent many elements, so a raw tag count is uncertain → route to *Needs review*, never a confirmed mismatch.
- **"NIC"** (not in contract) items should not appear in the BOQ.
- Addenda and alternates; "or approved equal" in specs; BOQ units (EA, LF, SF, CY).
- **Prefer native data** (Revit schedules, IFC) when available; PDF parsing is the fallback.

**Finding schema (example)**
```json
{
  "id": "F-0042",
  "type": "quantity_mismatch",
  "severity": "high",
  "tier": "confirmed",
  "disciplines": ["A"],
  "statement": "Door type D3: 14 tags on A-101/A-102, 12 rows in door schedule A-601, BOQ item 08-110 = 12 EA",
  "evidence": [
    {"doc": "A-101", "rev": "B", "page": 1, "bbox": [412, 233, 431, 247], "snippet": "D3"},
    {"doc": "A-601", "rev": "B", "page": 1, "bbox": [88, 540, 610, 556], "snippet": "D3 ... 3'-0\" x 7'-0\""},
    {"doc": "BOQ.xlsx", "sheet": "Doors", "row": 18, "snippet": "08-110 Wood door D3, 12 EA"}
  ],
  "method": "rule:QTY-001",
  "confidence": 0.97,
  "status": "open",
  "reviewer": null
}
```
Rule: no finding without ≥1 evidence anchor (≥2 for conflicts). Language: "potential discrepancy", never "error".

**Human review & accountability**
- Review screen sorted by severity; side-by-side evidence crops; Accept / Reject / Comment; rejection reasons feed the eval set.
- The tool never edits drawings or approves anything. The AOR/EOR decides. Full audit trail.

**Workflow integration**
- Typical flow: Revit → PDF set → Bluebeam review → ACC issues → Excel QC log.
- Trigger: new revision uploaded to ACC / Google Drive / Dropbox → n8n runs the pipeline.
- Outputs: annotated PDF (highlights + comments readable in Bluebeam), Excel issue log in their QC format, ACC Issues via Autodesk Platform Services API, BCF (optional), email/chat notification.
- Fits their existing **Second Eye** QC service; could become a sellable AI-assisted product.

### 4.2 Technology stack

| Layer | Prototype | Production |
|---|---|---|
| Language / API | Python, FastAPI | same |
| PDF text & coordinates | PyMuPDF, pdfplumber | same |
| Tables | Camelot / PyMuPDF tables | same + vendor fallback |
| OCR (scans) | PaddleOCR | Azure Document Intelligence (optional) |
| Visual diff | OpenCV | same |
| BOQ | pandas, openpyxl | same |
| Units | pint | same |
| LLM / VLM | Claude or GPT via API (zero data retention), Pydantic structured output | + local model option for NDA projects |
| Storage | SQLite + local files | PostgreSQL + pgvector, object storage |
| Orchestration | n8n | n8n / LangGraph |
| Review UI | Streamlit | React + PDF.js |
| Tracing / eval | pytest + custom harness | + Langfuse |

---

## 5. Prototype plan

**Sample documents (never client data)**
1. **Synthetic seeded set (ground truth):** A-101 floor plan with door tags, A-601 door schedule, M-101 with equipment tags, M-601 equipment schedule, one spec section (08 14 16 Flush Wood Doors), a BOQ in Excel, and two revisions (Rev A, Rev B). Seed ~30–40 known defects across all finding types, plus an answer key. Because every answer is known, you can report precision and recall.
2. **One real public U.S. bid set** (city or school-district procurement portals publish drawing sets and project manuals). Shows real-world messiness. Credit the source.

**Minimum features**
- Sheet index and title-block parsing.
- Tag and schedule extraction.
- Plan vs schedule vs BOQ quantity check.
- Undefined / orphan tags.
- One spec-vs-schedule LLM check with citations.
- Revision diff with overlay image and unclouded-change flag.
- Annotated PDF, Excel issue log, Streamlit review screen.

**Demo video (4–5 min):** upload → run → findings list → click a finding → jump to highlighted spot on the PDF → accept/reject → show the eval table.

**Suggested repo layout**
```
aec-drawing-intelligence/
├─ README.md            # problem, architecture, one-command run, results
├─ data/
│  ├─ synthetic/        # Rev A, Rev B PDFs, spec, BOQ, answer_key.json
│  └─ public/           # public bid set (with source note)
├─ src/
│  ├─ ingest/           # pdf_text.py, title_block.py, tables.py, boq.py, specs.py
│  ├─ graph/            # model.py (entities + provenance), build.py
│  ├─ checks/           # quantities.py, missing.py, dimensions.py, revisions.py, semantic_llm.py
│  ├─ evidence/         # verify_citations.py, crops.py
│  ├─ outputs/          # annotate_pdf.py, issue_log_xlsx.py, acc_issues.py
│  └─ api/              # FastAPI app
├─ ui/                  # Streamlit review screen
├─ eval/                # run_eval.py, metrics.py, reports/
└─ n8n/                 # exported workflow JSON
```

---

## 6. Evaluation plan (accuracy + hallucination detection)

**Detection metrics (per finding type):** precision, recall, F1 on the seeded set. Report actual numbers.

**Extraction metrics:** tag recall, schedule cell accuracy, dimension-parse accuracy, title-block field accuracy.

**Evidence metrics:** correct page; bbox overlap ≥ 50% with the true location.

**Hallucination controls**
1. **Citation verification:** every quoted snippet must be found in the source at the cited page/bbox (automated). Pass rate must be 100% for shipped findings.
2. **Negative controls:** clean documents with zero seeded defects; any finding is a false positive.
3. **Run-to-run consistency:** same inputs, repeated runs, same findings.
4. **Abstention:** when extraction confidence is low, output *Needs review*, never a confident claim.
5. **Unsupported-claim rate:** reviewer samples findings and checks that evidence actually supports the statement.

**Calibration:** stated confidence should match measured precision; auto-surface only findings at ≥ 90% precision; the rest go to *Needs review*.

**Production monitoring:** reviewer accept rate (live precision); issues found later by QC that the tool missed (live recall proxy); time per review.

**Pilot acceptance criteria (targets, not results):** recall ≥ 80% and precision ≥ 85% on seeded set; 100% citation-verification pass; ≥ 30% QC time reduction on pilot projects.

---

## 7. 30-day implementation roadmap

| Week | Work | Exit criterion |
|---|---|---|
| 1 | Shadow the QC team; collect 3 past projects with their QC logs as ground truth; measure baseline hours per review; settle data-security rules (approved LLM provider, zero retention, NDA limits) | Baseline numbers and pilot scope signed off |
| 2 | Adapt extraction to their title blocks and CAD standards; run the eval harness on past projects | Recall/precision measured on their real data |
| 3 | Review UI, n8n folder trigger, Bluebeam/Excel outputs; shadow pilot on 2 live projects alongside normal QC | Zero impact on deliveries |
| 4 | Compare to baseline, tune thresholds, run a QC-team workshop | Go/no-go report with ROI |

---

## 8. Cost

| Item | Estimate |
|---|---|
| People | Existing staff: AI lead (you) + ~20% of a senior QC reviewer for 30 days |
| Compute | VM ~$50–150/month (or an existing workstation) |
| Software | n8n self-hosted, PostgreSQL, Streamlit, PyMuPDF: free/open source (check PyMuPDF AGPL licence for commercial use) |
| LLM API | A few dollars per drawing-set run (rules handle most checks; LLM only for semantic checks) – **verify current provider pricing before quoting** |
| OCR (scans only) | Low; pay-per-page cloud OCR or free PaddleOCR |

---

## 9. ROI (formula + scenarios; every input is an assumption to validate in Week 1)

- **Hours saved / month** = sets per month × QC hours per set × % reduction
- **Value** = hours saved × billing rate (~$20–25/hr) + rework avoided
- **Payback** = one-time effort ÷ (monthly value − monthly running cost)

| Scenario | Sets/month | QC hrs/set | Reduction | Hours saved/month | Value at $22/hr |
|---|---|---|---|---|---|
| Conservative | 20 | 8 | 25% | 40 | ~$880 |
| Base | 30 | 12 | 40% | 144 | ~$3,170 |
| Optimistic | 40 | 16 | 50% | 320 | ~$7,040 |

Running cost ~$300–1,000/month → base-case payback ~1–3 months.
**Bigger upside:** Uppteam already sells a **Second Eye** QC service; an AI-assisted version could be sold to U.S. firms at U.S. rates. Also: fewer errors reaching clients (protects reputation, avoids RFIs and rework).

---

## 10. Report / deck outline (12 slides)

1. Problem & principle ("The system finds and proves; engineers decide")
2. Why "LLM on PDFs" fails (5 reasons)
3. Architecture diagram
4. Project graph & cross-document relationships
5. Detection engines (rules + AI)
6. Evidence & review UX (screenshot)
7. Demo results on sample set (metrics table)
8. Evaluation & hallucination controls
9. Workflow integration (Revit → PDF → Bluebeam → ACC, n8n)
10. 30-day roadmap
11. Cost & ROI
12. Risks, limits, governance (scans, symbols without text, geometry from images, TYP/SIM, data security)

---

## 11. How to make them accept it gladly

- **Open with the accountability principle** and the "Why not just an LLM on PDFs" slide.
- **Show honest limits** (scanned sheets, text-less symbols, measuring from images, TYP/SIM) and how each routes to *Needs review*. That is exactly what "uncertainty" in their key-evaluation line means.
- **Use their vocabulary:** CD sets, AOR/EOR, Second Eye, AOP, Bluebeam, ACC. Write "potential discrepancy", never "error".
- **Report measured numbers, not promises.** Modest real results beat big claims.
- **Say you used AI tools to build it** (the JD asks for daily ChatGPT/Claude users), and be able to explain every component. They will probe.
- **Never use client data;** state that all samples are synthetic or public.
- **Keep it positive** about the company; don't mention negative research findings.

## 12. Cover email (template)

> Subject: Challenge 1 – AI-Powered AEC Drawing Intelligence – Sahil Navadiya
>
> Dear [Name],
>
> Please find my submission for Challenge 1:
> 1. Report (PDF): architecture, stack, evaluation plan, 30-day roadmap with cost and ROI
> 2. Prototype: [GitHub link] (README has a one-command run)
> 3. Demo video (4 min): [link]
>
> The core design principle: the system extracts and structures drawings, specs and BOQs, checks them with deterministic rules first, uses AI only where judgment is needed, and links every finding to evidence on the sheet so engineers can verify and decide. On my seeded sample set it achieved [X]% precision and [Y]% recall, with every shipped finding passing citation verification.
>
> All sample documents are synthetic or public; no client data was used. I'd welcome the chance to walk you through it.
>
> Best regards,
> Sahil Navadiya

## 13. Next steps

1. Generate the synthetic seeded sample set (PDFs, spec, BOQ, answer key).
2. Build the extraction → graph → checks → evidence pipeline.
3. Build the review UI and outputs (annotated PDF, Excel log).
4. Run the evaluation and fill in real numbers.
5. Write the report/deck, record the demo, send the email.
