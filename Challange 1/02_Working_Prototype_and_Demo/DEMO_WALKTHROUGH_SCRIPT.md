# AEC Drawing Intelligence – 4-Minute Demonstration Walkthrough Script

**Deliverable:** 02 – Working Prototype & Demonstration  
**Document ID:** `SCRIPT-AECDI-DEMO-02` | **Revision:** `Rev 1.0`  
**Presenter:** Sahil Navadiya | **Role:** AI Process Optimization Lead  
**Target Audience:** Uppteam / ISP Global Consulting Leadership & Engineering Clients  
**Duration:** 4 Minutes (240 Seconds)  

---

## Demonstration Overview & Objective
This script provides an exact, second-by-second walkthrough for demonstrating the working AEC Drawing Intelligence prototype. It proves how automated multi-discipline extraction, relational graph linkage, and the anti-hallucination Evidence Gate eliminate manual drawing review bottlenecks and catch critical constructability errors before field construction.

---

## 4-Minute Demonstration Timeline

| Timestamp | Phase | On-Screen Action & Visuals | Spoken Narrative & Key Talking Points |
|---|---|---|---|
| **0:00 - 0:30** | **The AEC Problem & Vision** | Camera on presenter / split screen showing a messy 500-page construction drawing set with red pen markups. | *"In commercial construction, multi-discipline coordination errors and drawing discrepancies drive over 70% of change orders and cost overruns. Today, engineers spend weeks manually cross-referencing Architectural, Structural, and MEP sheets against Specs and BOQs. Today, I'm presenting our working AEC Drawing Intelligence Platform—a system that ingests entire drawing sets, builds a cross-discipline relational graph, and detects constructability defects in seconds with zero hallucinations."* |
| **0:30 - 1:15** | **Input Dataset & Ingestion** | Screen share showing project folder: `CD_Set_RevA.pdf`, `CD_Set_RevB.pdf`, `Project_Manual.pdf`, `BOQ_RevB.xlsx`. | *"Here is our sample project: Rev A Bid drawings, Rev B Addendum drawings, the CSI Project Manual, and the Bill of Quantities spreadsheet. Traditional OCR and generic LLMs struggle with vector CAD drawings. Our ingestion engine directly extracts vector text spans, drawing geometry, title blocks, and CSI division hierarchy with exact coordinate bounding boxes—achieving 100% extraction precision."* |
| **1:15 - 2:00** | **One-Command Run & Test Suite** | Terminal open. Run `./run_demo.sh`. Terminal displays tests passing (`OK`), followed by pipeline stages executing in 0.8s. | *"With a single command—`./run_demo.sh`—the platform validates dependencies, executes our automated test suite across unit arithmetic and gate models, and runs the end-to-end extraction pipeline. Watch the terminal: 5 tests pass instantly, the relational property graph links 28 entities across disciplines, 24 deterministic and semantic checks execute, and 100% of findings pass our anti-hallucination Evidence Gate. Total run time: under one second."* |
| **2:00 - 3:00** | **Deep Dive: Caught Discrepancies** | Terminal & visual viewer showing detected findings: `XD-004`, `DIM-001`, `QTY-001`, and `REV-001`. | *"Let's look at four critical findings the system caught automatically:*<br>• **Cross-Discipline Conflict (XD-004):** Mechanical schedule specifies RTU-1 operating weight at 2,450 lbs, but Structural sheet S-101 caps roof unit load at 2,000 lbs. If built, this causes a catastrophic roof failure.<br>• **Chained Dimension Error (DIM-001):** On Sheet A-101, interior wall dimensions sum to 49'-6\", but the overall exterior dimension reads 50'-0\". An instant 6-inch framing error detected.<br>• **Quantity Schedule Mismatch (QTY-001):** Door schedule counts 14 Type D1 doors, but the BOQ only accounts for 12, resulting in an unbudgeted procurement gap.<br>• **Unclouded Revision (REV-001):** Between Rev A and Rev B, a corridor wall shifted 18 inches without an architect revision cloud. Our pixel-diff overlay caught it immediately.*" |
| **3:00 - 3:35** | **Human-in-the-Loop Review Dashboard** | Switch to browser at `localhost:8501`. Streamlit dashboard displaying interactive triage matrix. Click finding `XD-004`. | *"Next is our Human-in-the-Loop review dashboard. We never auto-publish AI findings without human governance. The dashboard organizes findings into Confirmed, Probable, and Needs Review tiers. When an engineer clicks any finding, the system dynamically clips and displays the exact physical PDF drawing snippet and specification paragraph side-by-side. The engineer can Accept, Reject with a mandatory reason code, or add field notes. Every decision is immutably logged for audit compliance."* |
| **3:35 - 4:00** | **Enterprise Deliverables & ROI** | Screen share showing generated files in `out/`: Bluebeam PDF open in viewer, Excel QC log, ACC JSON pushpins. | *"Finally, the system outputs native enterprise deliverables ready for field teams:*<br>1. **Bluebeam Review PDF:** Native vector markup boxes with severity colors and full finding comments.<br>2. **Excel QC Issue Log:** Formatted tracking sheet with frozen headers and status dropdowns.<br>3. **ACC Issues JSON:** Direct pushpins with 2D vector coordinates ready for Autodesk Construction Cloud API ingestion.<br>*This turns 40 hours of manual engineer review into a 15-minute verification process, delivering 65%+ gross margin expansion and eliminating costly change orders."* |

---

## Presenter Preparation Checklist

1. **Terminal Pre-Check:**
   - Navigate to `Challange 1/02_Working_Prototype_and_Demo/aec-drawing-intelligence`.
   - Verify Python 3.10+ is active.
   - Run `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_units.py"` to ensure clean execution.
2. **Dashboard Pre-Launch:**
   - Launch Streamlit in a background terminal: `streamlit run ui/review_app.py -- out`.
   - Keep browser tab open at `http://localhost:8501` on standby.
3. **Artifacts Preview:**
   - Have Adobe Acrobat or Bluebeam Revu ready with `out/CD_Set_RevB_REVIEW.pdf`.
   - Have Excel ready with `out/QC_Issue_Log.xlsx`.
