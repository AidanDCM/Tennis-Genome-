# POINTSIM-001 — Mechanistic Point-to-Match Simulation Findings

Status: accepted historical development result from the frozen 2000–2025 protocol. This is not forward confirmation and is not a market/profitability test.

## Provenance

- Accepted workflow run: `34490672908`
- Accepted frozen head: `73bccc7d208ce701d56fe87167245ebc74386aa4`
- Artifact ID: `10157782295`
- Artifact digest: `sha256:3291797e1a293c5d1c52f421a3a7fd0512bcebb4060c7d7ac13ad41738ba7910`
- Pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- Development coverage: 2000–2025 only
- The spent partial-2026 holdout remained excluded

## Frozen question

POINTSIM-001 tests whether date-frozen opponent-adjusted serve-point probabilities become better match probabilities when propagated explicitly through tennis scoring mechanics.

Two separate hypotheses were preregistered:

- **H-018A mechanics:** explicit point → game → set → match mechanics beat a chronological statistical control using the exact same two serve-point probability inputs.
- **H-018B incremental:** POINTSIM adds information beyond the existing chronological Core probability when included as a second input to a meta-model.

The source does not currently canonicalize all historical tiebreak/final-set rules. The simulator therefore uses the frozen standard-scoring approximation declared in the protocol and reports this as a limitation rather than treating the scoring path as historically exact.

## ATP

OOF population: **68,518** matches. Format coverage: **100%**.

### Same-input mechanics test

| Model | Brier | Log loss | Accuracy | ECE-10 |
|---|---:|---:|---:|---:|
| S0 same-input statistical control | **0.209227** | **0.604548** | 66.1680% | **0.011392** |
| S1 POINTSIM mechanistic probability | 0.214639 | 0.627741 | **66.5592%** | 0.065027 |

Mechanics joint proper-score wins: **0/24 years**.

**H-018A: FAIL.**

The mechanistic scoring transform is substantially worse than a flexible chronological statistical remapping of the same serve-point inputs. It is also strongly overconfident under this representation.

### Incremental-to-Core test

| Model | Brier | Log loss | Accuracy | ECE-10 |
|---|---:|---:|---:|---:|
| M0 Core recalibration control | **0.203880** | **0.592241** | 67.8318% | 0.005796 |
| M1 Core + POINTSIM | 0.203991 | 0.592346 | **67.8479%** | **0.004198** |

Incremental joint proper-score wins: **8/24 years**.

**H-018B: FAIL for ATP.**

POINTSIM does not earn a predictive role in the ATP probability architecture. A small ECE improvement does not override worse registered proper scores.

## WTA

OOF population: **63,201** matches. Format coverage: **100%**.

### Same-input mechanics test

| Model | Brier | Log loss | Accuracy | ECE-10 |
|---|---:|---:|---:|---:|
| S0 same-input statistical control | **0.215001** | **0.618121** | **65.4705%** | **0.024403** |
| S1 POINTSIM mechanistic probability | 0.221467 | 0.642398 | 65.1414% | 0.079332 |

Mechanics joint proper-score wins: **1/24 years**.

**H-018A: FAIL.**

As on ATP, explicit standard scoring mechanics are not a superior standalone mapping of the current serve/return point-strength estimates and are materially overconfident.

### Incremental-to-Core test

| Model | Brier | Log loss | Accuracy | ECE-10 |
|---|---:|---:|---:|---:|
| M0 Core recalibration control | 0.205538 | 0.596212 | 67.6287% | **0.007939** |
| M1 Core + POINTSIM | **0.205287** | **0.595686** | **67.7299%** | 0.009228 |

Incremental joint proper-score wins: **16/24 years**.

**H-018B: PASS historically for WTA.**

POINTSIM contains a small but reasonably stable residual signal beyond Core on WTA despite failing as a standalone probability model. This is exactly why H-018A and H-018B were separated: a misspecified mechanistic probability can still encode useful information that a stronger statistical model can exploit.

The WTA incremental gain is modest:

- Brier improvement: **+0.000251**
- log-loss improvement: **+0.000526**
- accuracy improvement: about **+0.10 percentage points**
- ECE worsens slightly

Therefore the result is a **conditional WTA challenger component**, not permission to replace the current historical-alignment architecture or to use raw POINTSIM probabilities directly.

## Architecture consequence

- **ATP:** do not promote POINTSIM as standalone or incremental probability input.
- **WTA:** retain POINTSIM as a B/conditional incremental probability component for a later matched comparison against the current post-Genome historical-alignment architecture.
- **Both tours:** raw mechanistic POINTSIM probability is rejected as a standalone model under the current serve/return state and scoring-rule approximation.

The current production-development candidate remains the historical-alignment architecture established before this experiment:

- ATP: full-Genome historical alignment → Identity calibration
- WTA: strict-Core-geometry historical alignment → Identity calibration

WTA POINTSIM has only shown incremental value against the Core benchmark so far. It has **not yet shown incremental value beyond the stronger WTA historical-alignment output**, so it must not be inserted into the final engine yet.

## Interpretation

The standalone failure suggests that the current serve-point probability estimates and/or simplified scoring-rule assumptions are not calibrated enough for direct mechanistic propagation. Tennis scoring mechanics amplify small point-probability errors, which is consistent with the large ECE observed for S1.

The WTA incremental pass suggests the mechanistic transformation may nevertheless encode nonlinear information about how serve/return asymmetry maps into match outcomes. That hypothesis now needs a stricter adversarial test against the current WTA historical-alignment probability before any promotion.

## Non-claims

POINTSIM-001 does not establish:

- exact historical scoring-rule simulation;
- superiority of mechanistic modeling generally;
- ATP value from POINTSIM;
- WTA value beyond the current historical-alignment architecture;
- forward validation;
- sportsbook mispricing;
- positive expected value;
- CLV, ROI, or profitability.

## Next

The next registered test should be **POINTSIM-ADV-001** for WTA only: compare the current WTA historical-alignment probability against a chronological meta-model that adds POINTSIM, with an alignment-only recalibration control and the same aggregate/year/recent proper-score gates used elsewhere. ATP should not be carried into that experiment except as a negative control if explicitly preregistered.
