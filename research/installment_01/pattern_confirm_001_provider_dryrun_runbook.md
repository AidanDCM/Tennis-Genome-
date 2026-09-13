# PATTERN-CONFIRM-001 Credentialed Provider Dry-run Runbook

This runbook operates the transport-only gate frozen by Pre-result Amendment 009. It does **not** start confirmatory accumulation.

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

## Expected outputs

A completed dry run attempts to upload one artifact named like:

`pattern-confirm-provider-dryrun-<run_id>`

The artifact contains only the sanitized output directory emitted by `pattern_confirm_provider_dryrun`, including when available:

- `snapshot_1.json`
- `snapshot_2.json`
- `provider_dryrun_report.json`

The workflow is expected to fail when the dry-run report fails closed. The artifact is still uploaded first so the operational cause can be inspected without rerunning blindly.

## Interpretation

A successful workflow proves only that the live provider transport/schema/alignment/stability gate is operationally compatible at that execution.

It does **not** prove either selected hypothesis, authorize a bet, append a prospective live row, or increase confirmatory N.

Before the first row can enter `PATTERN-CONFIRM-001`, the event must still pass all frozen downstream contracts, including:

1. unique verified market-to-Sportradar-to-canonical identity;
2. complete legal Sportradar state capture and source-package construction;
3. internally reproduced frozen Profile/Core values;
4. live-row provenance/hash/chronology checks; and
5. after settlement, the independent Sportradar `match_started` actual-start audit proving the Pinnacle snapshot was at least five minutes pre-start and the prediction was committed before start.

Until those gates pass for an individual match, the match contributes zero confirmatory N.

## Failure discipline

Do not fix a failed dry run by changing the scientific market, substituting another bookmaker, reducing the five-minute checkpoint, weakening identity uniqueness, lowering the snapshot separation, or accepting incomplete state.

A provider/API/schema defect should be diagnosed as an operational defect. Any change that would alter the frozen scientific population or semantics requires a new pre-result amendment while N is still zero.
