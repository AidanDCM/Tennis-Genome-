# FULL-STACK-FORWARD-001 — Operational Amendment 002

Date: 2026-09-13

Status: **REGISTERED PRE-RESULT / N=0**

This amendment applies to `FULL-STACK-FORWARD-001`. It is separate from PATTERN-CONFIRM-001, which remains N=0 under its own frozen protocol.

## Purpose

Operational Amendment 001 hardened prediction timing, independent anchoring and provider-derived settlement. Amendment 002 closes a different evidence-integrity gap: an official prediction ledger alone does not prove that all candidate events entering the supervised collection process were accounted for. A selective process could otherwise record only successfully processed matches while silently omitting discovered events that failed input construction or operations.

This amendment therefore adds a versioned eligible-event census and mandatory reconciliation with the prospective pilot ledger.

## Scientific non-change

This amendment changes **operational denominator-integrity enforcement only**.

It does **not** change:

- TGE-Independent-v1 or any frozen model parameter;
- ATP/WTA architecture;
- the first-1,000-primary-eligible-matches-per-tour sample target;
- primary eligibility criteria for an individual completed prediction;
- Brier score or log-loss definitions;
- the strict-Core comparator;
- the paired-bootstrap procedure, seed, confidence level or incremental-value gate;
- tour separation;
- the no-peeking rule;
- market separation;
- any betting, staking or PASS rule.

The amendment was registered before prospective accrual. FULL-STACK-FORWARD-001 remains N=0.

## Required census

A supervised event that enters the registered discovery stream must be written to `FULL-STACK-FORWARD-001-census-v1` before its scheduled start using retained discovery evidence.

Each discovered event must receive exactly one terminal disposition:

1. `PREDICTED`
2. `NOT_ELIGIBLE`
3. `INPUT_UNAVAILABLE`
4. `EXCLUDED_PREMATCH`
5. `OPERATIONAL_FAILURE`

The allowed machine-readable reason codes are versioned in the census implementation. No ad-hoc `OTHER` reason is permitted.

Non-predicted dispositions require retained supporting evidence. Except for an operational failure that becomes known after the scheduled start, a terminal disposition must be recorded before scheduled start.

## Prediction linkage

A `PREDICTED` census disposition must bind:

- the exact prospective pilot `PREDICTION_COMMIT.record_sha256`;
- the canonical match ID.

Before registered outcome metrics are read, census/pilot reconciliation must pass through the analysis completeness cutoff.

Reconciliation requires:

- every `PREDICTED` census event maps to a real pilot prediction;
- no pilot prediction maps to multiple census events;
- every official pilot prediction has a `PREDICTED` census disposition;
- canonical match ID agrees;
- tour agrees;
- scheduled start agrees;
- the census predicted disposition does not predate the pilot prediction commitment;
- every discovered event scheduled at or before the completeness cutoff has a terminal disposition.

Failure of reconciliation blocks the formal read. It is an operational-integrity failure, not a reason to retroactively delete or repair unfavorable events.

## Relationship to the formal cohort

The registered primary cohort remains the first 1,000 primary-eligible completed singles matches per tour in prediction-commit order.

The census does not make an ineligible match eligible and does not add excluded rows to the primary probability score. Its role is to make the denominator and all operational exclusions visible so that successful prediction commits cannot be selectively presented without the surrounding discovered-event population.

Operational counts and reason distributions remain permissible before N=1,000 because they do not condition on match winners or model loss.

## Threat boundary

`FULL-STACK-FORWARD-001-census-v1` proves completeness **after entry into the supervised discovery stream**. It does not yet independently prove that the upstream provider discovery feed itself contained every theoretically eligible tennis event. Upstream provider-batch enumeration and external anchoring are separate future hardening possibilities.

The census local hash chain is tamper-evident against accidental edits and ordinary corruption but is not, by itself, an independent trusted timestamp against a determined operator with full local filesystem control.

These limitations must remain visible in any future audit statement.

## Non-claims

This amendment establishes no new evidence of predictive superiority, market mispricing, sportsbook edge, profitability or real-money readiness.
