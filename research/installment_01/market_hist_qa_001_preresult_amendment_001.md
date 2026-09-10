# MARKET-HIST-QA-001 — Pre-Result Amendment 001

Status: **FROZEN BEFORE LICENSED BETFAIR DATA IS SUPPLIED OR INSPECTED**

## Purpose

Define the canonical coverage denominator correctly given the source-date semantics of the current canonical tennis tables.

## Canonical date semantics

The canonical `event_date` inherited from the research source is the tournament start date, not an exact per-match start timestamp.

Using `event_date` naively at the edges of a purchased Betfair date interval could therefore create false missingness. For example, a tournament beginning just before the purchased end date may contain later-round matches after the bundle ends.

## Boundary-safe denominator

For MARKET-HIST-QA-001 canonical coverage, a canonical match is denominator-eligible only when its tournament start date satisfies:

```text
requested_start_date <= event_date <= requested_end_date - 21 days
```

The 21-day end buffer is intentionally aligned with the already-frozen +21-day MARKET-HIST player-pair/tournament-start matching window.

Tournaments beginning before the purchased start date are excluded from the denominator even if some of their later rounds happen to appear in the Betfair bundle.

This creates a conservative **interior tournament cohort** for coverage measurement. It is not used to alter model probabilities or select matches based on outcomes.

## Numerator

The numerator remains denominator-eligible canonical completed, non-walkover, non-retirement matches with exactly one identity-resolved executable `CLOSE_PREPLAY` Betfair MATCH_ODDS observation.

## Annual labels

Annual coverage is assigned by canonical tournament-start year, consistent with the existing historical research chronology. Exact Betfair market timestamps remain preserved separately and must still be strictly pre-play.

## Unchanged

No QA threshold, MARKET-EDGE model, signal definition, multiplicity rule, or economic calculation changes here.
