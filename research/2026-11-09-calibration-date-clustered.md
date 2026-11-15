# Iteration 5 — UTC start-date clustered paired uncertainty (2026-11-09)

Evidence tier: **exploratory, reused non-production WTA Web Shadow scorecard; not independently settled challenger evidence**.

## Operational audit
- Main `8af76720a6291b166263fa1cd8191504f84ed6b6` remains unchanged. Open PRs: #428 (result identity conflicts, action-required CI) and #429 (research only).
- Latest main Forward Settlement Monitor run 42698460395 completed successfully as a workflow, not proof of new forward challenger settlements. Prior Forward Validation Aggregate run 42655914939 reported zero settled forward challenger observations.
- Paper-only Web Shadow: 88 settled records, 85 completed scored (46/85 correct, 54.12%, Brier 0.251461, log loss 0.696908); 16 pending. Elo comparison on paired 78, not interchangeable with production evidence.
- Exact-head CI on previous research commit da1a362540af56e330d8cbc8d883baed9dc24e2b passed: run 42694950458 (Ruff, Pytest).

## Experiment actually executed
- Changed `scripts/research_web_shadow_calibration.py` in commit `f7ef9ef57df5e242ea7e4c5c78e16c16ef4572d7`. Added an intercept-only CR1 date-cluster sandwich variance for *paired* loss differences. Grouping: UTC scheduled-start date, not prediction run or player. Unequal cluster sizes handled using residual sums `sum(d_i - mean_d)` within each date; scale `G/(G-1)/N²`. This is a **descriptive normal approximation**, not an exact small-cluster test, and not adjusted for exploratory search.
- Added four edge-case and mathematical tests in `ad4008d6c70a3d4df942c65ad320496233e46a99` (three clusters, unequal sizes, invalid input, unchanged-model zero difference).
- Real-data research workflow run **42705546945** on code SHA f7ef9ef57df5e242ea7e4c5c78e16c16ef4572d7: **success**, job 129461254069; log inspected.
- Evaluated 55 chronological paper matches grouped into **15 UTC start-date clusters**. Baseline 26/55 correct, Brier 0.26380044, log loss 0.72277044. Adaptive slope Brier gain +0.00556721 with cluster-normal 95% interval **[-0.00534751,+0.01648193]**; log-loss gain +0.01232146 with **[-0.01190053,+0.03654344]**. Fixed slope 0.5 Brier gain +0.01089040 with **[-0.00554912,+0.02732992]**. All these intervals cross zero; no established superiority. Winner selections unchanged. Inspect full output for fixed-half log-loss interval.
- Research source on inference caveats: Sasaki & Wang (2022), https://arxiv.org/abs/2210.16991, finds conventional cluster-robust inference can fail with highly unbalanced clusters. This is a limitation of our descriptive CR1 approach, especially with only 15 clusters. Forecast combination alternative: Hendry & Clements (2004), https://doi.org/10.1111/j.1368-423X.2004.00119.x, finds simple averaging can beat elaborate estimated weights; do not claim transfer to WTA without sealed testing.
- Repository-wide CI on new tests: run 42705583621, **pending at ledger creation**. Do not claim tests passed until inspected.

## Falsifiable conclusion and next actions
The added dependence-aware interval is a better diagnostic than independent-match standard errors, but still crosses zero for observed gains. **Do not promote or select a model** from these reused outcomes. Verify exact-head CI; repair lint/test failures. Then prioritize P0 result identity and pre-start settlement gates (#428), real prospective challenger sample, and sealed paired evaluations; P1 implement stronger small-cluster bootstrap/permutation sensitivity and tournament-level clustering, explicitly checking cluster imbalance. Avoid tuning a fixed slope against the same 55 observations. Keep the frozen champion and untouched future holdout.
