# DYNAMIC-STATE-DEVELOPMENT-001

Status: **registered development-only comparison; no protected or prospective claim**

## Scientific question

Does replacing the current fixed-learning-rate opponent-adjusted serve/return state with
the new uncertainty-aware dynamic state improve match-win probability forecasts before
adding broader target context or residual pattern machinery?

This experiment deliberately tests the simplest interpretation of the dynamic-state
hypothesis first.

## Procedures

Both procedures use the same match-win mapping:

- overall pre-date Elo probability converted to logit;
- one opponent-adjusted serve/return matchup edge;
- median imputation + missingness indicators;
- standardization;
- logistic regression with the existing `FeatureProbabilityModel` defaults.

The only difference is the serve/return state estimator.

### FIXED-STATE

Uses the existing `walk_forward_serve_return` state and
`ServeReturnConfig(base_service_win_rate=0.62, learning_rate=0.50,
reference_points=60)`.

### DYNAMIC-STATE

Uses `walk_forward_dynamic_serve_return` with the parameters already exercised by the
known-truth state-shift benchmark:

- base service win rate 0.62;
- initial variance 0.50;
- process variance per day 0.001;
- mean-reversion half-life 365 days;
- point-information weight 0.10;
- minimum variance 0.02;
- maximum variance 1.50.

The dynamic uncertainty values are **not** model inputs in this first comparison. This
isolates state-estimation quality before testing whether uncertainty itself contains
incremental predictive information.

## Historical legality boundary

This first development test uses only state derived from prior match outcomes/statistics:

- Elo;
- fixed serve/return state;
- dynamic serve/return state.

It intentionally excludes target-row:

- ranking/ranking points;
- age;
- hand/height/IOC;
- surface;
- round;
- seed/entry;
- tournament context.

Those fields remain unresolved for canonical v2 target-row use under
`historical_availability_audit_001`.

The source's date-only chronology remains atomic: same-date matches cannot update one
another.

## Chronological evaluation

Default test years are 2015–2025.

For each test year `Y`:

1. build all states chronologically;
2. fit each procedure's logistic mapping using only rows from years `< Y`;
3. predict every eligible row in year `Y`;
4. never refit using outcomes from year `Y` before scoring that year.

The historical universe is already research-exposed. Therefore the result is
**DEVELOPMENT_ONLY** even though predictions are chronological.

It must not be described as independent confirmation.

## Metrics and dependence

Primary descriptive comparisons:

- Brier score;
- log loss.

Positive improvement means the dynamic state has lower loss.

Dependence-aware inference uses ISO calendar-week blocks:

- paired block bootstrap, 95% interval, 10,000 resamples;
- paired block sign-flip test, 20,000 resamples;
- fixed inference seed 20260914.

Calendar-week blocking is registered before results and must not be changed because a
different block definition gives a more favorable answer.

## Interpretation

Possible outcomes are all scientifically legitimate:

- **dynamic improves both scores**: state estimation deserves deeper development;
- **no improvement**: synthetic responsiveness did not translate to match-win information;
- **worse**: the current uncertainty/process model is misspecified or overreactive;
- **mixed**: investigate calibration/state behavior without calling the challenger superior.

This experiment cannot promote a v2 model. A surviving procedure must later enter a
registered search family and protected evaluation under the Workbench controls.

It establishes no betting edge and does not modify TGE-Independent-v1.
