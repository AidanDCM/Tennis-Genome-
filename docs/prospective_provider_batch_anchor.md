# Prospective provider-batch external anchor and capture cadence

Status: **pre-result denominator-integrity infrastructure for FULL-STACK-FORWARD-001**.

This layer extends the retained provider-batch denominator ledger with an external-time attestation and
a mechanically checked capture cadence. It does not alter TGE-Independent-v1 or the registered
probability experiment.

## Why this exists

The retained provider-batch ledger proves what was present once a Sportradar daily-summary payload was
stored, but its local observation timestamp and hash chain are controlled by the operator's filesystem.
A determined operator could otherwise backdate a local batch or omit an entire scheduled capture.

The anchor/cadence layer addresses those two threats separately:

1. GitHub Actions provides an external server timestamp proving that the exact batch record/digests
   existed no later than the GitHub run `created_at` time;
2. a frozen UTC slot schedule makes missing provider captures mechanically detectable.

## External batch anchor

Every retained provider batch used to satisfy formal denominator completeness must be anchored through
`.github/workflows/provider_batch_anchor.yml` immediately after capture.

The workflow receipt binds:

- provider-batch record SHA-256;
- the claimed immediate batch-chain head;
- queried schedule date;
- local batch `observed_at`;
- exact raw Sportradar payload SHA-256;
- deterministic manifest SHA-256;
- repository, workflow source SHA and GitHub run ID.

Local verification also retains the complete GitHub workflow-run metadata JSON. The trusted anchor time
is the GitHub server `created_at` value. The runner's own receipt timestamp is provenance only.

The verifier requires the workflow run to be:

- `workflow_dispatch`;
- completed successfully;
- from repository `AidanDCM/Tennis-Genome-`;
- from `.github/workflows/provider_batch_anchor.yml`;
- dispatched from `main`;
- source-SHA consistent with the receipt.

The external anchor must be created no more than one hour after the local observation timestamp, with a
five-minute tolerance for local/server clock skew. This prevents a substantially retrospective GitHub
anchor from legitimizing a backdated local capture.

For event-level denominator trust, a locally pre-start provider event is accepted only if at least one
retained batch containing that event also has a verified GitHub server anchor strictly before that
event's scheduled start.

## Frozen capture cadence

Formal prospective collection uses four UTC slots per day:

- 00:00 UTC;
- 06:00 UTC;
- 12:00 UTC;
- 18:00 UTC.

Each slot has a one-hour capture/anchor window beginning at the slot time. For **every** due slot, the
operator must retain and externally anchor two Sportradar daily-summary payloads:

1. the slot's UTC calendar date (`D`);
2. the following UTC calendar date (`D+1`).

Example: the 12:00 UTC slot on 2026-09-15 requires anchored daily-summary batches for both
2026-09-15 and 2026-09-16, with the local observations and GitHub server anchors occurring between
12:00 and 13:00 UTC.

A slot is considered due only once its one-hour window has closed. `verify_capture_cadence(...)`
requires every `slot x {D,D+1}` pair due through the declared completeness time to have anchored
coverage. Any missing pair fails closed.

The six-hour spacing plus D/D+1 overlap does not guarantee that a provider can never add a match at
short notice. Instead, any in-scope match first observed only after scheduled start remains a
`DENOMINATOR_FAILURE` under Operational Amendment 003 and blocks the formal read. The cadence makes
that failure auditable rather than silently invisible.

## Formal reconciliation

A registered formal read must use the combined gate
`reconcile_anchored_batches_with_census(...)`, which requires all of the following:

1. the retained provider-batch store verifies;
2. the external anchor store verifies;
3. fixed-slot D/D+1 cadence is complete through the analysis cutoff;
4. Amendment-003 provider-batch/census reconciliation passes;
5. every due `CENSUS_REQUIRED` event has at least one externally timestamped pre-start batch.

An unanchored additional batch cannot rescue an event. A GitHub anchor created after an event's
scheduled start cannot establish pre-start denominator eligibility even if the local `observed_at`
claims an earlier time.

## Coverage start

The cadence structure is frozen here at N=0. The concrete `coverage_start` must be recorded as an exact
00:00/06:00/12:00/18:00 UTC slot **before formal prospective accrual begins**. It should be the first
slot after the genuine supervised end-to-end production dry run has succeeded. Data collected before
that registered start remains diagnostic and cannot retroactively establish cadence coverage.

## Operator sequence

For each UTC slot:

1. query Sportradar daily summaries for D;
2. capture the raw JSON with the provider-batch ledger;
3. immediately dispatch the provider-batch anchor workflow using the resulting record/digest fields;
4. save the workflow receipt artifact and GitHub run metadata;
5. attest the batch anchor locally;
6. repeat steps 1-5 for D+1;
7. verify both local ledgers.

The current ChatGPT GitHub connector does not expose workflow dispatch, so implementation/testing of the
workflow and verifier does **not** count as a genuine external anchor run. The first real dispatch remains
part of the supervised production dry run.

## Threat boundary

This substantially reduces operator discretion but does not make GitHub itself an infallible external
notary. The local verifier consumes retained GitHub run metadata rather than independently querying
GitHub on every verification. A durable run ID/URL therefore remains part of the audit trail, and a
formal audit should confirm the referenced run externally.

GitHub artifact retention is currently 90 days; the local receipt/run evidence must remain retained
indefinitely for the experiment. Long-term archival of the externally visible receipt/run metadata can
be hardened further without changing the frozen statistical experiment.

This layer establishes no evidence of predictive superiority, sportsbook edge, profitability,
autonomous wagering readiness or real-money readiness.
