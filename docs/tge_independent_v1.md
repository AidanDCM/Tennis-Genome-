# TGE-Independent-v1

Status: **development-frozen market-blind architecture**.

This document freezes the independent tennis probability architecture that survived the current historical research program. It does not claim sportsbook edge, expected value, or profitability, and it is not a new forward-validation event. The partial-2026 holdout has already been spent and cannot be reused to validate this freeze.

## Purpose

`TGE-Independent-v1` is the probability engine that must exist *before* market prices enter the system. Its only job is to estimate pre-match tennis probabilities and expose diagnostics/provenance. It does not know bookmaker, odds, edge, stake, profit, closing line, or realized outcome.

A later market layer may consume the independent prediction. The market layer must never feed information back into the independent engine under this version.

## Frozen development cutoff

- Research/development history: 2000–2025.
- Partial-2026 data: spent by earlier Core-v1 forward work; unavailable for rescue testing.
- Future confirmation of any post-2026 architecture change requires genuinely later unseen data.

## ATP architecture

Probability path:

1. `strict_core_v1`
2. `full_genome_historical_alignment_k100`
3. Identity calibration

Supported diagnostics:

- Core probability confidence
- conditioned Genome unfamiliarity
- historical-neighbor support
- data-quality/provenance diagnostics

Explicitly excluded from ATP v1:

- raw POINTSIM probability
- POINTSIM incremental component
- pure Surface Elo replacement
- universal composite uncertainty score
- hard PASS threshold

Rationale:

- Core v1 survived the partial-2026 forward test.
- Profile-aware historical Genome alignment survived GENOME-ADV-001 beyond simpler Core-only/local-calibration controls.
- POINTSIM failed ATP standalone and incremental gates.
- conditioned unfamiliarity is useful historically but did not justify a universal uncertainty model or fixed abstention threshold.

## WTA architecture

Probability path:

1. `strict_core_v1`
2. `strict_core_geometry_historical_alignment_k100`
3. `pointsim_conditional_meta_component`
4. Identity calibration after the two-input meta mapping

Supported diagnostics:

- Core probability confidence
- model disagreement
- historical-neighbor support
- data-quality/provenance diagnostics

Explicitly excluded from WTA v1:

- Profile-aware Genome geometry
- raw POINTSIM probability as a standalone forecast
- pure Surface Elo replacement
- universal composite uncertainty score
- hard PASS threshold

Rationale:

- WTA Profile-aware Genome geometry failed the stronger adversarial interpretation gate, while Core-geometry neighborhoods retained local residual value.
- POINTSIM-ADV-001 showed that frozen POINTSIM contains a small, historically stable incremental WTA signal beyond historical alignment.
- POINTSIM remains B/conditional: it enters only through the validated historical-alignment + POINTSIM statistical mapping.
- model disagreement is a diagnostic signal, not a frozen PASS policy.

## Prediction boundary

Every independent prediction must contain:

- immutable prediction ID and match ID;
- tour;
- creation timestamp;
- information cutoff timestamp;
- exact model version;
- architecture hash;
- `p_player_a` and `p_player_b` summing to one;
- optional component probabilities;
- diagnostics;
- input/source manifest hashes;
- reason codes.

The independent prediction object must not contain:

- bookmaker identity;
- market odds;
- no-vig market probability;
- edge;
- EV;
- stake;
- closing-line value;
- realized outcome;
- realized profit.

Those belong to separate downstream records.

## Timestamp semantics

`prediction_cutoff_at` is the latest timestamp of information legally consumed by the model. `created_at` may be equal to or later than the cutoff, but never earlier. Later creation does not authorize newer information: reproducibility is defined by the cutoff and the frozen input manifests.

## Architecture identity

The code representation of this specification is serialized deterministically and hashed with SHA-256. Any change to tour pathways, calibration status, diagnostics, exclusions, development cutoff, or version changes the architecture hash and therefore creates a distinct candidate rather than silently mutating `TGE-Independent-v1`.

## Abstention status

No hard `PASS`/`PREDICT` policy is promoted in v1.

The engine exposes validated diagnostic signals, but policy selection remains downstream research. A market-blind probability should not be suppressed merely because later betting logic may decide not to act.

## Market isolation

The market layer is a one-way downstream consumer:

`TGE-Independent-v1 -> market snapshot -> no-vig comparison -> decision policy -> paper-bet ledger`

There is no reverse arrow from market price into `TGE-Independent-v1`.

This isolation is permanent for this version so we can later measure whether the engine adds information beyond the market rather than accidentally training it to reproduce the market.

## Scientific status

Development-frozen means the research architecture is stable enough to use as a fixed reference for the next system layers. It does **not** mean:

- commercially production-ready data;
- independent forward confirmation of every late-added component;
- sportsbook edge;
- positive expected value;
- profitable betting;
- permission for real-money deployment.

Those require separate evidence.
