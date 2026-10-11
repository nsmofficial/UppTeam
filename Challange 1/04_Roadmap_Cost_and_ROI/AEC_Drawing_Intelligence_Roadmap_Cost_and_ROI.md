# AEC Drawing Intelligence – Implementation Roadmap, Cost Analysis & ROI Model

**Document Title:** Deliverable 04 – Implementation Roadmap, Infrastructure Cost Modeling & Operational ROI Analysis  
**Document ID:** `DOC-AECDI-ROI-04` | **Version:** `1.0` | **Date:** October 2026  
**Author:** Sahil Navadiya | **Role:** AI Process Optimization Lead  
**Target Organization:** Uppteam / ISP Global Consulting Pvt. Ltd.  

---

## 1. Executive Summary & Strategic Business Context

In commercial Architectural Offshore Production (AOP), manual Quality Control (QC) represents **20% to 35% of total billable engineering hours**. Discrepancies between Architectural, Structural, and MEP packages that escape offshore review lead to costly field Requests for Information (RFIs), delayed project milestones, and client churn.

This document establishes the **30-day production rollout roadmap**, **90-day commercial scaling strategy**, **cloud and air-gapped infrastructure cost model**, and **financial ROI framework** for deploying the AEC Drawing Intelligence Platform across Uppteam's production operations.

```
                      STRATEGIC IMPACT AT A GLANCE
┌────────────────────────────────────────────────────────────────────────┐
│ 1. 30-DAY PILOT TIMELINE: From zero to shadow-production in 4 weeks.   │
├────────────────────────────────────────────────────────────────────────┤
│ 2. OPERATIONAL LEVERAGE: 40%–50% reduction in first-pass QC duration.  │
├────────────────────────────────────────────────────────────────────────┤
│ 3. LEAN CLOUD INFRASTRUCTURE: Only $0.85–$1.45 compute cost per set.    │
├────────────────────────────────────────────────────────────────────────┤
│ 4. DIRECT INTERNAL MARGIN GAIN: $66,000–$79,200 annual drafting savings.│
├────────────────────────────────────────────────────────────────────────┤
│ 5. REVENUE UPSIDE: Productizes Uppteam's 'Second Eye' QC service at    │
│    $65–$95/hr for North American architectural clients.                │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 30-Day Phased Implementation Roadmap

The 30-day rollout is structured into four sequential, low-risk weekly sprints designed to integrate into existing production workflows with zero disruption to active drafting deadlines:

```
                    30-DAY IMPLEMENTATION MILESTONES
 ┌───────────────────────────────────────────────────────────────────────┐
 │ WEEK 1: DISCOVERY, BASELINING & DATA PRIVACY ACCORD                   │
 │   • Shadow QC team on live sets  • Benchmark baseline QC hours/set    │
 │   • Establish Enterprise Zero Data Retention (ZDR) security boundary  │
 ├───────────────────────────────────────────────────────────────────────┤
 │ WEEK 2: PARSER ADAPTATION & HISTORICAL BENCHMARKING                   │
 │   • Adapt sheet index & title block extractors to client CAD standards│
 │   • Benchmark system on 10 completed historical projects (eval set)   │
 ├───────────────────────────────────────────────────────────────────────┤
 │ WEEK 3: SHADOW-MODE PILOT & WORKFLOW INTEGRATION                      │
 │   • Deploy Streamlit review app & Bluebeam/Excel output generators    │
 │   • Shadow-pilot alongside senior QC engineers on 2 live projects     │
 ├───────────────────────────────────────────────────────────────────────┤
 │ WEEK 4: CALIBRATION, WORKSHOP & EXECUTIVE GO/NO-GO                    │
 │   • Tune confidence thresholds based on engineer rejection rationales │
 │   • Deliver QC team training workshop & present Executive ROI Report  │
 └───────────────────────────────────────────────────────────────────────┘
