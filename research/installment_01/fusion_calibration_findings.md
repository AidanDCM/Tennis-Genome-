# FUSION-CAL-001 — Probability Fusion and Calibration Findings

Status: accepted historical development result from the frozen protocol. This is not forward confirmation and is not a market/profitability test.

## Provenance

- Accepted workflow run: `34487501962`
- Accepted frozen head: `8aba00a9258bffd7f469aa74405c33a34511a734`
- Artifact ID: `10157170018`
- Artifact digest: `sha256:532eb87ad6622ed863eb31c4a79cf42783642aece6c493ab82da0d4b0babd089`
- Pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- Development coverage: 2000–2025 only
- The spent partial-2026 holdout remained excluded

## Frozen question

The historical-alignment predictor already contains Core probability plus a historical residual correction. FUSION-CAL-001 therefore tested **probability fusion**, not independent model diversification.

Candidates:

- F0: incumbent alignment probability
  - ATP: full-Genome historical alignment
  - WTA: strict-Core-geometry historical alignment
- F1: chronological recalibration of alignment probability alone
- F2: fixed equal-logit Core/alignment blend diagnostic
- F3: chronological two-view logistic fusion of Core + alignment

The primary fusion gate required F3 to beat F1 on aggregate Brier and log loss, jointly win both metrics in at least 60% of evaluated years, and not worsen either metric over 2021–2025.

## ATP — no fusion layer

Common fusion population: **62,422** matches.

| Candidate | Brier | Log loss | Accuracy | ECE-10 |
|---|---:|---:|---:|---:|
| F0 alignment | **0.202604** | **0.589155** | 67.9616% | 0.007302 |
| F1 alignment recalibration | 0.202697 | 0.589388 | 67.9744% | 0.012714 |
| F2 equal-logit blend | 0.202663 | 0.589315 | 67.9232% | **0.006935** |
| F3 two-view fusion | 0.202715 | 0.589442 | 67.9536% | 0.013066 |

F3 versus F1:

- Brier improvement: **-0.0000183**
- log-loss improvement: **-0.0000538**
- joint Brier + log-loss wins: **6/22 years (27.3%)**
- recent 2021–2025 Brier gate: pass
- recent 2021–2025 log-loss gate: fail

**Decision:** fusion FAIL. Retain F0.

The recent fitted F3 models place most standardized weight on the existing alignment probability and only a small residual coefficient on Core. For example, the standardized Core coefficient falls from about `0.075` in 2021 to about `0.041` in 2025 while the alignment coefficient remains around `1.05`. This is descriptive evidence of redundancy, not a causal coefficient interpretation.

## WTA — no fusion layer

Common fusion population: **57,328** matches.

| Candidate | Brier | Log loss | Accuracy | ECE-10 |
|---|---:|---:|---:|---:|
| F0 alignment | **0.205729** | **0.596732** | **67.5586%** | 0.007986 |
| F1 alignment recalibration | 0.205902 | 0.597497 | 67.5638% | 0.008076 |
| F2 equal-logit blend | 0.205752 | 0.596764 | 67.5342% | 0.008260 |
| F3 two-view fusion | 0.205920 | 0.597541 | 67.5150% | **0.007348** |

F3 versus F1:

- Brier improvement: **-0.0000181**
- log-loss improvement: **-0.0000441**
- joint Brier + log-loss wins: **13/22 years (59.1%)**
- recent 2021–2025 Brier gate: pass
- recent 2021–2025 log-loss gate: pass

WTA misses the predeclared 60% annual gate by one year, but that is not the only failure: F3 also loses both aggregate proper scores to F1 and loses materially to raw F0.

**Decision:** fusion FAIL. Retain F0.

## Calibration decision

Calibration was evaluated in a second nested chronological ledger and could not retroactively determine whether fusion passed.

### Selected ATP F0

On the common calibration population:

- Identity Brier: **0.202036**
- Identity log loss: **0.587828**
- Identity ECE-10: **0.007092**

Platt, Beta, and Isotonic all worsen aggregate Brier and log loss versus Identity. Therefore **ATP F0 remains Identity-calibrated**.

ATP Platt technically passes the calibration gate for the rejected F3 candidate, but F3 already failed the independent fusion gate. The protocol forbids using downstream calibration to rescue that rejected architecture.

### Selected WTA F0

On the common calibration population:

- Identity Brier: **0.206016**
- Identity log loss: **0.597252**
- Identity ECE-10: **0.007296**

Platt, Beta, and Isotonic all worsen aggregate Brier and log loss versus Identity. Therefore **WTA F0 remains Identity-calibrated**.

This does not contradict CAL-SEL-001's earlier WTA Beta finding. CAL-SEL-001 calibrated the then-current Core probability. FUSION-CAL-001 evaluates the later WTA historical-alignment probability, whose error structure and calibration are different. Calibration does not automatically transfer between model architectures.

## Architecture consequence

The current market-blind probability architecture becomes simpler, not larger:

- **ATP:** full-Genome historical-alignment probability → Identity calibration
- **WTA:** strict-Core-geometry historical-alignment probability → Identity calibration
- no additional Core+alignment fusion layer
- no equal-weight blend
- no post-hoc calibrator promoted for the selected alignment outputs

The strict Core probability remains an important benchmark, explanatory component, and uncertainty/disagreement input. It is not given a second probability-fusion weight merely because it is available.

## What this establishes

The historical-alignment layer appears to have already absorbed the useful Core information strongly enough that a second Core probability view adds no robust proper-score benefit under the registered fusion test.

This is evidence against unnecessary probability-stack complexity. It is **not** evidence that all future independent model families will be redundant.

A genuinely different model family should still be tested. The next registered direction is a mechanistic point → game → set → match probability constructed from date-frozen opponent-adjusted serve/return state, with a same-input statistical control and an incremental-to-Core gate.

## Non-claims

FUSION-CAL-001 does not establish:

- sportsbook mispricing
- positive expected value
- CLV
- ROI
- optimal betting thresholds
- production-ready calibration
- independent forward confirmation

The partial-2026 holdout remains spent and cannot be reused to validate this post-holdout architecture decision.
