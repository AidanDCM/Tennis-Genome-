# Installment 01 Hypothesis Registry

These are hypotheses, not established findings.

## H-001 Elo beats ranking

**Hypothesis:** Pre-match Elo produces better calibrated future win probabilities than ranking/ranking points alone.

Confounders/risks:
- tuning Elo on future periods;
- inconsistent treatment of retirements;
- ranking snapshot timing.

Primary metrics: log loss, Brier, calibration.

## H-002 Surface Elo adds information

**Hypothesis:** Surface-specific Elo adds incremental predictive value beyond overall Elo when estimated with sufficient shrinkage/sample control.

Risks:
- sparse surface histories;
- surface categories too coarse;
- surface Elo merely duplicating recent form.

## H-003 Opponent-adjusted serve/return improves baseline

**Hypothesis:** Point-based opponent-adjusted serve and return ratings improve probability quality beyond Elo/surface Elo.

Risks:
- poor point-stat coverage;
- opponent adjustment leakage;
- strongly correlated redundant variables.

## H-004 Recent underlying form matters beyond rating

**Hypothesis:** Recent opponent-adjusted point/serve/return performance predicts future residual performance after stable strength controls.

Compare fixed windows and exponential decay.

## H-005 Workload has conditional predictive value

**Hypothesis:** High recent workload affects future performance primarily under specific conditions rather than as a universal main effect.

Candidate moderators:
- age
- rest hours
- previous-match length
- heat
- surface
- injury state

## H-006 Rest duration is nonlinear

**Hypothesis:** The incremental effect of rest hours/days is nonlinear and may saturate after adequate recovery.

## H-007 Age modifies fatigue

**Hypothesis:** Older/certain career-stage players show stronger negative residuals after high workloads or short turnarounds.

Must survive player-strength and scheduling controls.

## H-008 H2H adds little after strong controls

**Hypothesis:** Raw head-to-head information has limited incremental value once overall/surface strength, serve/return, recency, and matchup information are included.

Counter-hypothesis: specific repeated matchup geometry contains genuine incremental signal.

## H-009 Profile Gap predicts movement before Elo fully catches up

**Hypothesis:** Players whose underlying profile strength exceeds Elo-implied strength subsequently outperform Elo expectation, especially for rapidly improving players.

Counter-hypothesis: Profile Gap is just noisy recent form.

## H-010 Model disagreement predicts error

**Hypothesis:** Matches where independently constructed models strongly disagree have larger forecast errors and worse calibration.

Potential use: abstention.

## H-011 Historical neighbors add incremental residual signal

**Hypothesis:** Strictly historical Match Fingerprint neighborhoods predict residual performance beyond conventional baseline models.

Counter-hypothesis: nearest-neighbor effects disappear after adequate parametric/GBM baselines.

## H-012 Neighborhood density predicts reliability

**Hypothesis:** Dense familiar regions of Match Fingerprint space yield lower error and better calibration than sparse/out-of-distribution regions.

Potential use: uncertainty and PASS decisions.

## H-013 Selective prediction improves retained-match accuracy

**Hypothesis:** If the confidence system is valid, reducing coverage by abstaining from low-confidence matches should monotonically improve probability quality/accuracy among retained matches.

A non-monotonic curve indicates poor confidence estimation or overfitting.

## H-014 Calibration materially matters

**Hypothesis:** Raw model outputs require chronological probability calibration and calibrated versions improve reliability/Brier/log loss without simply fitting noise.

## H-015 Player-order symmetry should hold

**Hypothesis:** Swapping Player A/B should invert prediction probability and leave decision-relevant information equivalent.

This is an engineering invariant more than a tennis hypothesis.

## H-016 Family-level feature selection beats indiscriminate metric accumulation

**Hypothesis:** A compact, validated set of feature families performs as well as or better than a very large redundant metric set on future data.

## H-017 Missingness and data quality predict uncertainty

**Hypothesis:** Lower feature coverage/reliability is associated with larger forecast error and should inform uncertainty/abstention.

## H-018 Market disagreement may identify either edge or model failure

Deferred market-aware hypothesis:
Large `p_model - p_market_novig` differences are not automatically profitable. Their future outcomes and CLV will reveal whether the model has unique information or is systematically wrong in those regions.
