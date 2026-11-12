# 2026-11-09 iteration 2 — executed calibration ablation (research-only)

Source: immutable `web-shadow/scorecard.json` and per-match prediction and settlement files at main `8af76720a6291b166263fa1cd8191504f84ed6b6`. New code head `86883550d51654703b2c8b8db2650c212a55cb1b`. Draft PR #429. This is **not independent forward challenger evidence**, and no production artifact was changed.

## Reproduction

`python scripts/research_web_shadow_calibration.py --repo-root .`

GitHub Actions exact-head run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42676595311 (syntax validation and real-data calibration experiment steps succeeded). Artifact: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42676595311/artifacts/13700746083

Source scorecard: 88 settled; **85 completed eligible**, 2 walkovers and 1 retirement excluded. Original 85-match Brier/log loss/accuracy reproduced by code within 1e-10, providing an independent numeric consistency check against the saved summary.

## Experiment, no winner changes

Hypothesis: a positive log-odds slope chosen from the fixed set [0.5,0.7,0.9,1.0,1.1] by earlier completed observations' log loss (plus regularization toward 1) reduces later proper-score error relative to slope=1. Each evaluation match has >=30 training matches whose results were observed **before its scheduled start**; no current or future outcomes enter fitting. Score 55 later observations. The test reuses already examined paper data and is **exploratory**, not preregistered independent proof.

| Metric | Unchanged baseline | Chronological calibration challenger |
|---|---:|---:|
| Eligible later matches | 55 | 55 |
| Accuracy | 26/55 = 47.27% | 26/55 = 47.27% |
| Brier (lower better) | 0.26380044 | 0.25823323 |
| Log loss (lower better) | 0.72277044 | 0.71044898 |

Paired mean Brier improvement = +0.00556721; paired mean log-loss improvement = +0.01232146. Selected slopes 0.5 for 25 and 0.7 for 30 evaluation matches; others zero. The probabilities became less extreme, while winner accuracy remained exactly unchanged, as mathematically required by positive slopes. This small exploratory difference **does not establish statistical significance or a deployable improvement**.

## Evidence and external comparison

- Poudel et al. (2026), *A Unified Benchmark of Machine Learning and Deep Neural Networks for Tennis Match Prediction*, https://doi.org/10.3390/analytics5030022 — common chronological comparison across model families on ATP; Elo + machine learning yielded modest uplift over Elo. External ATP results are not directly comparable with our 55 WTA paper predictions.
- Buhamra & Groll (2025), *Statistical enhanced learning for modeling and prediction tennis matches at Grand Slam tournaments*, https://arxiv.org/abs/2502.01613 — rolling/expanding-window comparisons and engineered features. Do not adopt any market-related inputs; our research excludes them.
- Schwaderer et al. (2026), *Topological Data Analysis and Graph-Theoretic Approaches for Tennis Match Prediction*, https://arxiv.org/abs/2607.23509 — network-centrality features offer a possible later **pre-start-only** opponent-history ablation, but topology requires a carefully timestamped graph to avoid future-result leakage.

## Operational blockers and next experiments

- Main CI latest successful at 42554677132. PR #428 result acquisition CI action_required, and two identity conflicts remain; do not weaken identity checks. Latest Forward Validation Aggregate run 42655914939 completed but reported no settled forward challenger observations. **Independent prospective challenger N=0**.
- **P0** investigate CI action_required and adjudicate WTA identity conflicts with corroborating official sources, then expand qualified forward sample without retrospective fabrication.
- **P1** add a paired uncertainty interval / temporal block bootstrap to the read-only calibration evaluation, plus no-change/shrinkage negative controls and deterministic unit tests. Avoid interpreting the current tiny improvement as established.
- **P2** freeze the calibration challenger *before* new forward matches and evaluate only on genuinely new pre-start observations; retain untouched champion and a final holdout.
- **P3** controlled surface-Elo and opponent-history ablations on strictly chronological WTA datasets with complete feature provenance; avoid indiscriminate search.
