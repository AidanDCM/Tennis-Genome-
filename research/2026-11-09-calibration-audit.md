# Research iteration — 2026-11-09: calibration before model complexity

Status: **research-only challenger proposal; not a production result, model change, or promotion.**
Base main SHA: `8af76720a6291b166263fa1cd8191504f84ed6b6`.

## Verified operational evidence
- Main CI run 42554677132: success (Ruff and Pytest steps completed successfully). Does not imply all operational pipelines are working.
- Forward Validation Aggregate run 42655914939: success as a job, but job log explicitly says `No settled shadow artifacts exist yet`; aggregate status `NO_SETTLED_FORWARD_OBSERVATIONS`. Independently validated forward challenger sample: **0**.
- One open PR #428: WTA result acquisition (snapshot 2026-11-09 08:39:51 UTC); 16 pending inspected, 1 finished result, 13 unmatched pending, 2 player-identity conflicts. CI on PR head `e676c961d674ffd32d254bb96f738ae7242e211f` is `action_required`, with no completed CI jobs. Do not merge without checks and identity review.
- Official non-production Web Shadow scorecard on main: 88 settled records, but only 85 in the overall scored metrics (46/85 correct, accuracy 0.54117647, Brier 0.25146106, log loss 0.69690827). These denominators must never be conflated.
- Paired Elo subset: 78; Genome accuracy 41/78 (0.52564), Elo accuracy 42/78 (0.53846); Genome Brier 0.25243283 versus Elo 0.25974519, Genome log loss 0.69868199 versus Elo 0.72271889. A better proper score but *worse* 0/1 accuracy is possible; neither establishes superiority at n=78.
- Aggregate selected-probability mean 0.62042361 vs hit rate 0.54117647: overconfidence gap 0.07924714. No prospective challenger performance inference from these paper-only metrics.

## Literature checked
1. 2026 unified tennis benchmark (133,138 ATP matches, temporal split): https://doi.org/10.3390/analytics5030022 — Elo 65.87% vs hybrid Elo+ML 67.52% on its population; high-capacity networks offer diminishing accuracy gains. **Not comparable to our WTA sample or independently reproduced here.** Feature ablation before expensive deep learning is justified.
2. Gneiting, Balabdaoui & Raftery (2007), calibration and sharpness: https://doi.org/10.1111/j.1467-9868.2007.00587.x — probability quality needs calibration and proper scores, not only hit rate.
3. Waghmare & Ziegel (2026), proper scoring rules: https://doi.org/10.1146/annurev-statistics-042424-050626 — Brier/log loss are principled probability evaluation targets.
4. Gollub et al. (2021), forecasting serve performance: https://doi.org/10.3233/JSA-200345 — small-sample shrinkage and opponent strength may improve serve-return estimates; test only after sufficient historical input availability is audited.
5. Ferro (2017), forecast evaluation with observation error: https://doi.org/10.1002/qj.3115 — unresolved player identity and result quality can distort scores; fix result matching before model tuning.

## Next controlled hypothesis and experiment (NOT YET EXECUTED)
Hypothesis H1: A single global, regularized calibration slope applied to the frozen Genome's log-odds, fitted strictly on earlier chronological settled predictions, improves *subsequent* out-of-sample Brier and log loss without changing its selected winners. Challenger formula: `p_cal = sigmoid(a * logit(p_raw))` with `a > 0` and intercept fixed at zero for player-label symmetry; constrain `a` to a prespecified compact range, use training-only regularization toward 1. Baseline: unchanged frozen Genome probability. A constant-0.5 shrinkage control and unmodified Elo comparator must be retained.

Prerequisites: verify immutable pre-start probability timestamps, unique match IDs, results, eligibility, chronology and absence of duplicated matches; derive exact 85/88 inclusion reasons. Use expanding-window walk-forward folds with no observation's result preceding its actual availability, not random cross-validation. Fit only on past, evaluate paired on later; preserve a final untouched prospective holdout. Predeclare primary metric paired Brier difference and secondary log-loss difference, 0/1 accuracy, calibration, 95% uncertainty intervals and eligible coverage; no post-hoc model promotion. Because positive slope preserves 0.5 side, **H1 should not increase winner-selection accuracy**; if a future run claims it does, investigate sample-selection or implementation errors.

Failure criteria: no eligible chronological training/evaluation sample, provenance/identity ambiguity, no statistically credible out-of-sample gain, worse calibration, or insufficient qualified sample. In any such case leave champion unchanged and report null result. Only move to more complex ensemble/feature changes after forward settlement evidence exists.

## Priority
P0: clear PR #428's `action_required` CI and adjudicate two identity conflicts without weakening gates; expand genuine settled forward challenger N.
P1: reproduce 85/88 scoring inclusion and inspect raw prediction-level chronology.
P2: preregister and implement the global-slope calibration challenger, with chronological paired evaluation.
P3: feature ablations, surface/recency Elo hybrids, and opponent-adjusted serve/return models.

This is an auditable design artifact, not a successful executed experiment.
