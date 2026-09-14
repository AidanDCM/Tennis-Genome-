# Prospective provider-batch denominator layer

Status: **pre-result denominator-integrity infrastructure for FULL-STACK-FORWARD-001**.

This layer sits upstream of `FULL-STACK-FORWARD-001-census-v1`. Its purpose is to retain the
complete Sportradar daily-summary payload used for supervised discovery, classify every summary
in that retained payload, and prove that every in-scope event due through a declared completeness
cutoff entered the census.

It does not change TGE-Independent-v1, the formal cohort size, the registered probability metrics,
the paired-bootstrap gate, or any betting rule.

## Frozen tour-level scope

The historical TGE population was built from ATP and WTA **tour-level singles** files. The initial
baseline explicitly excluded qualifying, Challenger/ITF, Futures and doubles files. The prospective
provider-batch layer therefore uses the matching main-tour Sportradar categories:

- ATP: `sr:category:3`, category name `ATP`;
- WTA: `sr:category:6`, category name `WTA`.

The separate Sportradar WTA 125K category is outside this registered denominator scope. This is a
population-preservation rule, not a claim that WTA 125K matches are uninteresting or unusable in a
future separately registered experiment.

Category ID/name agreement is checked fail-closed. A known ID with a changed category name is
provider-semantic drift and invalidates the batch capture rather than being silently reinterpreted.

## Batch evidence

`ProviderBatchStore` retains two immutable evidence blobs for every capture:

1. the exact raw Sportradar daily-summary JSON bytes;
2. a deterministic manifest re-derived from those raw bytes.

Each store record is self-hashed and chained to the previous record. Verification reopens the exact
raw payload, rebuilds the manifest and requires byte-equivalent canonical content.

The manifest contains every provider summary, not only successfully modeled matches.

## Classification

Every summary receives exactly one batch classification:

- `CENSUS_REQUIRED`: main-tour ATP/WTA singles with a parseable scheduled start still in the
  pre-start discovery window;
- `OUT_OF_SCOPE`: a provider category outside the registered ATP/WTA tour-level population, or a
  non-singles competition;
- `DENOMINATOR_FAILURE`: an otherwise in-scope ATP/WTA singles event whose schedule cannot be
  parsed or whose first retained batch observation is already at/after scheduled start.

The batch layer intentionally does **not** require resolved competitors, a valid model input,
`start_time_confirmed=true`, or a friendly provider status before an event enters the census. Those
are downstream operational facts. Once a main-tour singles event is seen pre-start, failures such as
identity resolution, schedule quality, cancellation or model-input construction must be expressed as
versioned census dispositions rather than by removing the event from the denominator.

## Reconciliation

Before a registered formal read, `reconcile_batches_with_census(...)` must pass through the same
completeness cutoff used for census/pilot reconciliation.

For every batch event due through that cutoff:

- each `CENSUS_REQUIRED` provider event must have exactly the matching Sportradar census discovery;
- provider event ID, tour, event type and scheduled start must agree;
- any retained `DENOMINATOR_FAILURE` blocks reconciliation;
- a Sportradar census discovery due through the cutoff cannot exist without a retained provider-batch
  event;
- repeated retained observations of one provider event must not disagree on tour or scheduled start.

Future events beyond the declared cutoff stay retained but are not prematurely required to have a
census discovery.

## Threat boundary

This closes the **skip-after-batch-capture** gap: after a Sportradar daily payload is retained, an
in-scope event in that payload cannot silently disappear before the census.

It does **not yet** prove that the operator captured every required provider date/cadence, nor does the
local batch hash chain supply an independent trusted timestamp against a determined operator with full
filesystem control. Independent external anchoring and a mechanically enforced capture cadence are the
next hardening layer.

These limitations must remain visible. This infrastructure provides no evidence of predictive
superiority, sportsbook edge, profitability or real-money readiness.
