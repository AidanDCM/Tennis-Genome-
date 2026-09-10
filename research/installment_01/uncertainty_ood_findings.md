# UNCERTAINTY-OOD-001 — Findings

Status: **historical uncertainty-development result**

UNCERTAINTY-OOD-001 tested whether pre-match historical unfamiliarity, model disagreement, missingness, and player-history depth can rank the expected error of the already-generated strict Core v1 probability better than Core probability confidence alone.

This experiment did **not** adjust match probabilities and did not search for a betting/PASS threshold. Its primary target was forecast-risk ranking.

## Accepted run

- workflow: `34440755483`
- accepted head: `ba8ee1c3fb6a4888f7e6d89a05b723f021a6a9aa`
- artifact: `tennis-genome-uncertainty-ood`
- artifact ID: `10137986958`
- artifact SHA-256: `fcf122e91ffc30e156a146e797d2a172b9da859943eb0c5648ddc03ee3e85600`
- source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- coverage: 2000–2025 only
- source status: CC BY-NC-SA 4.0 research-only
- partial-2026 holdout: already spent by prior work and excluded

Both ATP and WTA canonical rebuilds, uncertainty runs, summary generation, provenance copying, and artifact upload succeeded on the same frozen research head.

## Decision summary

| Hypothesis / coordinate | ATP | WTA | Decision |
|---|---|---|---|
| difficulty-conditioned historical unfamiliarity | **PASS** | **FAIL** | ATP B/conditional uncertainty candidate; WTA not promoted |
| model disagreement | **FAIL** | **PASS** | WTA B/conditional uncertainty candidate; ATP remains non-monotone/conditional |
| alignment-vector missingness | fail | fail | not a standalone uncertainty coordinate |
| minimum prior-match history depth | fail | fail | not a standalone uncertainty coordinate under this definition |
| ATP prior point-exposure depth | fail | n/a | not promoted |
| combined chronological Ridge risk ranking | **FAIL** | **FAIL** | no Uncertainty v1 composite and no hard PASS score |

These are historical development decisions only. No independent future holdout remains for these candidates.

## ATP — conditioned unfamiliarity survives the repaired density test

The ATP historical-alignment representation is the full Genome representation frozen by GENOME-ADV-001.

Conditioned-unfamiliarity population: **65,419** matches.

The preregistered coordinate removes expected distance as a function of Core confidence, confidence squared, and historical-pool size using only earlier rows, then standardizes the target residual by prior residual dispersion.

### Aggregate

- Brier-contribution slope: **+0.004477**
- log-loss-contribution slope: **+0.010359**
- Q5-minus-Q1 Brier contribution: **+0.014823**
- Q5-minus-Q1 log-loss contribution: **+0.035313**

Brier by conditioned-unfamiliarity quintile:

- Q1: **0.195084**
- Q2: **0.201790**
- Q3: **0.203787**
- Q4: **0.205465**
- Q5: **0.209907**

The aggregate relation is monotone in the registered direction.

### 2021–2025

- Brier slope: **+0.003693**
- log-loss slope: **+0.006327**
- Q5-minus-Q1 Brier: **+0.014980**
- Q5-minus-Q1 log loss: **+0.033130**

The direction remains positive recently, so the frozen conditioned-density gate **passes for ATP**.

This does not revive raw `D100`. Raw distance remains rejected. The supported ATP coordinate is specifically the **prior-only difficulty/pool-conditioned unfamiliarity residual**.

## WTA — conditioned unfamiliarity does not survive the recent-period gate

WTA uses strict-Core geometry only, as frozen by GENOME-ADV-001.

Conditioned-unfamiliarity population: **60,129** matches.

Aggregate results initially look supportive:

- Brier slope: **+0.002217**
- log-loss slope: **+0.005257**
- Q5-minus-Q1 Brier: **+0.025290**
- Q5-minus-Q1 log loss: **+0.058253**

However 2021–2025 reverses the registered linear direction:

- Brier slope: **-0.003372**
- log-loss slope: **-0.007174**

Recent quintiles are U-shaped rather than monotone: both the unusually *close* and unusually *far* regions are difficult. Therefore the simple positive unfamiliarity score fails the frozen WTA gate. No sign flip or absolute-value repair is allowed post result.

WTA conditioned unfamiliarity remains experimental only.

## Model disagreement

The disagreement definition is inherited unchanged from CAL-SEL-001: maximum minus minimum probability across Elo-only, strict Core, and A+B diagnostic forecasts.

### ATP — fails the stricter monotonicity gate

Aggregate:

- Brier slope: **+0.103617**
- log-loss slope: **+0.292877**
- Q5-minus-Q1 Brier: **+0.017147**
- Q5-minus-Q1 log loss: **+0.044572**

Recent slopes stay positive, but 2021–2025 Q5-minus-Q1 reverses:

- Brier spread: **-0.004463**
- log-loss spread: **-0.002053**

The recent ATP relation is non-monotone: the very lowest-disagreement quintile is itself relatively difficult. Under the preregistered rule, ATP disagreement therefore **fails promotion as a standalone monotone uncertainty coordinate**. The earlier B/conditional interpretation is not upgraded.

### WTA — passes cleanly

Aggregate:

