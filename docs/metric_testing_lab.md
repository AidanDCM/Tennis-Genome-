# Metric Testing Laboratory

Every proposed metric must pass the same laboratory. The question is not merely whether it correlates with winning, but whether it provides **incremental, stable, pre-match predictive information** beyond what the current model already knows.

## Standard experiment template

For metric `X`:

### A. Data audit
- definition
- units
- source
- timestamp semantics
- historical availability
- missingness rate
- missingness mechanism
- reliability grade
- known-before-T0 check

### B. Raw relationship
Evaluate unadjusted relationship with:
- match outcome
- point/game/set performance where relevant
- expected-vs-actual residuals

Use plots/bins/splines rather than assuming linearity.

### C. Redundancy / correlation
Measure relationship to existing features and feature families.

Examples:
- Pearson/Spearman for exploratory numeric dependence
- mutual information where useful
- correlation clusters
- variance inflation diagnostics for interpretable linear models
- model-based redundancy tests

### D. Confounder map
Document plausible alternative explanations before interpreting the result.

### E. Add-one test

`M1 = M_baseline + X`

Compare chronologically on:
- log loss
- Brier score
- calibration
- accuracy
- subgroup stability

### F. Remove-one / ablation test

`M_minus_X = M_full - X`

If removal produces no meaningful degradation, `X` may be redundant.

### G. Unique signal test

When `X` is strongly explained by other variables, test the component not captured by them.

Conceptually:

`X_unique = X - E[X | controls]`

Then evaluate whether `X_unique` predicts future residual performance.

Important: use cross-fitting/chronological fitting where necessary so residualization itself does not leak evaluation information.

### H. Interaction tests

Only test plausible or registered interactions, such as:
- age × fatigue
- heat × fatigue
- previous workload × rest
- surface × serve strength
- handedness × opponent profile

Do not brute-force unlimited interactions without multiple-testing control.

### I. Matched / neighborhood comparison

Use Match Fingerprints to compare otherwise similar historical states that differ materially in `X`.

This is a predictive robustness tool, not automatic causal proof.

### J. Stability

Repeat effect estimation across chronological periods and relevant strata:
- ATP/WTA
- surface
- tournament level
- ranking band
- age band
- favorites/underdogs
- data-quality tier

### K. Uncertainty

Store:
- point estimate
- confidence/credible interval as appropriate
- sample size
- number of independent periods validated
- stability score

### L. Promotion decision

A metric report card should contain:

```yaml
metric_id: rest_hours
status: candidate
raw_signal: moderate
incremental_logloss_delta: null
incremental_brier_delta: null
calibration_delta: null
main_effect: unknown
validated_interactions: []
validation_windows_passed: 0
sample_size: null
reliability_grade: null
metric_grade: C
notes: "Not yet tested"
```

## Family-level testing

Closely related variables are tested both individually and as a family.

Example serve family:
- serve points won
- first-serve points won
- second-serve points won
- hold rate
- ace rate
- double-fault rate

Questions:
1. Does the family improve the baseline?
2. Which compact subset retains most of the improvement?
3. Which variables add unique information?
4. Are effects stable across surfaces/opponents?

## Residual target

A central research target is:

`performance_residual = actual_performance - expected_performance_from_baseline`

A metric becomes especially interesting when it explains future residuals after baseline strength is already accounted for.

Examples of performance targets may include:
- match win indicator vs predicted probability
- point win percentage residual
- serve/return performance residual
- games/sets residuals where appropriate

## Required artifacts per experiment

Each experiment should produce:
- hypothesis record
- exact data cutoff
- feature definitions
- train/validation/test windows
- code version / commit
- baseline metrics
- candidate metrics
- delta metrics
- confidence intervals
- subgroup results
- plots/tables
- adversarial review
- promotion/rejection decision

## Anti-self-deception gate

Before promotion ask:

1. Could this be leakage?
2. Could another correlated metric explain it?
3. Did we search many variants before selecting this one?
4. Does the effect survive future periods?
5. Does it survive an untouched holdout?
6. Is the gain meaningful, not merely statistically detectable?
7. Does it improve probability quality, not only accuracy?
8. Does it survive reasonable preprocessing/model choices?
9. Is it concentrated in one tiny subgroup?
10. Would we still believe it if the direction were opposite our intuition?
