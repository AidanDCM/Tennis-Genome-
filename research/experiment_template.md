# Experiment Template

Copy this file into `research/installment_XX/experiments/EXP-XXX-name.md` before final validation.

## Identity

- Experiment ID:
- Title:
- Created:
- Owner:
- Hypothesis ID:
- Code branch/commit:

## Question

What precise predictive question is being tested?

## Status before test

`PROPOSED | REGISTERED | RUNNING`

## Metric / feature family

Definition, units, transformation, source, timestamp semantics.

## Expected direction

Optional. State before validation.

## Plausible mechanism

Why could this feature contain pre-match information?

## Alternative explanations / confounders

List them explicitly before running the final test.

## Data legality

- earliest source availability:
- T0 rule:
- missingness:
- data-quality exclusions:
- retirement/walkover policy:

## Dataset

- manifest:
- tour(s):
- surfaces:
- date range:
- discovery range:
- validation range:
- untouched test range:
- N:

## Baseline

Exact accepted model/version the candidate must improve.

## Candidate

Exact difference from baseline.

## Preprocessing

All fit operations and where they are fit chronologically.

## Primary metrics

- log loss
- Brier score
- calibration

## Secondary metrics

- accuracy
- subgroup stability
- coverage/selective risk if relevant

## Add-one result

Baseline vs baseline + candidate.

## Remove-one / ablation result

Full model vs full model without candidate.

## Unique-signal / residual test

Required when feature is strongly correlated with accepted features.

## Interaction tests

Only pre-registered/plausible interactions here.

## Multiple-testing family

State how multiplicity is controlled.

## Chronological fold results

| Fold | Baseline log loss | Candidate log loss | Δ | Brier Δ | Calibration notes | N |
|---|---:|---:|---:|---:|---|---:|

## Subgroups

Report all pre-registered groups, not only winners.

## Uncertainty

Point estimate, interval, paired uncertainty, effective sample size.

## Adversarial review

Answer:
1. Leakage possibility?
2. Confounding/redundancy?
3. Hyperparameter/search degrees of freedom?
4. Temporal instability?
5. Tiny subgroup dependence?
6. Implausible effect size?
7. Alternative preprocessing result?
8. Does future holdout agree?

## Decision

`ACCEPTED_CORE | ACCEPTED_CONDITIONAL | NEEDS_REPLICATION | REJECTED`

## Metric grade

`A | B | C | D`

## What we learned

Record useful negative findings too.
