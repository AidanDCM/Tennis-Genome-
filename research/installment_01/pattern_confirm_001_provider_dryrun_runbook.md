# PATTERN-CONFIRM-001 Credentialed Provider Dry-run Runbook

This runbook operates the transport-only gate frozen by Pre-result Amendment 009 and interpreted together with the prospective correctness repair in Amendment 010. It does **not** start confirmatory accumulation.

## Current evidence state

`PATTERN-CONFIRM-001` remains at **prospective N=0**. A green repository, synthetic tests or a successful transport dry run cannot by themselves convert the experiment to live accumulation.

Before the first eligible live row can count, every frozen production gate must pass under the repaired execution semantics, including canonical Player A/B orientation, stable provider-event uniqueness, complete frozen-history binding, source-package verification, chronology/timing and later actual-start audit.

## Required repository secrets

Configure these as GitHub Actions repository secrets. Do not paste either value into chat, source code, workflow inputs, issues, pull requests, logs or artifacts.

- `THE_ODDS_API_KEY`
- `SPORTRADAR_API_KEY`

The workflow reads them only through its runtime environment.

## Manual execution

Run the GitHub Actions workflow named:

`PATTERN-CONFIRM Provider Dry-run`

Choose the Sportradar access level that corresponds to the configured credential:

- `trial`, or
- `production`.

The workflow always uses a 300-second separation between its two provider snapshots. That interval is not an operator-tunable scientific parameter.

## Frozen provider roles

The dry run must test the providers already frozen for this experiment:

- Pinnacle through The Odds API v4 (`THE_ODDS_API_V4_PINNACLE_V1`) for the H2H market snapshot;
- Sportradar Tennis v3 (`SPORTRADAR_TENNIS_V3`) for stable event/player identity and eventual actual-start authority.

Do not substitute another bookmaker or provider to make the transport gate pass.

Provider home/away order is not the scientific Player A/B convention. Historical/live inference uses sorted canonical player IDs. Any provider-side names, IDs and later odds/state must remain attached to the correct real player when converted into canonical orientation.

## Expected outputs

A completed dry run attempts to upload one artifact named like:

`pattern-confirm-provider-dryrun-<run_id>`

The artifact contains only the sanitized output directory emitted by `pattern_confirm_provider_dryrun`, including when available:

- `snapshot_1.json`
- `snapshot_2.json`
- `provider_dryrun_report.json`

The workflow is expected to fail when the dry-run report fails closed. The artifact is still uploaded first so the operational cause can be inspected without rerunning blindly.

## Interpretation

A successful workflow proves only that the frozen live provider transport/schema/alignment/stability gate was operationally compatible at that execution.

It does **not** prove either selected hypothesis, authorize a bet, append a prospective live row, settle a row, inspect an outcome or increase confirmatory N.

Before the first row can enter `PATTERN-CONFIRM-001`, the target must still pass all frozen downstream contracts, including:

1. unique verified The Odds API ↔ Sportradar ↔ canonical identity;
2. canonical Player A/B ordering identical to historical training;
3. complete legal Sportradar state capture and source-package construction;
4. frozen base-history population hash **and** full semantic history digest `8be80277f80d5ca8bf34ce2df52d3393bc72cc7d92787772772dc2571a5c1f02`;
5. internally reproduced frozen Profile/Core values;
6. live-row provenance/hash/chronology/state checks;
7. uniqueness of internal match ID, market event ID and Sportradar sport-event ID across the ledger; and
8. after settlement, the independent Sportradar timeline audit proving the market snapshot was at least five minutes before the earliest `match_started` event and the prediction was committed before start.

If actual start is unavailable, do not fall back to scheduled start. The row is `ACTUAL_START_UNVERIFIED` and contributes zero N.

## Fixed-look protection

A transport-compatible match is still only a candidate row. When eligible rows are eventually settled, confirmatory evaluation must advance through a resolved chronological prefix. A later settlement cannot replace an unresolved earlier qualifying match merely to reach a fixed look.

Completed look membership and its input digest are persisted. A rerun that changes an already completed look must fail closed.

## Failure discipline

Do not fix a failed dry run or downstream gate by changing the scientific market, substituting another bookmaker, reducing the five-minute checkpoint, weakening canonical orientation or identity uniqueness, lowering the snapshot separation, accepting incomplete state, changing the frozen history, or altering a hypothesis/correction.

A provider/API/schema defect should be diagnosed as an operational defect. Any change that would alter the frozen scientific population or semantics requires a new pre-result amendment while N is still zero.