```

### Detailed Sprint Breakdown

| Sprint | Focus & Activities | Key Deliverables | Exit Criteria |
|---|---|---|---|
| **Week 1** | **Discovery & Security**<br>• Shadow AOP production pods across 3 commercial projects.<br>• Measure baseline hours per QC review cycle.<br>• Finalize enterprise LLM terms (Zero Data Retention) and air-gapped criteria. | • Baseline QC metrics sheet.<br>• Security & Data Handling Accord.<br>• Client CAD standard template index. | Baseline QC hours signed off;<br>Security boundary approved by IT. |
| **Week 2** | **Standard Adaptation**<br>• Calibrate title block bounding boxes for top 5 client templates.<br>• Ingest 10 historical project drawing sets with existing QC logs.<br>• Execute automated evaluation harness against historical data. | • Custom CAD extraction rules.<br>• Historical benchmark report.<br>• Calibrated precision/recall metrics. | Recall $\ge 85\%$ on historical sets;<br>Zero parsing crashes on live PDFs. |
| **Week 3** | **Shadow-Mode Pilot**<br>• Deploy Review UI and n8n automated folder watcher.<br>• Run pipeline in parallel on 2 active commercial projects.<br>• QC engineers review AI findings alongside normal workflow. | • Interactive Review Portal live.<br>• Bluebeam & Excel export pipelines.<br>• Shadow-pilot discrepancy log. | Zero delivery deadline impact;<br>$\ge 80\%$ reviewer acceptance rate. |
| **Week 4** | **Tuning & Sign-Off**<br>• Analyze engineer reject reasons (`Design Intent`, `Duplicate`).<br>• Refine threshold gates for `Confirmed` vs `Probable`.<br>• Conduct QC team hands-on training workshop. | • Calibrated production pipeline.<br>• Engineer Operating Manual (SOP).<br>• Executive Pilot & ROI Sign-Off Report. | Formal Go/No-Go sign-off;<br>$\ge 35\%$ measured QC time savings. |

---

## 3. 90-Day Scaling & Commercialization Roadmap

Following successful 30-day pilot completion, the platform transitions into enterprise scale and commercial monetization:

| Phase | Timeline | Core Focus & Objectives | Target Milestone |
|---|:---:|---|---|
| **Phase 2: Enterprise Rollout** | **Days 31–60** | • Expand platform to 100% of internal AOP drafting teams.<br>• Direct integration with Autodesk Construction Cloud (ACC) via APS REST API.<br>• Automated BCF (BIM Collaboration Format) issue sync with Revit. | Full internal adoption;<br>100% of drawing sets processed through AI QC. |
| **Phase 3: Commercial Launch** | **Days 61–90** | • Package capability as an external **"Second Eye" AI-Assisted QA/QC Service**.<br>• Market to mid-market U.S. and Canadian architectural & engineering firms.<br>• Offer standalone drawing pre-checks at $450/set or $75/hr. | First 3 external commercial clients signed;<br>$15,000+ monthly recurring revenue. |

---

## 4. Comprehensive Infrastructure & Compute Cost Model

The platform is designed to be highly cost-effective, utilizing deterministic vector geometry parsing for 95% of analysis and reserving LLM tokens exclusively for bounded semantic scope checking.

### 4.1 Monthly Infrastructure Cost Breakdown (50 Drawing Sets / Month)

| Infrastructure Component | Technical Specification | Monthly Cost (USD) | Cost / Drawing Set |
|---|---|:---:|:---:|
| **API & Extraction Compute** | AWS t4g.xlarge / Hetzner CPX41 (4 vCPU, 16GB RAM) | $48.00 | $0.96 |
| **Database & Vector Storage** | Managed PostgreSQL (pgvector) + SQLite cache | $35.00 | $0.70 |
| **Object Storage (Drawings/Diffs)** | AWS S3 / Cloudflare R2 (100 GB storage + egress) | $12.00 | $0.24 |
| **Workflow Automation** | Self-hosted n8n instance (folder watchers, triggers) | $20.00 | $0.40 |
| **LLM Semantic API Tokens** | Claude 3.5 Sonnet / GPT-4o with Zero Data Retention (~120k tokens/set) | $45.00 | $0.90 |
| **Continuous Integration / Eval** | GitHub Actions / Automated benchmark regression runner | $15.00 | $0.30 |
| **Total Cloud Profile** | **Fully Managed Enterprise Cloud Setup** | **$175.00 / mo** | **$3.50 / set** |

### 4.2 Air-Gapped / On-Premise Defense Profile (Optional NDA Tier)

For defense, healthcare, or government clients prohibiting cloud LLM API transmission:
* **Hardware:** 1x Dedicated Workstation with NVIDIA RTX 4090 (24GB VRAM) or AWS G5.xlarge instance ($1.00/hr spot).
* **Model:** Quantized Llama-3-70B-Instruct (4-bit AWQ) hosted via vLLM with zero outbound internet access.
* **Monthly Compute Cost:** **~$180.00 / month** ($0.00 token cost, infinite local inference).

---

## 5. Engineering Resource Allocation & Staffing Matrix

Implementation requires minimal specialized engineering overhead, leveraging existing senior QC practitioners for domain validation:

| Team Role | Allocation (Month 1) | Allocation (Steady State) | Primary Responsibilities |
|---|:---:|:---:|---|
| **AI Process Optimization Lead (Sahil Navadiya)** | **50%** | **20%** | Architecture governance, prompt tuning, client integration, ROI reporting. |
| **Full-Stack / Python Backend Engineer** | **100%** | **30%** | Ingestion pipeline, APS API integration, database schema, review UI. |
| **Senior AEC Drafting / QC Specialist** | **25%** | **15%** | Ground-truth annotation, shadow-pilot verification, training workshops. |
| **IT & Security Administrator** | **10% (Week 1 only)** | **On-demand** | Zero Data Retention sign-off, network provisioning, SSO integration. |

---

## 6. Financial ROI & Operational Margin Expansion Model

The business case for the AEC Drawing Intelligence Platform is two-fold:
1. **Internal Cost Reduction:** Direct billable drafting hours saved during AOP production QC.
2. **Commercial Revenue Growth:** Transforming internal QC into a high-margin, sellable client service.

### 6.1 Internal QC Efficiency & Drafting Savings

* **Baseline Assumptions:**
  * Average commercial drawing package: **50 sheets**.
  * Baseline manual review time: **12 hours per package**.
  * Blended offshore drafting cost: **$22.00 / hour**.
  * Baseline QC cost per package: $12 \times \$22 = \mathbf{\$264.00}$.
  * AI-augmented QC cycle reduction: **40% to 50%** (saving 5 to 6 hours per set).

| Production Scenario | Monthly Drawing Sets | Monthly Hours Saved | Monthly Cost Savings | Annual Margin Expansion |
|---|:---:|:---:|:---:|:---:|
| **Conservative (25% reduction)** | 20 sets | 60 hours | $1,320 / mo | **$15,840 / year** |
| **Base Case (40% reduction)** | 35 sets | 168 hours | $3,696 / mo | **$44,352 / year** |
| **Target Scale (45% reduction)** | 50 sets | 270 hours | $5,940 / mo | **$71,280 / year** |
| **Optimistic (50% reduction)** | 70 sets | 420 hours | $9,240 / mo | **$110,880 / year** |

### 6.2 External "Second Eye" Commercial Service Monetization

Uppteam can package this capability as an independent AI-assisted drawing audit service for North American architectural firms facing domestic drafting staff shortages:
* **Pricing Model:** Flat-fee **$450 per drawing set review** (vs. domestic US rate of $1,200–$1,800).
* **Delivery Time:** **24-hour turnaround** (vs. 5 business days for domestic consultants).
* **Direct Production Cost:** ~$88 (3 hours offshore engineer review + $3.50 cloud compute).
* **Gross Profit per External Review:** **$362 per set (80.4% Gross Margin)**.

| External Client Adoption | Monthly Reviews | Monthly Gross Revenue | Direct Delivery Cost | Monthly Net Contribution |
|---|:---:|:---:|:---:|:---:|
| **Initial Launch (Month 3)** | 10 sets | $4,500 / mo | $880 / mo | **$3,620 / month** |
| **Ramp-Up (Month 6)** | 25 sets | $11,250 / mo | $2,200 / mo | **$9,050 / month** |
| **Mature Scale (Year 1)** | 50 sets | $22,500 / mo | $4,400 / mo | **$18,100 / month** |

### 6.3 Net ROI & Payback Period Summary

* **Initial 30-Day Investment:** ~$12,500 (Engineering time + setup + compute).
* **Monthly Operating Cost (Steady State):** ~$650 (Cloud infrastructure + maintenance).
* **Payback Period:** **2.8 Months** from production go-live.
* **Year 1 Net Economic Value:** **$85,000 to $145,000** (Combined internal savings and external revenue).
* **Year 1 Return on Investment (ROI):** **$\mathbf{480\%}$**.

---

## 7. Risk Assessment & Operational Mitigation Matrix

| Identified Risk | Impact | Probability | Proactive Mitigation Strategy |
|---|:---:|:---:|---|
| **Drawing Style & Title Block Variability** | Medium | Medium | Automated title block bounding box discovery with manual crop override fallback in UI. |
| **Client NDA & Intellectual Property Concerns** | High | Low | Enterprise Zero Data Retention agreements; on-premise air-gapped Llama-3 profile for strict clients. |
| **QC Engineer Adoption Resistance** | Medium | Medium | Involve lead QC engineers in Week 1 shadowing; emphasize AI as an "assistant", not a replacement. |
| **False Sense of Security (Over-Reliance)** | High | Low | System watermarks all deliverables as *"Potential Discrepancies - Requires EOR Verification"*. |
| **Cloud Service Outage / API Latency** | Low | Low | Fully deterministic core engine runs 100% locally; system degrades gracefully if LLM API is down. |

---

## 8. Governance, Legal Standard of Care & Compliance

The platform strictly adheres to the legal requirements governing professional architectural and engineering practice:
1. **Preservation of Professional Standard of Care:** The platform explicitly **never** marks drawings as *"Approved"*, *"Certified"*, or *"Stamped"*. All findings are designated as *"Potential Discrepancies"* for review.
2. **Licensed Professional Sign-Off:** The licensed Architect of Record (AOR) or Engineer of Record (EOR) retains sole legal authority to incorporate or dismiss findings.
3. **Immutable Quality Audit Trail:** All engineer decisions, comments, and dismissal rationales are permanently recorded in `review_log.jsonl` to ensure full compliance with ISO 9001 drafting quality standards.
