# MARKET-EDGE-ADV-001 — Market + Core Adversarial Incrementality Test

Status: **PREREGISTERED BEFORE LICENSED BETFAIR OUTCOME INSPECTION**

## Purpose

MARKET-EDGE-ADV-001 is a deliberately harder follow-up to `MARKET-EDGE-001`.

`MARKET-EDGE-001` asks whether frozen Profile Gap and Genome signals add predictive information beyond Betfair closing prices after chronological market recalibration.

This experiment asks the stricter question:

> Does either signal still add information after the adversary is allowed to use both Betfair closing prices and Tennis Genome Strict Core probability?

This experiment is additive. It does **not** rewrite, replace, retune, or reinterpret the frozen `MARKET-EDGE-001` protocol after results.

No licensed Betfair outcomes may be inspected to choose this design, its windows, its transformations, or its gates.

## Preconditions

Before this experiment is eligible to run:

1. `MARKET-HIST-001` reconstruction must exist from licensed ADVANCED or PRO Tennis MATCH_ODDS data.
2. `MARKET-HIST-QA-001` must classify the relevant tour as `ELIGIBLE_CONFIRMATORY`.
3. The licensed source bundle, MARKET-HIST artifact, canonical tables, and frozen model artifacts must have immutable hashes/provenance.
4. `POWER-MDE-001` should be run outcome-blind first and retained as a feasibility diagnostic.
5. All probability/signal artifacts used here must have been generated without Betfair information and without post-2025 tuning.

If a tour fails MARKET-HIST-QA coverage, its results are exploratory only even if this code can technically run.

## Frozen four-claim family

The confirmatory family remains four claims:

1. ATP Profile Gap beyond Market + Core;
2. WTA Profile Gap beyond Market + Core;
3. ATP Genome beyond Market + Core;
4. WTA Genome beyond Market + Core.

Each claim is tested against the **same model architecture** for its Market + Core control.

Profile Gap and Genome are not tested sequentially against one another. A Profile result cannot make the Genome bar easier or harder, and vice versa.

## Immutable input definitions

### Betfair market probability

Use the exact executable `CLOSE_PREPLAY` two-runner no-vig probability from the already-frozen MARKET-HIST / MARKET-EDGE input path:

`exchange_mid_implied_proportional_v1`

No last-traded-price substitution is allowed.

### Strict Core probability

Use already-generated honest out-of-sample Strict Core probability, never a Core model retrained on Betfair outcomes.

Frozen source fields:

- Profile Gap claims: `PROFILE-GAP-001.predictions[].strict_core_probability`;
- Genome claims: `GENOME-ADV-001.predictions[].core_probability_a`.

The loader must verify experiment ID, tour, uniqueness of `match_id`, finiteness, and probability bounds.

If a claim's frozen model artifact and Betfair market artifact do not share a match, that row is unavailable for that claim. Missing Core values must not be imputed from later models or reconstructed using market outcomes.

### Frozen tennis signals

Use the exact signal fields already allowed by MARKET-EDGE-001:

- ATP Profile Gap: `profile_gap_match`;
- WTA Profile Gap: `profile_gap_match`;
- ATP Genome: `full_neighbor_residual`;
- WTA Genome: `core_neighbor_residual`.

No feature selection, sign flip, nonlinear transform search, clipping search, interaction search, or signal blending is allowed after outcome inspection.

## Common evaluation population

For each claim, intersect by canonical `match_id`:

- executable Betfair CLOSE_PREPLAY row;
- completed non-retirement/non-walkover outcome;
- canonical match year;
- frozen Strict Core probability;
- frozen signal value.

The Market + Core control and its signal challenger must be scored on **identical rows**.

Each claim is tour-specific. Duplicate match IDs or wrong-tour rows fail closed.

No row after 2025 is allowed in development evaluation.

## Primary chronological design

Use expanding-year walk-forward evaluation.

For evaluation year `Y`:

- training rows must have year `< Y`;
- target-year outcomes may not influence fitting, scaling, optimizer initialization, exclusions, or transforms;
- require at least 1,000 earlier matched rows;
- evaluate every eligible row in year `Y` on the fitted earlier-year model;
- carry fitted parameters into an immutable prediction ledger.

The first eligible evaluation year is determined mechanically by the 1,000-row requirement, not selected after results.

## Probability clipping

Before a logit transform, clip both market and Core probabilities to:

`[1e-6, 1 - 1e-6]`

This matches the frozen MARKET-EDGE numerical boundary.

## Model ladder

Let:

- `m = logit(p_market_close)`;
- `c = logit(p_core)`;
- `s = z_train(signal)`, where signal mean and population SD are fit on earlier rows only.

### M0 — Market-only diagnostic

`logit(p) = alpha + gamma_m * m`

M0 exists to quantify how much the stronger control changes the bar relative to MARKET-EDGE-001. It is diagnostic here, not the primary adversary.

### M1 — Market + Core control

`logit(p) = alpha + gamma_m * m + gamma_c * c`

M1 is the confirmatory control for all four claims.

### M2 — Market + Core + Profile Gap

For Profile Gap claims only:

`logit(p) = alpha + gamma_m * m + gamma_c * c + beta * s_profile`

### M3 — Market + Core + Genome

For Genome claims only:

`logit(p) = alpha + gamma_m * m + gamma_c * c + beta * s_genome`

The Profile and Genome challengers are fitted separately against M1.

### Optional joint diagnostic

