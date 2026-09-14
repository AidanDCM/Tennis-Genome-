# Prospective eligible-event census

Status: **pre-result denominator-integrity infrastructure for FULL-STACK-FORWARD-001**.

The event census exists to prevent a prospective evidence process from recording only the matches that happened to receive predictions while silently losing other discovered candidate events. It is separate from PATTERN-CONFIRM-001 and does not change either experiment's N.

## Scope

The census operates beside `FULL-STACK-PILOT-001-ledger-v1`.

The pilot ledger proves the integrity, timing, anchoring and later settlement of official predictions. The census answers a different question: **what happened to every event that entered the supervised discovery stream?**

Each discovered event must receive exactly one terminal disposition:

- `PREDICTED` — an official pilot prediction was committed;
- `NOT_ELIGIBLE` — the event failed a frozen structural eligibility rule;
- `INPUT_UNAVAILABLE` — required pre-match model inputs could not be constructed;
- `EXCLUDED_PREMATCH` — retained pre-match evidence failed a frozen calculator/source/schedule contract;
- `OPERATIONAL_FAILURE` — the event should have been processed but the supervised pipeline failed or missed the commit window.

There is deliberately no free-form `OTHER` status or reason. Every terminal status has a frozen machine-readable reason-code set.

## Discovery evidence

Discovery evidence uses schema:

`full-stack-forward-census-discovery-v1`

A retained discovery object contains at least:

- provider;
- provider event ID;
- tour;
- event type;
- observation time;
- scheduled start;
- optional canonical match ID if already resolved.

Discovery must be recorded before scheduled start. The canonical event key is `provider:provider_event_id`, so the same provider event cannot be entered twice.

Example:

```text
python -m tennis_genome.prospective.census discover \
  --store prospective/full_stack_forward_001_census \
  --evidence discovered_event.json
```

The exact evidence bytes are retained by SHA-256. The resulting discovery record enters an append-only local hash chain.

## Terminal disposition

A discovered event remains visibly open until it receives exactly one terminal disposition.

Example non-predicted disposition:

```text
python -m tennis_genome.prospective.census dispose \
  --store prospective/full_stack_forward_001_census \
  --discovery-record-sha256 <discovery-record-sha> \
  --status INPUT_UNAVAILABLE \
  --reason-code FOUNDATIONAL_STATE_UNAVAILABLE \
  --disposed-at 2026-09-20T09:30:00-04:00 \
  --supporting-evidence input_failure.json
```

Non-predicted dispositions require retained supporting evidence. Except for `OPERATIONAL_FAILURE`, the disposition must be recorded before scheduled start. Operational failures may be recognized immediately after start, but remain explicit denominator failures rather than disappearing.

A `PREDICTED` disposition requires both the exact pilot prediction record SHA-256 and canonical match ID:

```text
python -m tennis_genome.prospective.census dispose \
  --store prospective/full_stack_forward_001_census \
  --discovery-record-sha256 <discovery-record-sha> \
  --status PREDICTED \
  --reason-code PREDICTION_COMMITTED \
  --disposed-at 2026-09-20T09:45:00-04:00 \
  --prediction-record-sha256 <pilot-prediction-record-sha> \
  --match-id <canonical-match-id>
```

The census does not trust that linkage by itself. Formal reconciliation cross-checks it against the pilot ledger.

## Frozen reason codes

### `PREDICTED`

- `PREDICTION_COMMITTED`

### `NOT_ELIGIBLE`

- `UNSUPPORTED_TOUR`
- `NOT_SINGLES`
- `UNSUPPORTED_BEST_OF`
- `EVENT_CANCELLED_PREMATCH`

### `INPUT_UNAVAILABLE`

- `SOURCE_MANIFEST_UNAVAILABLE`
- `FOUNDATIONAL_STATE_UNAVAILABLE`
- `PROFILE_STATE_UNAVAILABLE`
- `SERVE_RETURN_STATE_UNAVAILABLE`
- `IDENTITY_UNRESOLVED`

### `EXCLUDED_PREMATCH`

- `CALCULATOR_CONTRACT_REJECTED`
- `PREMATCH_SOURCE_INVALID`
- `SCHEDULE_INVALID`

### `OPERATIONAL_FAILURE`

- `MISSED_COMMIT_WINDOW`
- `PIPELINE_FAILURE`

Changing these codes after prospective accrual begins is a protocol change and must be versioned rather than silently edited.

## Pilot reconciliation

`reconcile_with_pilot(...)` verifies both stores and then requires:

- every `PREDICTED` census event references a real earlier pilot prediction record;
- one pilot prediction cannot be linked to multiple census events;
- every official pilot prediction has exactly one `PREDICTED` census disposition;
- census and pilot canonical match ID agree;
- tour agrees;
- scheduled start agrees;
- the census `PREDICTED` disposition does not predate the actual pilot prediction commitment;
- at an analysis completeness cutoff, every discovered event whose scheduled start is at or before the cutoff has a terminal disposition.

Formal FULL-STACK-FORWARD-001 analysis should require successful reconciliation through the analysis cutoff before any registered outcome metrics are read.

## Verification

```text
python -m tennis_genome.prospective.census verify \
  --store prospective/full_stack_forward_001_census
```

Verification recomputes record hashes, chain order, retained evidence hashes, discovery identity, observation/start chronology, uniqueness, terminal status/reason validity and open-event counts. For every terminal disposition it also reopens the canonical `disposition_evidence_sha256` blob and requires event identity, status, reason, disposition time, prediction linkage, and match ID to reproduce exactly.

## Threat boundary

This v1 census closes **silent dropping after discovery**: once an event is written into the supervised discovery stream, it must remain visible and receive a terminal disposition.

It does **not yet prove that the upstream provider discovery feed itself was complete**. A determined operator could theoretically omit an event before it ever reaches the census. Provider-batch capture, batch hashing/anchoring, or another independently enumerable schedule source is the next hardening layer if complete upstream denominator proof becomes necessary.

The local census hash chain is tamper-evident against accidental edits and ordinary corruption, not an independent trusted timestamp against a determined operator with full filesystem control. The pilot's GitHub anchor remains the independent pre-start timestamp for official predictions.

## Non-claims

The census does not establish predictive value, betting edge, profitability, market efficiency failure or real-money readiness. It is denominator-integrity infrastructure for a prospective probability experiment.
