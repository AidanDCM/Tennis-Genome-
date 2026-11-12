# 2026-11-09 iteration 7 — executed exact date-cluster sign-flip sensitivity

Evidence tier: **retrospective exploratory, non-production WTA Web Shadow**. Not a prospective champion/challenger result, not a model promotion.

## Audited state
- Main remains `8af76720a6291b166263fa1cd8191504f84ed6b6`; open PRs #428 (result acquisition with identity conflicts) and #429 (this research).
- Main non-production scorecard: 88 settled, 85 eligible completed, 46/85 correct; Brier 0.251461, log loss 0.696908. Last verified Forward Validation Aggregate (2026-11-09) had zero settled forward challenger observations.
- CI for prior iteration at branch head `3a0a10b71089a6189a5563e3771fa1e1968ac130` passed (run 42714876763).

## Execution, exact evidence
Added `scripts/research_calibration_signflip_real.py` in commit `dce6d62b5ff89bfbc6ca82057b276cda92018d1f`, plus dedicated GitHub workflow in commit `2b009e68bde7cb3f07cb3ddb072f6e4f99684702`. It reads the scorecard and immutable prediction/settlement paths, reuses the pre-existing chronological calibration experiment, reproduces adaptive slope counts and Brier improvement, then enumerates 2^15 = 32,768 exact date-cluster sign assignments for both paired Brier and log-loss differences.

Reproduce: `python scripts/research_calibration_signflip_real.py --repo-root .`

**Actual GitHub Actions execution:** https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42722031179 — success, logs inspected, exact head `2b009e68bde7cb3f07cb3ddb072f6e4f99684702`.

- 55 evaluation matches, 15 UTC start-date clusters (cluster sizes 1–6).
- Adaptive vs unchanged: Brier improvement +0.005567207901; exact two-sided sign-flip fraction **0.3297119140625**. Log-loss improvement +0.012321455818; fraction **0.33074951171875**.
- Fixed 0.5 logit slope vs unchanged: Brier improvement +0.010890400417; fraction **0.2144775390625**. Log-loss improvement +0.023841833740; fraction **0.2188720703125**.
- Winner-selection accuracy unchanged because all calibration slopes are positive.

These are **exploratory sensitivity fractions**, NOT valid confirmatory p-values: cluster-level sign-exchangeability is unverified, observations were reused for model selection, and temporal/tournament dependence remains. Exact enumeration eliminates Monte Carlo error, not methodological bias. No evidence supports model promotion.

## Methodological sources / contrary evidence
- MacKinnon, Nielsen & Webb (2023), cluster-robust inference and few-cluster caveats; https://doi.org/10.1080/07350015.2022.2091103 (bibliographic metadata should be verified before citation).
- Gneiting, Balabdaoui & Raftery (2007), calibration and sharpness: https://doi.org/10.1111/j.1467-9868.2007.00587.x.
- The sign-flip test is most sensitive to unverified sign symmetry, cluster definition, and retrospective selection. A large observed Brier improvement is not proof of generalization.

## Highest-value next execution
1. Confirm repository-wide CI at the new head and repair any failures; add direct unit tests for end-to-end runner and its scorecard mismatch safeguards.
2. Audit PR #428 identity conflicts and pending/finished result matching without bypassing identity/provenance gates; prioritize independent forward sample growth.
3. Freeze a prospective, predeclared calibration challenger on new pre-start predictions; compare Brier/log loss, accuracy, and coverage with paired uncertainty only after verified forward settlements.
4. Compare date versus tournament clustering only as sensitivity, not as a new search for the smallest p-value.

No champion, predictions, or settlements were edited.