A `Market + Core + Profile Gap + Genome` model may be reported only as a separately labeled exploratory diagnostic on rows where both signals exist.

It is not part of the four primary claims and cannot rescue a failed Profile or Genome claim.

## Fitting

Use deterministic unpenalized Bernoulli logistic maximum likelihood with analytic gradient and BFGS, consistent with MARKET-EDGE-001's fitting philosophy.

Initialization is frozen:

- M0: `[0, 1]`;
- M1: `[0, 1, 0]`;
- signal challenger: `[0, 1, 0, 0]`.

Signal standardization uses earlier training rows only.

No optimizer restart grid, regularization tuning, feature scaling search, or alternative solver selection may be chosen from real outcomes.

If the design is non-identifiable, has zero/non-finite signal SD, or optimization fails/non-finite parameters result, the affected evaluation year fails closed and the error must be reported. It must not silently fall back to a simpler model.

## Primary comparisons

The confirmatory comparison for each signal is:

**M1 Market + Core vs its corresponding signal challenger**

on the exact same chronological predictions.

Report M0 and raw market probability as context, but neither is the promotion denominator for MARKET-EDGE-ADV-001.

Primary proper scores:

- Brier score;
- binary log loss.

Supporting metrics:

- accuracy;
- ECE with 10 bins;
- McNemar paired accuracy test;
- fitted market/Core/signal coefficients;
- market-Core correlation and signal correlation diagnostics where available.

## Statistical inference

For challenger minus M1 comparisons, reuse the MARKET-EDGE paired inference design:

- paired bootstrap CI for mean Brier improvement;
- paired bootstrap CI for mean log-loss improvement;
- two-sided paired sign-flip/permutation p-value for Brier losses;
- two-sided paired sign-flip/permutation p-value for log losses;
- McNemar exact test for accuracy disagreements.

Use deterministic experiment-derived seeds.

Primary evidence remains proper scores, not accuracy.

## Multiplicity

Apply Holm family-wise error control separately to the four Brier p-values and the four log-loss p-values at family alpha 0.05.

A claim must survive Holm in **both** proper-score families.

No checkpoint, subgroup, coefficient, joint-model, or robustness-window analysis is included in this four-claim family unless separately preregistered.

## Stability gates

For each claim, pre-Holm candidate status requires all of:

1. aggregate M1-to-challenger Brier improvement > 0;
2. aggregate M1-to-challenger log-loss improvement > 0;
3. 95% paired-bootstrap lower bound > 0 for Brier improvement;
4. 95% paired-bootstrap lower bound > 0 for log-loss improvement;
5. challenger improves both Brier and log loss in at least 60% of evaluated calendar years;
6. aggregate 2021-2025 Brier improvement > 0;
7. aggregate 2021-2025 log-loss improvement > 0;
8. no single calendar year contributes more than 50% of absolute total Brier improvement magnitude;
9. no single calendar year contributes more than 50% of absolute total log-loss improvement magnitude;
10. no chronology, identity, provenance, or optimizer-integrity violation.

Final `market_core_incremental_pass` additionally requires Holm-adjusted p < 0.05 for both Brier and log-loss families.

These thresholds mirror the spirit of MARKET-EDGE-001 so a stronger control, rather than a friendlier decision rule, is the substantive change.

## Primary interpretation

A passing claim may be described as:

> historically market-and-Core-incremental on the licensed 2000-2025 development sample.

It must not be described as independently forward-confirmed, causal, guaranteed profitable, or sufficient for live staking.

If a signal passed MARKET-EDGE-001 but fails MARKET-EDGE-ADV-001, the correct interpretation is that its market incrementality was not isolated from information already present in Strict Core.

If it passes both, the evidence for genuinely distinct tennis information is materially stronger.

## Trailing-three-year robustness analysis

Because exchange efficiency and model relationships may drift, run a secondary rolling robustness ledger.

For evaluation year `Y`, use only rows from calendar years:

`Y-3, Y-2, Y-1`

and still require at least 1,000 total training rows. Target-year outcomes remain forbidden.

Use the exact same M1/challenger forms, transforms, solver, and signal standardization rules.

This rolling analysis is **not** a second optimization path and is not substituted for the expanding-window primary result.

Report:

- aggregate Brier/log deltas;
- annual joint proper-score direction;
- 2021-2025 direction where available;
- coefficient drift;
- coverage relative to the primary ledger.

A contradiction between primary and trailing-window direction is reported as a nonstationarity warning. It does not permit choosing whichever window looks better after the fact.

## MARKET-EDGE-001 relationship

Both experiments must remain in the permanent record.

- MARKET-EDGE-001 answer: signal vs recalibrated closing market.
- MARKET-EDGE-ADV-001 answer: signal vs recalibrated closing market **plus frozen Strict Core probability**.

A negative stronger-adversary result does not retroactively alter the original frozen result; it narrows its interpretation.

## No decision-policy optimization here

MARKET-EDGE-ADV-001 remains a probability-quality experiment.

Do not use its outcomes to search:

- edge thresholds;
- stake sizes;
- Kelly fractions;
- bookmaker/exchange selection rules;
- probability buckets to bet;
- checkpoint timing;
- commission assumptions;
- selective-PASS thresholds.

Economic policy research remains downstream and separately preregistered.

## Explicit non-claims

This experiment does not prove future profitability, CLV persistence, fill quality, capacity, robustness to limits, or future calibration.

The 2026 holdout is already spent by earlier work and remains forbidden for development. Genuine future data are still required for final forward confirmation.
