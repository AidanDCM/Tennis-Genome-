# Calibration + Selective Prediction — Pre-Registered Protocol

Status: **pre-registered before calibration/selective-prediction results are inspected**

Core dependency: merged Core v1 milestone `c377d5b8eac4016d58ad02e05851b2765166c8ce`.

The sealed partial-2026 holdout has already been inspected and is therefore **spent**. It must not be reused as independent validation for any calibrator, confidence rule, or model change developed here.

This experiment uses 2000–2025 research history for chronological development only. Any promoted post-Core-v1 change requires genuinely later forward confirmation.

---

## Questions

1. Can post-hoc probability calibration improve the meaning of Core v1 probabilities without degrading Brier/log-loss quality?
2. How does predictive performance change as the engine abstains from lower-confidence matches?
3. Does disagreement between independently structured probability views identify uncertain matches beyond probability distance from 50% alone?

This experiment does **not** test sportsbook value or profitability.

---

## Base model

Use the frozen tour-specific **strict A-only Core v1 feature specification** from `models/core_v1_spec.py`.

For every outer test year `Y`:
1. fit preprocessing/model coefficients using matches strictly before `Y`;
2. predict all eligible matches in `Y`;
3. preserve the same source-date state-freezing rule used by prior experiments.

These year-`Y` probabilities are out-of-sample base probabilities.

No random train/test split is permitted for the primary analysis.

---

## Nested calibration discipline

A calibrator for outer year `Y` may train **only on earlier out-of-sample predictions** whose match outcomes are already historical relative to `Y`.

It may not train on:
- in-sample predictions from the same base-model fit;
- year `Y` outcomes;
- future years;
- the spent 2026 holdout.

Minimum calibrator history: 1,000 prior OOF predictions containing both outcome classes.

Primary calibration-history policy: **expanding prior OOF history**.

No calibration-window tuning is allowed in the primary result.

---

## Registered calibrators

### Identity
No post-hoc calibration. This is the control.

### Platt
Fit logistic regression to the logit of prior OOF probabilities.

### Beta calibration
Fit logistic regression to:
- `log(p)`;
- `-log(1-p)`.

This allows asymmetric correction near the probability boundaries.

### Isotonic
Fit a monotonic isotonic regression on prior OOF probability/outcome pairs.

All input probabilities are clipped only for numerical stability, never for result optimization.

---

## Calibration evaluation

Primary:
1. Brier score;
2. binary log loss.

Calibration diagnostics:
- ECE-10;
- mean predicted probability vs observed rate;
- calibration intercept/slope when estimable;
- reliability buckets.

Secondary:
- accuracy, recognizing monotonic calibration should not be judged primarily by winner classification.

Report:
- aggregate ATP/WTA separately;
- year-by-year;
- recent 2021–2025 block;
- probability buckets.

---

## Calibration promotion rule

A post-hoc calibrator may be considered a production candidate only if, versus identity:
1. aggregate log loss does not worsen;
2. aggregate Brier does not worsen;
3. ECE-10 improves materially;
4. there is no obvious 2021–2025 collapse;
5. gains are not driven by one isolated season.

If no registered calibrator satisfies the rule, **identity remains the production choice**. A null result is acceptable.

No calibrator receives final forward-validation status from this experiment because 2026 is already spent.

---

# Selective prediction / abstention

Selective prediction measures what happens when the engine is allowed to say **PASS** on less certain matches.

This remains a prediction-confidence experiment, not a betting policy.

## Probability-confidence rule

Primary confidence score:

`abs(calibrated_probability - 0.5)`

Evaluate fixed coverage levels:
- 100%
- 75%
- 50%
- 25%
- 10%
- 5%

At each coverage level report:
- N;
- accuracy;
- Brier;
- log loss;
- ECE-10;
- mean predicted favorite probability;
- realized favorite win rate.

Do not tune coverage thresholds after seeing outcomes.

---

## Model-disagreement diagnostic

Generate three chronological probability views on the same match population:
1. Elo-only;
2. strict A-only Core v1;
3. A+B diagnostic model.

Define raw disagreement as:

`max(probabilities) - min(probabilities)`

Report performance by disagreement quantile and jointly with probability confidence.

Primary question: do high-disagreement matches show worse calibration/probability quality than low-disagreement matches?

Disagreement is diagnostic in this installment. It is not automatically promoted to a hard PASS rule.

---

## Anti-self-deception rules

- No 2026 reuse for tuning or independent confirmation.
- No post-result changes to coverage percentages.
- No selecting only surfaces/tours/years that flatter a calibrator.
- Every candidate is compared on the same eligible match population.
- Preserve rejected/no-effect calibrators in the findings ledger.
- Accuracy cannot override worse Brier/log loss.
- A smoother-looking reliability chart is not sufficient evidence.

---

## Deliverables

1. reusable calibrator implementations;
2. nested chronological calibration evaluator;
3. calibration report for ATP/WTA;
4. selective-prediction coverage curves;
5. disagreement diagnostics;
6. accepted/rejected calibration decision;
7. explicit statement that later forward data is still required before post-Core-v1 changes are independently validated.
