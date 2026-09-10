# GENOME-NN-001 — Findings

Status: **historical development result**

GENOME-NN-001 tested whether a transparent, strictly historical Tennis Genome neighborhood contains residual predictive information beyond the frozen strict Core v1 model, and whether raw neighborhood distance is a useful uncertainty / out-of-distribution coordinate.

The experiment was preregistered in `genome_neighborhood_protocol.md` with two pre-result amendments before any historical output was inspected.

## Accepted run

- workflow: `34429137547`
- accepted head: `04701329baf0c314bf3542f58c9068b7d01c94be`
- artifact: `tennis-genome-neighborhood`
- artifact SHA-256: `082e9aff6f679054681b1dbda3d1160c9c6597e9246b9cff5854d211778bd9fa`
- source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- coverage: 2000–2025 only
- source status: CC BY-NC-SA 4.0 research-only
- primary distance: historical-fold median-imputed / standardized Euclidean
- primary neighborhood size: `k=100`
- partial-2026 holdout: excluded and already spent by earlier work

Both ATP and WTA runs, summary generation, provenance copying, and artifact upload completed successfully on the same frozen workflow head.

## Decision summary

| Hypothesis | ATP | WTA | Decision |
|---|---|---|---|
| H-011 — historical neighbors add incremental residual signal | pass | pass | provisional historical support on both tours |
| H-012 — raw neighborhood density predicts reliability | fail | fail | reject raw `D100` as an uncertainty coordinate |
| shared-player adversarial transferability | pass | pass | classify H-011 as a general historical-alignment candidate, not identity-dependent |

These are development decisions only. No independent forward holdout remains for this candidate.

## H-011 — ATP

Fair nested chronological meta-comparison, N = **65,419**:

| Metric | Meta-control | Genome challenger | Change |
|---|---:|---:|---:|
| Brier | 0.203211 | 0.202880 | **+0.000331 improvement** |
| log loss | 0.590661 | 0.589868 | **+0.000793 improvement** |
| accuracy | 68.0414% | 67.9390% | -0.1024 pp |
| ECE-10 | 0.003677 | 0.005824 | worse |

Registered stability:
- joint Brier + log-loss wins: **17/23 years = 73.91%**;
- 2021–2025 Brier improvement: **+0.000156**;
- 2021–2025 log-loss improvement: **+0.000418**;
- 2021–2025 direction therefore does not reverse.

Direct residual evidence, N = **68,518** neighbor rows:
- slope of future Core residual on `R_NN`: **+0.352258**;
- Q5-minus-Q1 realized Core residual: **+0.046458**;
- 2021–2025 slope: **+0.249510**;
- 2021–2025 Q5-minus-Q1 residual: **+0.032232**.

The residual monotonicity is substantively stronger than the final probability-score gain. That is expected: the fair meta-model shrinks a noisy residual estimate instead of adding it one-for-one.

Secondary-k direction checks remain positive:
- k=25: slope **+0.171211**, Q5-Q1 **+0.043737**;
- k=250: slope **+0.506758**, Q5-Q1 **+0.049889**.

Only k=100 controls the primary decision.

### ATP shared-player exclusion

After excluding every candidate neighbor sharing either target player:
- eligible coverage: **100.00%**;
- Brier improvement: **+0.000297**;
- log-loss improvement: **+0.000714**;
- recent Brier improvement: **+0.000194**;
- recent log-loss improvement: **+0.000509**.

This clears the frozen transferability rule and classifies ATP as a **general historical-alignment candidate**, not an identity-dependent effect.

## H-011 — WTA

Fair nested chronological meta-comparison, N = **60,129**:

| Metric | Meta-control | Genome challenger | Change |
|---|---:|---:|---:|
| Brier | 0.205334 | 0.205118 | **+0.000216 improvement** |
| log loss | 0.595734 | 0.595259 | **+0.000476 improvement** |
| accuracy | 67.6595% | 67.7360% | +0.0765 pp |
| ECE-10 | 0.006572 | 0.007743 | worse |

Registered stability:
- joint Brier + log-loss wins: **15/23 years = 65.22%**;
- 2021–2025 Brier improvement: **+0.000083**;
- 2021–2025 log-loss improvement: **+0.000187**;
- 2021–2025 direction therefore does not reverse.

