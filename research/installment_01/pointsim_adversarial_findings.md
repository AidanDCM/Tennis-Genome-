# POINTSIM-ADV-001 — WTA Mechanistic Residual Adversary Findings

Status: accepted historical development result from the frozen 2000–2025 WTA protocol. This is not independent forward confirmation and is not a market/profitability test.

## Provenance

- Accepted workflow run: `34493151233`
- Accepted frozen head: `87e93a8c9907328fc51f4d152fe643fffa7b7a9c`
- Artifact ID: `10159299587`
- Artifact digest: `sha256:92ab7f6ed87b4bfb0efb27dded138efeb4e6778d407ae8c7ed18e1e8e829f817`
- Pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- Development coverage: WTA 2000–2025 only
- The spent partial-2026 holdout remained excluded

## Frozen question

POINTSIM-ADV-001 asks whether the frozen POINTSIM-001 mechanistic probability adds incremental WTA information beyond the stronger incumbent strict-Core-geometry historical-alignment probability.

The registered comparison was:

- A0: incumbent raw historical-alignment probability, diagnostic only;
- A1: chronological alignment-only recalibration control;
- A2: chronological alignment + frozen POINTSIM challenger.

A1 and A2 used identical earlier-year rows, regularization, preprocessing, and future test IDs. The promotion gate was frozen before result inspection.

## Result

Matched prediction population: **57,328** WTA matches.

| Population | A1 Brier | A2 Brier | Δ Brier | A1 Log loss | A2 Log loss | Δ Log loss |
|---|---:|---:|---:|---:|---:|---:|
| Aggregate | 0.205902 | **0.205647** | **+0.000255** | 0.597497 | **0.596964** | **+0.000534** |
| 2021–2025 | 0.212390 | **0.211595** | **+0.000795** | 0.612094 | **0.610221** | **+0.001873** |

Accuracy also improved modestly:

- aggregate: 67.56% → **67.63%**;
- 2021–2025: 65.93% → **66.15%**.

ECE was slightly worse for the challenger on the full population (`0.00805` → `0.00888`) and somewhat worse in 2021–2025 (`0.00804` → `0.01132`). Per protocol, ECE is secondary and cannot override the registered proper-score gate.

## Year stability

A2 jointly beat A1 on both Brier and log loss in **16 of 22 evaluated years (72.7%)**, exceeding the frozen 60% requirement.

The incremental POINTSIM coefficient is small relative to the alignment coefficient and is not uniformly positive in every early year. That reinforces the intended interpretation: POINTSIM is a conditional residual component, not a dominant standalone probability engine.

## Promotion decision

**POINTSIM-ADV-001: PASS.**

Every frozen gate passed:

1. aggregate Brier improved;
2. aggregate log loss improved;
3. joint proper-score wins occurred in at least 60% of evaluated years;
4. 2021–2025 Brier was non-worse and in fact improved materially;
5. 2021–2025 log loss was non-worse and also improved materially.

Therefore the frozen POINTSIM probability is promoted as a **B/conditional WTA component** in the development candidate architecture.

This does **not** reverse H-018A. Raw POINTSIM remains rejected as a standalone match-probability model. The promoted role is only as a weak second input layered on top of WTA historical alignment.

## Architecture consequence

The current tour-specific development candidate becomes:

- **ATP:** full-Genome historical alignment; no POINTSIM input.
- **WTA:** strict-Core-geometry historical alignment + frozen POINTSIM residual component.

POINTSIM should enter WTA through the same chronological two-input statistical mapping tested here, not by directly averaging raw probabilities and not by replacing historical alignment.

The WTA component remains conditional pending genuinely later forward evidence. The already-spent partial-2026 holdout must not be reused to rescue or tune it.

## Non-claims

POINTSIM-ADV-001 does not establish:

- standalone accuracy of the mechanistic simulator;
- exact historical scoring-rule simulation;
- independent forward validation;
- sportsbook mispricing;
- positive expected value;
- CLV, ROI, or profitability.

## Next

Freeze `TGE-Independent-v1` as a market-blind, tour-specific probability architecture with immutable model/version/provenance contracts. The freeze should preserve ATP and WTA asymmetry exactly as supported by the accepted historical evidence and explicitly label WTA POINTSIM as conditional rather than independently forward-confirmed.
