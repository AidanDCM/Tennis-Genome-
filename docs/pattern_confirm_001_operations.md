# PATTERN-CONFIRM-001 operations

This runbook is deliberately conservative. The scientific design is frozen; operations must reproduce it exactly rather than optimize it after future results appear.

## Current state

- Prospective cutoff: `2026-09-12T00:00:00-04:00`.
- Status: `ACCUMULATING`, **N=0** for both hypotheses.
- Frozen market provider: Pinnacle through The Odds API v4, identifier `THE_ODDS_API_V4_PINNACLE_V1`.
- Frozen identity / actual-start / settlement authority: Sportradar Tennis v3, identifier `SPORTRADAR_TENNIS_V3`.
- Current live wire contract: `pattern-confirm-live-v6`.
- Frozen production Profile artifact SHA-256: `cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351`.
- Frozen production Core artifact SHA-256: `5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7`.
- Frozen Market+Core fit SHA-256: `622d07e4a5d010b927ddf1c37900868a61d2e81d67c287f2a41dddaf4932b732`.
- Frozen training population: 75,112 ATP matches; population SHA-256 `c2c5b4ddcd30f68d75b98a9b5e460ff71d4601b50115695bb1784c8f5f897d2c`.
- Frozen complete base-history semantic SHA-256: `8be80277f80d5ca8bf34ce2df52d3393bc72cc7d92787772772dc2571a5c1f02`.

Pre-result Amendment 010 supersedes the earlier live execution assumptions where necessary. It repairs prospective correctness while leaving the hypotheses, thresholds, corrections, alpha allocation, O'Brien-Fleming boundaries, look Ns, provider choices, five-minute timing rule, model coefficients and promotion rules unchanged. Pre-result Amendment 011 further hardens settlement provenance at the same reported prospective N=0: outcomes and nonstandard-finish flags are derived from terminal Sportradar status/winner evidence rather than operator assertions, without changing any scientific rule.

The repository is **not authorized to accrue confirmatory N merely because the implementation and tests are green**. A real credentialed outcome-blind provider dry run and the remaining frozen production gates must pass before any live row can count.

## Canonical Player A/B orientation

Historical training defines Player A/B by sorted canonical player ID. Live provider home/away order is transport metadata only.

Before inference, the complete live path must place the two real players into the same historical canonical order and keep every side-specific item attached to that real player:

- canonical IDs and names;
- Sportradar competitor IDs and profiles;
- market names and Pinnacle prices;
- target pre-match state;
- Profile Gap and Core inputs;
- hypothesis membership and fixed correction;
- settlement outcome.

Do not use Sportradar `home` as scientific Player A. Do not apply a correction in provider order and swap only the display afterward.

## Frozen base-history identity

The original training-population hash remains required, but it is not sufficient by itself because it does not cover every feature-bearing field.

Production state reconstruction must also match the complete frozen semantic base-history digest:

`8be80277f80d5ca8bf34ce2df52d3393bc72cc7d92787772772dc2571a5c1f02`

Its derivation is recorded in:

`research/installment_01/pattern_confirm_001_base_history_derivation.json`

That derivation rebuilds the exact pinned ATP 2000-2025 source with the original production-freeze canonicalization code, reproduces the frozen 75,112-row population/hash, verifies the canonical files, then seals the complete semantic content consumed by state reconstruction, including feature-bearing pre-match fields and historical match statistics.

Do not substitute the old manifest JSON SHA as the new content identity. The manifest contains a volatile `built_at_utc` field.

## Provider dry run

The transport-only workflow is:

`PATTERN-CONFIRM Provider Dry-run`

It is manually dispatched and uses repository secrets `THE_ODDS_API_KEY` and `SPORTRADAR_API_KEY`. It captures two outcome-blind snapshots separated by at least 300 seconds and does not append a live row, settle a match, inspect a result or increase N.

See:

`research/installment_01/pattern_confirm_001_provider_dryrun_runbook.md`

A successful transport dry run is necessary but not sufficient for accumulation.

## Required live inputs

The production live firewall requires the frozen contracts and sealed provenance inputs rather than externally supplied `profile_gap` or `core_probability` numbers:

- frozen Market+Core fit;
- frozen Profile artifact;
- frozen Core artifact;
- sealed market-to-Sportradar-to-canonical identity mappings;
- sealed canonical crosswalk;
- sealed source packages / prospective states;
- raw pre-match Pinnacle snapshots for candidate rows.

The source-package path must reproduce Profile Gap and Core internally from the frozen artifacts and verified state.

## Append live rows

Use the live firewall, not the legacy generic prospective logger:

```bash
python -m tennis_genome.experiments.pattern_confirm_live \
  --fit research/installment_01/pattern_confirm_001_market_core_fit.json \
  --profile-artifact research/installment_01/profile_production_001.json \
  --core-artifact research/installment_01/core_production_001.json \
  --identity-mappings identity_mappings.jsonl \
  --crosswalk canonical_crosswalk.json \
  --source-packages source_packages.jsonl \
  append \
  --existing prospective_live_ledger.jsonl \
  --input new_live_batch.jsonl \
  --output prospective_live_ledger.next.jsonl
```

Before promoting `prospective_live_ledger.next.jsonl`, preserve the previous ledger atomically/versioned.

The live ledger fails closed on model/provenance/timing/state mismatches and requires uniqueness across all three stable identities:

1. internal `match_id`;
2. The Odds API `market_event_id`;
3. Sportradar `sport_event_id`.

An alias or regenerated internal ID must never allow the same underlying event to enter twice.

## Five-minute pre-start checkpoint

A Pinnacle snapshot can count only when it is at least five minutes before the verified actual match start.

Actual start is the earliest Sportradar timeline `match_started` event for the same stable Sportradar sport-event ID. Scheduled start is not an acceptable fallback for this audit. If actual start cannot be verified, the row remains `ACTUAL_START_UNVERIFIED` and contributes zero N.

Prediction generation and prediction commitment must also precede actual start under the frozen timing contract.

## Settlement

Outcomes remain physically separate from pre-match predictions. Under `pattern-confirm-live-v6`, settlement input must contain the same stable Sportradar event ID, a Sportradar timeline/status payload, and a timezone-aware `observed_at`. The provider status must be terminal (`ended` or `closed`), the provider must supply `winner_id`, and that winner must be one of the two Sportradar competitor IDs already sealed into the prospective record. When actual start is available, settlement observation cannot precede it.

Do **not** supply `outcome_a`, `retirement`, or `walkover` as operator assertions. `outcome_a` is derived mechanically by resolving provider `winner_id` against the prospective record's canonical A/B competitor IDs. Recognized provider `winning_reason` values derive retirement/default/walkover exclusions; those rows do not contribute to the confirmatory statistic.

Preserve the settlement source payload/digest and observation time with the audit evidence. A manual override, if ever required operationally, must remain an explicit separately audited exception rather than silently entering the confirmatory settlement loader.

Settlement cannot repair an invalid pre-match row. A row that failed identity, provider, chronology, data-quality, source-package, model or timing gates remains ineligible.

## Evaluate accumulation and persist fixed-look membership

Evaluate with an explicit persisted look-state file:

```bash
python -m tennis_genome.experiments.pattern_confirm_live \
  --fit research/installment_01/pattern_confirm_001_market_core_fit.json \
  --profile-artifact research/installment_01/profile_production_001.json \
  --core-artifact research/installment_01/core_production_001.json \
  --identity-mappings identity_mappings.jsonl \
  --crosswalk canonical_crosswalk.json \
  --source-packages source_packages.jsonl \
  evaluate \
  --ledger prospective_live_ledger.jsonl \
  --settlements settled_outcomes.jsonl \
  --look-state pattern_confirm_look_state.json \
  --output pattern_confirm_status.json
```

For each hypothesis, evaluation advances only through the resolved chronological prefix. An unresolved earlier qualifying match blocks a later qualifying match from being substituted into a fixed look. Explicit terminal exclusions may be resolved without contributing N.

Every completed look records its exact match IDs and an input digest. The persisted look-state file is part of the confirmatory audit trail. A later evaluation must fail if an already completed look disappears or changes membership/result.

Frozen cumulative looks remain:

- `PC-ATP-PG-LOW`: 524, 1,047, 1,570, 2,094 eligible matches.
- `PC-ATP-PG-ABS-HIGH`: 936, 1,872, 2,808, 3,744 eligible matches.

A match may count in both hypotheses only when it mechanically satisfies both frozen rules.

## Fail-closed discipline

Do not resolve an operational failure by:

- changing the bookmaker or provider;
- weakening the five-minute checkpoint;
- using scheduled start when actual start is unverified;
- weakening canonical identity/event uniqueness;
- changing canonical Player A/B orientation;
- accepting incomplete or stale state;
- changing a hypothesis threshold or correction;
- skipping an unresolved earlier match to fill a look;
- reconstructing an allegedly pre-match row after the match;
- altering the frozen historical base to make a state build pass.

A genuine scientific-contract change, if ever necessary, requires a separately documented pre-result amendment while prospective N is still zero. Operational defects should otherwise fail closed.