# FULL-STACK-FORWARD-001 — Operational Amendment 003

Date: 2026-09-14

Status: **REGISTERED PRE-RESULT / N=0**

This amendment applies to `FULL-STACK-FORWARD-001`. It is separate from PATTERN-CONFIRM-001,
which remains N=0 under its own frozen protocol.

## Purpose

Operational Amendment 002 added a mandatory census after an event entered the supervised discovery
stream. That still left a narrower upstream gap: once a Sportradar daily-summary payload had been
queried, an operator could theoretically omit one event from the census before creating any census
record for it.

Amendment 003 therefore adds `FULL-STACK-FORWARD-001-provider-batch-v1`, an append-only retained
provider-batch ledger. It preserves the exact Sportradar daily-summary response, deterministically
classifies every summary in that response, and requires batch/census reconciliation before a formal
registered read.

## Scientific non-change

This amendment changes **operational denominator-integrity enforcement only**.

It does **not** change:

- TGE-Independent-v1 or any frozen model parameter;
- ATP/WTA architecture;
- the first-1,000-primary-eligible-matches-per-tour sample target;
- primary eligibility criteria for a completed prediction;
- Brier score or log-loss definitions;
- the strict-Core comparator;
- the paired-bootstrap procedure, seed, confidence level or incremental-value gate;
- tour separation;
- the no-peeking rule;
- market separation;
- any betting, staking or PASS rule.

The amendment is registered before prospective accrual. FULL-STACK-FORWARD-001 remains N=0.

## Frozen prospective population interpretation

The registered prospective cohort refers to ATP and WTA singles. The frozen historical population
used tour-level ATP/WTA singles files and explicitly excluded qualifying, Challenger/ITF, Futures and
doubles files.

For provider-batch enumeration, the matching main-tour Sportradar categories are therefore frozen as:

- ATP: `sr:category:3`, category name `ATP`;
- WTA: `sr:category:6`, category name `WTA`.

The separate WTA 125K category is outside this registered denominator scope because it is not part of
the original tour-level population definition. This is a scope-preservation decision made at N=0,
not a post-result exclusion.

A known category ID whose provider category name no longer agrees with this frozen interpretation is
provider-semantic drift and must fail closed.

## Required provider-batch evidence

Every retained provider batch contains:

1. the exact raw Sportradar daily-summary JSON bytes;
2. a deterministic manifest derived only from those bytes plus the declared provider-observation time
   and queried schedule date;
3. a self-hashed append-only batch record chained to the prior batch record.

Verification must reopen the raw evidence, validate its digest, rebuild the manifest and require exact
canonical agreement with the retained manifest.

Every provider summary must remain represented in the manifest. No summary may be dropped because a
model input, identity mapping, competitor field, schedule confirmation or prediction operation later
fails.

## Deterministic batch classifications

Every provider summary receives exactly one of:

- `CENSUS_REQUIRED`: a main-tour ATP/WTA singles event with a parseable scheduled start that was
  observed before scheduled start;
- `OUT_OF_SCOPE`: a provider category outside the frozen ATP/WTA tour-level population or a non-singles
  competition;
- `DENOMINATOR_FAILURE`: an otherwise in-scope ATP/WTA singles event whose schedule is invalid or whose
  first retained observation is already at/after scheduled start.

Provider status, competitor resolution, `start_time_confirmed`, model-input availability and eventual
finish status do not remove a pre-start main-tour singles event from the census requirement. Those
facts belong to downstream census dispositions and formal primary-eligibility checks.

## Batch/census reconciliation

Before registered outcome metrics are read, provider-batch/census reconciliation must pass through the
analysis completeness cutoff.

For events due through that cutoff:

- every `CENSUS_REQUIRED` batch event must map to exactly the corresponding Sportradar census discovery;
- provider event ID, tour, singles event type and scheduled start must agree;
- every retained `DENOMINATOR_FAILURE` blocks the formal read;
- every Sportradar census discovery due through the cutoff must be present in retained batch evidence;
- repeated retained observations of one provider event must not disagree on tour or scheduled start.

Future events beyond the declared cutoff remain retained but do not become prematurely due for census
reconciliation.

## Threat boundary

This amendment proves completeness **after a Sportradar provider batch has been retained**. It closes
the skip-after-batch-capture gap but does not yet independently prove that every required provider date
or capture cadence was queried.

The local provider-batch chain is tamper-evident against accidental edits and ordinary corruption, but
is not an independent trusted timestamp against a determined operator with full filesystem control.
A separately anchored capture cadence is the next hardening layer.

These limitations must remain visible in any future audit statement.

## Non-claims

This amendment establishes no evidence of predictive superiority, market mispricing, sportsbook edge,
profitability or real-money readiness.
