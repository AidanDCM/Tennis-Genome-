# Champion–Challenger Shadow Framework v1

Status: **DEVELOPMENT INFRASTRUCTURE — DOES NOT MODIFY THE FROZEN CHAMPION**

This phase implements the first execution layer from the Tennis Genome V2 roadmap.

## Guarantees

- `TGE-Independent-v1` remains unchanged.
- Challengers are `SHADOW_ONLY` and content-addressed.
- The same immutable `CommonPreMatchSnapshot` binds every side-by-side challenger record.
- Snapshot feature payloads reject outcome and market semantics.
- Challenger predictions created at or after scheduled start are rejected.
- Prediction, registration, snapshot, anchor and settlement hashes are checked explicitly.
- External anchors must be unedited `github-actions[bot]` commitments and pre-start.
- Settlement winner identity must match the frozen A/B orientation.
- Challenger score aggregation refuses unknown, duplicate or hash-mismatched settlements.
- Failure Atlas rows clearly separate immutable pre-match diagnostics from post-result diagnostics.
- Failure Atlas output is hypothesis-generating only and has no production-retuning authority.

## Implemented records

- `ChallengerRegistration`
- `CommonPreMatchSnapshot`
- `ShadowModelOutput`
- `ShadowPredictionRecord`
- `ShadowPredictionAnchor`
- `ShadowSettlementRecord`
- `ChallengerLeagueRow`
- `FailureAtlasRecord`

## Implemented operations

- bind challenger output to a common snapshot;
- verify trusted external shadow anchor;
- verify one-snapshot side-by-side prediction sets;
- settle and score shadow predictions;
- build challenger league-table summaries;
- build deterministic Failure Atlas rows.

## Next integration step

Wire registered challenger generation into the live morning prediction workflow so the champion and eligible challengers consume one retained pre-match evidence snapshot, then extend the night settlement workflow to score the linked shadow records and append Failure Atlas rows. No challenger becomes production merely by being present in the shadow league.
