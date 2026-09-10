# POINTSIM-ADV-001 — WTA Mechanistic Residual Adversary

Status: **pre-registered before result inspection**.

## Question

POINTSIM-001 found that raw point-to-match mechanics were inferior to a same-input statistical mapping on both tours, but that POINTSIM added a small historical signal beyond the WTA Core benchmark. The current WTA probability architecture is stronger than Core: strict-Core-geometry historical alignment with Identity calibration.

POINTSIM-ADV-001 therefore asks one narrow question:

> Does the frozen POINTSIM probability add incremental probability quality beyond the current WTA historical-alignment probability?

This is the only promotion question in this experiment.

## Scope

- WTA only for promotion.
- Development data: 2000–2025 only.
- The spent partial-2026 holdout is forbidden.
- Walkovers excluded; retirements excluded, matching the upstream development experiments.
- No changes to POINTSIM scoring mechanics, serve/return state, Core features, Genome geometry, k, or historical-alignment model.

ATP is not rerun as a candidate because POINTSIM-001 already failed both standalone and incremental ATP gates. Avoiding unnecessary ATP retesting reduces researcher degrees of freedom.

## Frozen inputs

For each common chronological OOS WTA match:

1. `p_alignment`: the WTA strict-Core-geometry historical-alignment probability from the merged GENOME-ADV architecture.
2. `p_pointsim`: the raw frozen POINTSIM-001 mechanistic probability for the same match.
3. outcome label.

Rows are joined by immutable `match_id`. Any duplicate, missing, or outcome-disagreeing join fails closed.

## Models

### A0 — incumbent

Raw `p_alignment` on the common matched population. Diagnostic only.

### A1 — alignment-only recalibration control

For each outer test year, fit on earlier matched OOS rows only:

`StandardScaler -> LogisticRegression(C=1.0)`

Input:

- `logit(p_alignment)`

This control prevents ordinary recalibration of the incumbent from being credited to POINTSIM.

### A2 — alignment + POINTSIM challenger

For each outer test year, fit on the exact same earlier matched OOS rows:

`StandardScaler -> LogisticRegression(C=1.0)`

Inputs:

- `logit(p_alignment)`
- `logit(p_pointsim)`

A1 and A2 use identical outcomes, train years, future rows, regularization, preprocessing, and probability scoring.

No interaction terms, nonlinear transformations beyond logit, model selection, weight tuning, recency weighting, or calibrator search are allowed in POINTSIM-ADV-001.

## Chronology

For outer year `Y`:

- both upstream probability streams must themselves be OOS/chronological;
- A1/A2 training rows must have `year < Y`;
- year-Y outcomes cannot influence A1/A2 preprocessing, coefficients, or intercepts;
- the matched test population for A1 and A2 must be identical.

Minimum meta-training rows: **1,000**.

## Primary metrics

- Brier score
- binary log loss

Secondary diagnostics:

- accuracy
- ECE-10
- A2 standardized coefficients
- absolute `p_alignment - p_pointsim` disagreement quintiles

Accuracy/ECE cannot override failure of the primary gate.

## Promotion gate

A2 is promoted as a WTA conditional component only if **all** are true:

1. aggregate A2 Brier < A1 Brier;
2. aggregate A2 log loss < A1 log loss;
3. A2 jointly beats A1 on both Brier and log loss in at least **60%** of evaluated outer years;
4. aggregate 2021–2025 A2 Brier <= A1 Brier;
5. aggregate 2021–2025 A2 log loss <= A1 log loss.

Any failure means POINTSIM remains a research-only WTA signal and is not added to the current independent probability candidate.

No threshold may be relaxed after results.

## Interpretation

If the gate passes:

- conclude only that the frozen mechanistic probability contains incremental WTA information beyond the current historical-alignment probability under historical development data;
- classify POINTSIM as a **B/conditional WTA component** pending genuinely later forward confirmation;
- do not claim the standalone simulator is good; H-018A remains failed.

If the gate fails:

- keep the current WTA historical-alignment probability unchanged;
- retain POINTSIM-001's Core-level result as an interesting but redundant historical signal;
- do not tune scoring rules or simulator parameters on this failed population.

## Non-claims

This experiment does not test sportsbook prices, no-vig edge, EV, CLV, ROI, staking, or profitability. It does not provide independent forward confirmation. The partial-2026 holdout remains spent and unavailable for rescue testing.