- Brier slope: **+0.123139**
- log-loss slope: **+0.308510**
- Q5-minus-Q1 Brier: **+0.019973**
- Q5-minus-Q1 log loss: **+0.048345**

2021–2025:

- Brier slope: **+0.124242**
- log-loss slope: **+0.289464**
- Q5-minus-Q1 Brier: **+0.020323**
- Q5-minus-Q1 log loss: **+0.045933**

The highest-disagreement recent WTA quintile has Brier **0.226622** versus **0.206299** in the lowest quintile. WTA disagreement therefore **passes** its frozen uncertainty-coordinate gate and remains a B/conditional development candidate pending genuinely forward confirmation.

## Missingness does not behave as a universal risk coordinate

Alignment-vector missingness fails both tours.

ATP aggregate missingness slopes are negative, while recent slopes turn positive. WTA shows the same regime instability: aggregate missingness is associated with lower error, while recent missingness is associated with higher error.

This reflects changing source coverage / feature availability and makes raw missing fraction unsuitable as a standalone cross-era uncertainty score.

The result does not imply missing data are harmless. It means **unconditioned missing fraction is not a stable risk coordinate** under the current historical source.

## Simple history depth does not pass

The hypothesis that more prior matches should monotonically imply lower forecast error does not pass on either tour.

ATP aggregate slopes are slightly positive before turning negative recently. WTA slopes remain slightly positive even recently. The quintile behavior is non-monotone, consistent with history depth being confounded with career stage, player quality, survivorship, and the kinds of matches represented in the tour data.

ATP point-exposure depth also fails the aggregate/recent sign rule.

These fields remain useful provenance/data-depth descriptors, but no standalone uncertainty weight is promoted from this experiment.

## Combined chronological risk model — not promoted

Risk-prediction population:

- ATP: **62,422** OOS matches
- WTA: **57,328** OOS matches

The combined prior-only Ridge model was compared against simply retaining matches by Core confidence.

### ATP

| Coverage | Confidence Brier | Risk-model Brier | Δ Brier | Confidence log loss | Risk-model log loss | Δ log loss |
|---:|---:|---:|---:|---:|---:|---:|
| 75% | 0.187838 | 0.187902 | -0.000064 | 0.556802 | 0.556930 | -0.000127 |
| 50% | 0.164538 | 0.164568 | -0.000030 | 0.504403 | 0.504474 | -0.000072 |
| 25% | 0.125804 | 0.125588 | +0.000217 | 0.412452 | 0.411981 | +0.000471 |

Only **1/3** primary operational coverages improves on each proper score, below the required 2/3 gate. The mean 75/50/25 improvement is slightly positive, and recent mean direction is also positive, but the per-coverage rule intentionally prevents promotion based on one tighter subset.

The 10% and 5% ATP diagnostics improve more strongly, but the protocol explicitly forbids using those extreme-favorite subsets to drive promotion.

### WTA

| Coverage | Confidence Brier | Risk-model Brier | Δ Brier | Confidence log loss | Risk-model log loss | Δ log loss |
|---:|---:|---:|---:|---:|---:|---:|
| 75% | 0.192618 | 0.192563 | +0.000055 | 0.568876 | 0.568764 | +0.000112 |
| 50% | 0.170815 | 0.170447 | +0.000368 | 0.520666 | 0.519885 | +0.000782 |
| 25% | 0.134648 | 0.135872 | -0.001224 | 0.436789 | 0.439339 | -0.002549 |

Although WTA wins **2/3** operational coverages, the 25% loss is large enough that mean operational Brier and log-loss improvements are negative. The 2021–2025 mean differences are also negative. At 10% the model is materially worse than confidence-only.

Therefore the combined WTA uncertainty model also **fails**.

## Selective-prediction consequence

Core confidence remains the default general-purpose ranking coordinate. The project has learned tour-specific *diagnostic* uncertainty information, but not a stable composite that beats confidence broadly enough to justify a new PASS score.

The supported development coordinates are therefore kept modular:

- **ATP:** conditioned historical unfamiliarity is a B/conditional uncertainty candidate;
- **WTA:** model disagreement is a B/conditional uncertainty candidate;
- neither becomes a hard abstention rule yet.

A future policy experiment may test whether these tour-specific coordinates improve decisions *within predefined Core-confidence regions*. That must be separately preregistered; this result does not authorize post-hoc thresholds.

## What is not established

UNCERTAINTY-OOD-001 does **not** establish:

- a hard PASS / PLAY threshold;
- an independently forward-confirmed uncertainty model;
- that uncertainty signals cause errors;
- a universal OOD score across tours;
- that raw distance is useful;
- sportsbook mispricing;
- EV, CLV, ROI, or profitability.

## Architecture consequence

1. do **not** promote the combined Ridge risk model;
2. preserve Core probability confidence as the general selective-prediction baseline;
3. retain ATP difficulty-conditioned unfamiliarity as a conditional uncertainty descriptor;
4. retain WTA model disagreement as a conditional uncertainty descriptor;
5. keep missingness/history depth as provenance, not standalone risk weights;
6. proceed to the tour-specific probability ensemble using the historical-alignment representations frozen by GENOME-ADV-001;
7. calibrate that ensemble chronologically before any independent-model freeze;
8. if a PASS policy is later tested, use a separate preregistered policy experiment rather than selecting thresholds from this artifact.
