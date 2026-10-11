# Evaluation report

All documents are synthetic (fictional project). Seed 0 = development set (all 24 defect kinds, used while building the rules). Seeds 1-20 = test sets generated with randomised defects, targets, numbering and bay sizes (same generator family, so this measures robustness to variation, not to unseen drafting styles). Clean sets = negative controls with zero seeded defects.

## Headline

| Split | Sets | Seeded defects | Detected | Shipped findings | False positives | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| dev | 1 | 24 | 24 | 29 | 0 | 1.000 | 1.0 | 1.0 |
| test | 20 | 241 | 241 | 286 | 0 | 1.000 | 1.0 | 1.0 |
| holdout | 20 | 257 | 257 | 303 | 0 | 1.000 | 1.0 | 1.0 |
| clean | 5 | 0 | 0 | 0 | 0 | 1.000 | - | - |

## Holdout split by finding type

| Type | Defects | Detected | Recall | FP | Precision |
|---|---|---|---|---|---|
| missing_info | 94 | 94 | 1.000 | 0 | 1.000 |
| quantity_mismatch | 46 | 46 | 1.000 | 0 | 1.000 |
| dimension_conflict | 18 | 18 | 1.000 | 0 | 1.000 |
| cross_discipline_conflict | 35 | 35 | 1.000 | 0 | 1.000 |
| spec_conflict | 36 | 36 | 1.000 | 0 | 1.000 |
| revision_issue | 18 | 18 | 1.000 | 0 | 1.000 |
| tag_conflict | 10 | 10 | 1.000 | 0 | 1.000 |

## Calibration by tier (holdout split)

| Tier | Findings | Correct | Precision |
|---|---|---|---|
| confirmed | 229 | 229 | 1.0 |
| probable | 74 | 74 | 1.0 |

## Evidence and hallucination controls

- Evidence localisation (holdout): 251/251 detected defects have an evidence anchor on the ground-truth location (1.0).
- Citation verification (all splits): every shipped finding carries only re-verified anchors; anchors checked 1509, verified 1506, findings rejected by the gate 0.
- Negative controls: 0 shipped findings on 5 clean sets (every one would be a false positive).
- Abstentions (needs_review, holdout): 20 items, 20 on deliberate ambiguity traps ('TYP.' without a count). Trap violations (confident claims on traps): 0.
- Determinism: 2 runs on the dev set, identical output = True.
- Hallucination injection (mock LLM on dev set): 25 fabricated conflicts injected across 5 spec-section requests; 25 stopped by the evidence gate, 0 shipped (catch rate 1.0). 3/3 correct conflicts passed and corroborated the rule findings.
- Known limit, measured: 5 *real* quotes attached to *false* claims were also injected; 3 passed the gate (as tier probable). The gate proves a citation exists where cited; it cannot prove the citation supports the claim. That is why LLM findings are never 'confirmed' and are routed to an engineer, and why the reviewer reject rate is tracked in production.

Mean run time per set: 0.78 s (max 0.92 s, 46 sets).