Direct residual evidence, N = **63,201** neighbor rows:
- slope of future Core residual on `R_NN`: **+0.298653**;
- Q5-minus-Q1 realized Core residual: **+0.045170**;
- 2021–2025 slope: **+0.203003**;
- 2021–2025 Q5-minus-Q1 residual: **+0.040090**.

Secondary-k direction checks remain positive:
- k=25: slope **+0.143357**, Q5-Q1 **+0.037664**;
- k=250: slope **+0.471928**, Q5-Q1 **+0.046229**.

### WTA shared-player exclusion

After excluding every candidate neighbor sharing either target player:
- eligible coverage: **100.00%**;
- Brier improvement: **+0.000215**;
- log-loss improvement: **+0.000473**;
- recent Brier improvement: **+0.000120**;
- recent log-loss improvement: **+0.000259**.

This also clears the frozen transferability rule and classifies WTA as a **general historical-alignment candidate**.

## H-012 — raw density fails

The preregistered density hypothesis predicted that higher mean k=100 distance (`D100`) would correspond to larger Core error.

The observed direction is the opposite on both tours.

### ATP
- log-loss slope vs distance: **-0.020810**;
- absolute-residual slope vs distance: **-0.019233**;
- Q5-minus-Q1 Core log loss: **-0.155232**;
- recent direction also remains negative.

### WTA
- log-loss slope vs distance: **-0.005403**;
- absolute-residual slope vs distance: **-0.005735**;
- Q5-minus-Q1 Core log loss: **-0.097988**;
- recent direction also remains negative.

Therefore H-012 **fails** and raw `D100` is rejected as a reliability / abstention coordinate.

No post-result threshold, sign reversal, or reinterpretation is allowed to rescue H-012.

## Exploratory explanation of the H-012 failure

This section is explicitly **post-result exploratory analysis**, not confirmatory evidence.

Raw `D100` is correlated with Core confidence:
- ATP correlation between mean distance and `abs(p_core - 0.5)`: approximately **+0.358**;
- WTA correlation: approximately **+0.192**.

The farthest neighborhoods therefore contain disproportionately strong-favorite situations, which are also easier for Core v1. This can make raw distance look inversely related to error even if local historical sparsity has no protective effect.

When the artifact rows are stratified into Core-confidence quintiles, the distance-vs-log-loss slopes mostly collapse near zero rather than reproducing the large aggregate negative relationship. This suggests the primary raw-distance coordinate mixes **match extremity/difficulty** with unfamiliarity.

That explanation does not upgrade H-012. It creates a new future hypothesis only: an uncertainty coordinate may need to be conditional on expected match difficulty, year/regime, and data coverage before it can represent OOD.

## Interpretation

H-011 is the first evidence in the project that transparent historical alignment adds incremental chronological predictive structure after a strong parametric Core model has already modeled accepted strength, form, workload, physical, and tournament-context families.

The gain is real under the frozen historical protocol but small in probability-score terms. It should therefore be treated as a **B / conditional development candidate**, not a new dominant model layer. Its strongest evidence is:
- proper-score improvement on both tours;
- >60% joint-year win rate on both tours;
- positive recent-period direction;
- monotone future residual relation;
- persistence at k=25 and k=250;
- persistence after removing all same-player neighbors.

The challenger does not improve ECE, so Genome v1 does not solve calibration. Calibration remains a separate layer.

## What is not established

This result does **not** establish:
- independent forward confirmation;
- sportsbook mispricing;
- positive EV;
- CLV;
- profitability;
- optimal k or distance metric;
- optimal feature weights;
- a live PASS/abstention threshold;
- that raw distance measures OOD;
- that visual fingerprint similarity is predictive.

## Next registered work

1. merge the transparent Genome v1 / GENOME-NN-001 implementation after exact-head CI and diff audit;
2. preserve H-011 as a frozen historical candidate for genuinely forward confirmation when new data exists;
3. register a separate density experiment that conditions unfamiliarity on Core confidence / expected difficulty rather than repairing H-012 in place;
4. test module-specific neighborhoods only under new preregistered protocols;
5. avoid learned embeddings or metric learning until a transparent extension proves enough incremental value to justify the complexity;
6. continue production-compatible match/odds data acquisition before any market/EV or paper-profitability layer.
