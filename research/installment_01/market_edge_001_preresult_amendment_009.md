# MARKET-EDGE-001 — Pre-Result Amendment 009

Status: **FROZEN BEFORE POWER-MDE-001, STAGE A, AND ANY BOOKMAKER-VS-SIGNAL RESULT**

## Trigger

While binding the accepted Profile Gap and GENOME-ADV artifacts under Amendment 008, an input-boundary issue was identified before any bookmaker-vs-signal result was opened: the accepted historical development reports contain embedded historical `outcome_a` labels and performance diagnostics in addition to the frozen signal fields.

The existing market loaders read only `match_id` plus the registered signal field and ignore those outcome/performance fields. Therefore this is not evidence of a statistical calculation leak. It is, however, unnecessarily weak for an outcome-locked Stage-A boundary because result-bearing development report files would physically enter the Stage-A process.

No `MARKET-EDGE-001`, `MARKET-EDGE-ADV-001`, bookmaker-vs-Profile-Gap, or bookmaker-vs-Genome result has been evaluated or inspected before this amendment.

## Frozen hardening

Before POWER-MDE-001, each accepted historical signal report must be deterministically projected into a physically outcome-free market-signal artifact.

Projection version: `market-signal-projection-v1`.

Each projection must:

1. verify the exact accepted parent artifact SHA-256 frozen in Amendment 008;
2. verify the parent `experiment_id` and `tour`;
3. read only canonical `match_id` and the already-frozen signal field;
4. reject duplicate or empty match IDs;
5. reject missing, non-numeric, or non-finite signal values;
6. sort rows deterministically by `match_id`;
7. emit only projection provenance and the required signal rows;
8. include a deterministic self SHA-256 over the unsigned projection payload;
9. contain no winner/outcome label, score, retirement/walkover flag, model correctness, Brier/log-loss result, calibration result, or other historical performance diagnostic.

## Frozen field mapping

No signal definition changes.

- ATP Profile Gap parent: `profile_gap_atp_strict.json`
  - parent SHA-256 `532ff66304914f0962e5747f20790916c70e082efedba695d26717632db946fd`
  - projected field: `profile_gap_match`
- WTA Profile Gap parent: `profile_gap_wta_strict.json`
  - parent SHA-256 `343903af5f53cd1d519ebafdabf6ddb2dd0645847ff77e1820a156caf012bc55`
  - projected field: `profile_gap_match`
- ATP Genome parent: `genome_adv_atp.json`
  - parent SHA-256 `37671b15b4f7bb4db98767f09a10f57dd43eb61baeacd2aed0713e8a67b298fa`
  - projected field: `full_neighbor_residual`
- WTA Genome parent: `genome_adv_wta.json`
  - parent SHA-256 `08df00ce43bed558f8d479f14e74bdb05504864ab0c4310aa3f3979029d0e2a3`
  - projected field: `core_neighbor_residual`

The tour-specific Genome field mapping is the already-frozen behavior of `load_genome_values`; this amendment only makes the physical input boundary match that existing behavior.

## Stage-A binding

POWER-MDE-001 and the bookmaker Stage-A seal must consume the four `market-signal-projection-v1` files, not the result-bearing parent reports.

The parent report hashes remain frozen provenance and must be carried inside the projections. Stage B, if later authorized, must consume the exact same projected files sealed at Stage A.

## Unchanged methodology

This amendment does not change:

- the four confirmatory claims;
- any signal value;
- any signal orientation;
- `family_size = 4`;
- alpha `0.05`;
- conservative planning alpha `0.0125`;
- Holm correction;
- `min_prior_rows = 1000`;
- chronological fitting/evaluation;
- BOOKMAKER_CLOSE_V1 source semantics;
- proportional no-vig transform;
- any coverage threshold;
- the 2025-12-31 boundary;
- any result/promotion rule.

This is an outcome-firewall implementation hardening made before confirmatory market scoring.
