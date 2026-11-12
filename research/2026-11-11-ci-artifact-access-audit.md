# 2026-11-11 — CI diagnostics access and shadow uncertainty audit

## Repository and evidence
- Main scorecard read directly: `web-shadow/scorecard.json` on `main`, 88 settled records, 85 eligible scored, 46 correct, 16 pending, production_eligible=false. Brier 0.2514610585394295; log loss 0.6969082732945988.
- Paired historical baseline: 78 common samples, Genome 41/78, Elo 42/78; Brier Genome 0.25243282736841877 vs Elo 0.2597451903841716; log loss Genome 0.6986819892394467 vs Elo 0.7227188854273178. No claim of prospective superiority.
- PR #428 remains open: https://github.com/AidanDCM/Tennis-Genome-/pull/428 ; snapshot wta-results-20261109t083951z, match `web:wta:1148:2026:LS001`; 13 unresolved and 2 identity-conflicted predictions held out.
- PR #448 remains open draft: https://github.com/AidanDCM/Tennis-Genome-/pull/448 . Its commit `460ea296038c2000ae11ff90b0258a9cd6000cf1` has a successful associated CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43089722208 .
- Prior PR #447 CI https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43080766329 has diagnostic artifact ID 13883129305, 653 bytes, named ci-diagnostics, SHA-256 digest `799c485b8c505e7b240ef32df95ed58b67c8c72790d620fe60e8abbdcb8f45c2`. GitHub artifact metadata fetched successfully; artifact download through connected GitHub tool failed internally. Therefore its actual ZIP contents, pytest count and settlement summary remain **uninspected**. Do not imply otherwise.

## Prespecified numerical check
- Hypothesis: historical shadow winner accuracy is not precise enough to establish reliable superiority or justify calibrator fitting. Baseline: 50% classification reference, not a prospective head-to-head test. Population: 85 scorecard-eligible historical shadow matches. Success condition for a claim of above-50% accuracy: Wilson 95% lower bound > 0.5. Otherwise null/inconclusive.
- Executed independent Wilson calculation using `n=85, k=46, z=1.95996398454, p=k/n, d=1+z*z/n, center=(p+z*z/(2*n))/d, half=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/d`.
- Observed 46/85 = 0.5411764705882353; Wilson 95% [0.435763360699628, 0.6430286818098032]. **Failure to clear 50% lower bound**. This is an uncertainty diagnostic only, not a model ablation or paired prospective inference.
- Historical paired Brier baseline minus Genome = 0.007312363015752832. Aggregate scores alone cannot provide paired confidence intervals; per-match locked predictions and outcomes required. No retuning, model promotion or final-holdout use.

## Research and contrary evidence
- Schmidt et al., *A Unified Benchmark of Machine Learning and Deep Neural Networks for Tennis Match Prediction* (published July 3 2026), https://doi.org/10.3390/analytics5030022 . Same temporally split ATP population, Elo, classical ML, deep learning and hybrid; narrow improvement band; ATP != WTA, reproduction/license not verified, do not transfer accuracy claims.
- Bunker et al., *A comparative evaluation of Elo ratings- and machine learning-based methods for tennis match result prediction* (first online Nov 10 2023), https://doi.org/10.1177/17543371231212235 . Fourteen expanding annual ATP test periods; methodologically relevant chronological design, but some reported comparisons depend on prohibited market-derived features and therefore **must not be imported**. License/code reproducibility not verified.
- Contrary hypothesis: simple overall Elo may match or beat Genome on genuinely new locked WTA samples. Pre-register paired Brier/log-loss and chronologically fixed coverage, surfaces and cohorts.

## Reproduction and next queue
1. Inspect CI diagnostics ZIP through a working GitHub artifact-download route, validate archive SHA-256, inspect actual `pytest.txt` and `ruff.txt`. If output lacks settlement payload, add an isolated test artifact capturing a redacted deterministic summary without touching canonical data.
2. Review acquisition PR #428 against complete provenance and exclusions before any human approval; no automatic merge or settlement.
3. Audit active workflow freshness and qualified production-forward aggregate on main; increase legitimate prospective capture.
4. Once observations accrue, compare frozen champion vs simple Elo with paired chronological probability scores and uncertainty; keep final holdout untouched.
