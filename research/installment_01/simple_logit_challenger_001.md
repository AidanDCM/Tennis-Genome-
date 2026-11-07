# SIMPLE-LOGIT-CHALLENGER-001

Status: research implementation; no forward predictions registered.

This challenger was motivated by an external exploratory replay that had already inspected
the partial-2026 Core holdout. The 2026 slice and the external feature selection are spent
development evidence. This implementation is an adaptation to Tennis Genome's canonical
feature state, not a reproduction of that replay's coefficients or reported scores.

## Fixed candidate arms

- `BASE`: 14 named canonical foundational differences in
  `simple_logit_challenger.BASE_FEATURES`. No target-match rank or rank points.
- `RANK`: the same 14 differences plus `log(rank_b/rank_a)` and
  `log(points_a/points_b)`. Both players must have positive values; incomplete rows are
  excluded from *every* model in the paired ranking comparison, never zero-filled.

Both arms use mirrored player rows, no intercept, no mean centering, training-fold standard
deviation scaling, and logistic regression with `C=0.5`. Missing optional foundational
differences become zero, which is a neutral difference; this treatment is fixed here and
must be checked in a later missingness sensitivity study. ATP and WTA fit separately.

## Evidence limits

The historical completed-match-row ranking fields remain `RESEARCH_ONLY_UNVERIFIED` under
`docs/historical_ranking_availability_evidence_001.md`. Any historical evaluation using
them is exploratory. A forward ranking prediction requires a retained published ranking
snapshot for both players, with source URL, capture time, content hash, canonical IDs and
capture before verified actual start. A snapshot captured after start cannot be used to
repair a missed prediction. Training on the research-only historical ranks also prevents a
claim that the RANK arm has an independently verified historical T0 backtest.

## Evaluation contract before forward use

1. Train coefficients on documented historical development data ending before every
   target. Freeze the exact training manifest, code, feature order, scaling and coefficients.
2. Generate BASE and, when rank evidence permits, RANK probabilities from the same
   pre-start fixture input as frozen Strict Core and the final frozen stack. Preserve the
   fixture ID, player orientation, state cutoff and source hashes.
3. Score completed non-walkover, non-retirement matches only. Each comparison uses the
   intersection of exact canonical match IDs with valid pre-start probabilities. Report
   all missing, late and excluded matches separately.
4. Primary paired outcomes are mean Brier and log-loss differences. Accuracy, calibration,
   coverage and fixed decision thresholds are descriptive. Report rescued and spoiled picks,
   not only net wins, with date-block uncertainty intervals.
5. Keep WTA Web Shadow, ATP research replay and formal FULL-STACK-FORWARD-001 in separate
   cohorts. The challenger cannot alter any frozen model, experiment, or prior prediction.

No promotion threshold or independent confirmation claim has been registered yet. Before
formal prospective evaluation, freeze a complete comparison protocol and a trained model
artifact. Historical replay and current Web Shadow observations can guide development but
cannot become a fresh confirmation after inspection.
