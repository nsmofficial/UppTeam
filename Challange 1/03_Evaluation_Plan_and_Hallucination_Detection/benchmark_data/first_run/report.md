# Evaluation report

All documents are synthetic (fictional project). Seed 0 = development set (all 24 defect kinds, used while building the rules). Seeds 1-20 = test sets generated with randomised defects, targets, numbering and bay sizes (same generator family, so this measures robustness to variation, not to unseen drafting styles). Clean sets = negative controls with zero seeded defects.

## Headline

| Split | Sets | Seeded defects | Detected | Shipped findings | False positives | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| dev | 1 | 24 | 24 | 29 | 0 | 1.000 | 1.0 | 1.0 |
| test | 20 | 241 | 240 | 289 | 5 | 0.983 | 0.996 | 0.989 |
| clean | 5 | 0 | 0 | 0 | 0 | 1.000 | - | - |

## Test split by finding type

| Type | Defects | Detected | Recall | FP | Precision |
|---|---|---|---|---|---|
| missing_info | 81 | 81 | 1.000 | 0 | 1.000 |
| quantity_mismatch | 42 | 42 | 1.000 | 0 | 1.000 |
| dimension_conflict | 17 | 17 | 1.000 | 0 | 1.000 |
| cross_discipline_conflict | 46 | 46 | 1.000 | 0 | 1.000 |
| spec_conflict | 25 | 25 | 1.000 | 0 | 1.000 |
| revision_issue | 19 | 18 | 0.947 | 0 | 1.000 |
| tag_conflict | 11 | 11 | 1.000 | 5 | 0.688 |

## Calibration by tier (test split)

| Tier | Findings | Correct | Precision |
|---|---|---|---|
| confirmed | 225 | 220 | 0.978 |
| probable | 64 | 64 | 1.0 |

## Evidence and hallucination controls

- Evidence localisation (test): 222/237 detected defects have an evidence anchor on the ground-truth location (0.937).
- Citation verification (all splits): every shipped finding carries only re-verified anchors; anchors checked 770, verified 769, findings rejected by the gate 0.
- Negative controls: 0 shipped findings on 5 clean sets (every one would be a false positive).
- Abstentions (needs_review, test): 20 items, 20 on deliberate ambiguity traps ('TYP.' without a count). Trap violations (confident claims on traps): 0.
- Determinism: 2 runs on the dev set, identical output = True.
- Hallucination injection (mock LLM on dev set): 25 fabricated conflicts injected across 5 spec-section requests; 24 stopped by the evidence gate, 1 shipped (catch rate 0.96). 3/3 correct conflicts passed and corroborated the rule findings.

Mean run time per set: 0.77 s (max 0.92 s, 26 sets).

## Missed defects (test)

- seed_10: S10-10 rev_unclouded: A-601 door 205A width changed 3'-0" -> 3'-6" in Rev B without a revision cloud.

## False positives

- seed_07: F-008 rule:TAG-001 Potential discrepancy: door number 106 is tagged 2 times on the plans; door numbers must be unique.
- seed_07: F-009 rule:TAG-001 Potential discrepancy: door number 109 is tagged 2 times on the plans; door numbers must be unique.
- seed_07: F-010 rule:TAG-001 Potential discrepancy: door number 110 is tagged 2 times on the plans; door numbers must be unique.
- seed_08: F-016 rule:TAG-001 Potential discrepancy: door number 110 is tagged 2 times on the plans; door numbers must be unique.
- seed_09: F-010 rule:TAG-001 Potential discrepancy: door number 110 is tagged 2 times on the plans; door numbers must be unique.
