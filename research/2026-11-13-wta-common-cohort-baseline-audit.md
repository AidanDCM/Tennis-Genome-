# 2026-11-13 WTA common-cohort baseline audit (non-production, read-only)

## Pinned source and reproducibility
Main SHA: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`. Scorecard path: `web-shadow/scorecard.json`; Git blob `c9636ac9d86c256ccf241e652b9456034c451fc3`. Reproduce with `python - <<'PY'\nimport json\ns=json.load(open('web-shadow/scorecard.json'))\nb=s['baseline_comparison'];print(s['metrics']);print(b['settled_match_count'],b['genome'],b['baseline']);print(b['baseline']['brier_score']-b['genome']['brier_score'],b['baseline']['log_loss']-b['genome']['log_loss'])\nPY`. Do not use any post-start feature or relabel a prediction.

## Preregistered hypothesis and observed test
Hypothesis: on the *existing common* 79-match Elo-vs-Genome comparison cohort, Genome has lower **both** Brier and log loss than overall_elo_v1. Success requires positive baseline-minus-Genome deltas for both; failure otherwise. This is a descriptive audit of a pre-existing cohort, **not** a new independent challenger trial or significance test.

Executed connected GitHub fetch of main scorecard, parsed JSON, and numerically recomputed deltas from its recorded aggregates. N=79, Genome correct=42 (53.1646%), Brier=0.2522696014990375, log loss=0.6983470279140795. Elo correct=43 (54.4304%), Brier=0.2578582137265702, log loss=0.7186905603048556. Baseline minus Genome: Brier +0.005588612227532708, log loss +0.02034353239077602. **Descriptive hypothesis passes** on proper scores while Genome loses 1/79 in winner accuracy. No paired per-match loss differences, variance, chronological subgroups, or confidence intervals available from these aggregate fields; do not infer significance or superiority on future matches.

## Denominator and calibration checks
Main scorecard records 89 SETTLED, only 86 included in primary scored metrics (47 correct; 54.6512%, Brier 0.2513224181341722, log loss 0.6966212008671667), 15 PENDING, and baseline_match_count=97. The explicit common comparison has only 79, **not** 86 or 97. Its Genome accuracy and proper scores differ from the full 86. Recomputed full-sample four-bucket ECE from `sum(n_b * abs(acc_b - confidence_b))/86` = 0.07263465522676532; bucket Ns 44+25+12+5=86 and correct 23+13+7+4=47. 95% Wilson interval for 47/86: [0.4415616959,0.6474840532]. These are not production evidence.

## Capture and trust limitations
Main compiler still maps numeric RoundID 1=>F, 2=>SF, 5=>R32; 12 of 13 legacy pending candidates had unique player pairs but inconsistent round mapping in prior retained-artifact audit PR #478; one pair absent, two additional exact-ID conflicts. These remain **diagnostic only**. No source adjudication, retrospective settlement, feature change, champion promotion, or gate relaxation. Main SHA has not changed; open PRs #476-#480 remain review-only. Previous CI success on PR #479 tested code SHA `0db0353972244b6cf17e83e37465a2f713267140`, not this documentation commit. Production champion checksum and qualified forward denominator not independently refreshed in this run.

## External research and transfer limits
- Poudel et al. (2026), [A Unified Benchmark of Machine Learning and Deep Neural Networks for Tennis Match Prediction](https://doi.org/10.3390/analytics5030022): same temporally split ATP cohort (133,138 matches) across Elo, classical ML and deep networks; improvements over Elo modest. ATP population differs from WTA shadow, and published metrics cannot be transported. License for any associated implementation unverified; no code imported.
- Buhamra & Groll (2025), [Statistical enhanced learning for modeling and prediction tennis matches at Grand Slam tournaments](https://arxiv.org/abs/2502.01613): rolling/expanding evaluation and feature ablation; men's Slam population and feature availability differ. No code imported/license verified.
- Contrary: Clegg & Cartlidge (2025), [Tennis match outcome prediction using temporal directed graph neural networks](https://research-information.bris.ac.uk/en/publications/tennis-match-outcome-prediction-using-temporal-directed-graph-neu/): sophisticated graph model approximately tied weighted Elo on their tournament subset, arguing against complexity-first assumptions. No software imported/license verified.
No restricted market-derived inputs used.

## Prioritized executable queue
1. Extract common 79 per-match prelocked probabilities and outcomes with trustworthy IDs; calculate paired Brier/log-loss deltas, uncertainty, chronological stratification, and selection coverage; keep final holdout untouched.
2. Implement read-only mismatch reasons with adversarial negative controls; independently adjudicate 12 historical candidates without settlement.
3. Verify acquisition schedule, immutable production champion digest, qualified forward denominator and pre-start evidence gate from main.
4. Accumulate genuinely prospective matched observations before any challenger claim; compare simple Elo, Genome and calibration-only candidates on locked chronological cohorts.
