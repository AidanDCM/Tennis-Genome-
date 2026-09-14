# Sportradar Historical Start-Time Candidate 001

Status: **CANDIDATE SOURCE — NOT YET ADMITTED**

Audit date: 2026-09-14

## Purpose

Evaluate whether retained Sportradar Tennis v3 evidence can support a separate recent exact-time historical panel for v2 dynamic-state research.

This does **not** replace the long-history Sackmann-style panel and does not change any frozen model or experiment.

## Why this source is promising

Sportradar Tennis v3 exposes two different time concepts that must not be conflated:

1. schedule-level `sport_event.start_time`, with `start_time_confirmed` and `estimated` metadata;
2. event-timeline entries with typed events such as `match_started` and an event-level UTC `time`.

Primary documentation:

- https://developer.sportradar.com/tennis/reference/sport-event-summary
- https://developer.sportradar.com/tennis/reference/sport-event-timeline
- https://developer.sportradar.com/tennis/docs/tennis-ig-historical-data
- https://developer.sportradar.com/tennis/docs/tennis-ig-schedules

For historical state ordering, the timeline's typed `match_started` event is the stronger candidate than a schedule slot. A scheduled start can move or be estimated; the timeline is the event history.

## Historical-window limitation

Sportradar documents a rolling season catalog rather than unlimited match-season history. Past seasons remain available only while they are still inside the provider's catalog window, and the documentation recommends archiving needed historical data before an edition ages out.

Therefore this source is a candidate for a **recent exact-time panel**, not a replacement for the pinned 2000–2025 long-history research source.

The long-history and exact-time panels must remain separately fingerprinted and separately described.

## Candidate chronology definition

A match may receive an exact historical start timestamp only when retained source evidence contains a timeline event satisfying all of the following:

- `type == "match_started"`;
- `time` is a valid timezone-aware UTC-normalizable timestamp;
- the timeline is bound to one immutable Sportradar `sport_event.id`;
- the event is identified as the intended ATP/WTA singles match through retained provider context;
- the raw timeline response is retained byte-for-byte and SHA-256 hashed;
- the provider response generation/capture identity is retained;
- any timeline update metadata (`updated`, `updated_time`) is preserved rather than discarded.

Schedule-level `start_time` alone is **not** sufficient to establish the research chronology.

## Evidence-retention contract

For each admitted event, retain at minimum:

- exact raw Season Summaries page(s) used to enumerate the event;
- exact raw Sport Event Timeline payload;
- provider sport-event ID;
- season/competition/category IDs;
- provider `generated_at` when present;
- local retrieval timestamp;
- SHA-256 of every retained payload;
- parsed schedule `start_time`, `start_time_confirmed`, and `estimated` values when present;
- parsed `match_started.time`;
- timeline update markers when present;
- final event status / terminal reason used for research-population classification.

Derived rows must be reproducible from the retained raw evidence.

## Fail-closed exclusions

Do not assign an exact start timestamp when:

- no `match_started` event is present;
- multiple `match_started` entries conflict without a deterministic documented resolution;
- the timestamp is malformed or timezone-naive;
- the sport-event identity cannot be reconciled uniquely to the canonical historical match;
- the retained raw payload is missing or fails its recorded hash;
- ATP/WTA main-tour singles identity is unresolved;
- the event is a walkover/default or otherwise has no played-match chronology suitable for state updating.

Retain excluded events and their reason; do not silently drop them.

## Required empirical validation before admission

A real provider-backed audit must run before this source can be marked `HISTORICAL_EXACT_TIME_ADMITTED`.

For every fully accessible ATP and WTA main-tour singles season in the current provider window:

1. enumerate all season matches through paginated Season Summaries;
2. retain the complete raw page set and prove pagination completeness;
3. fetch and retain the Sport Event Timeline for every completed played singles event;
4. measure coverage of valid `match_started.time` separately by tour, season, competition level and provider coverage tier where identifiable;
5. quantify missing/conflicting/updated start events;
6. reconcile a sample against schedule `start_time` and verify that research chronology uses timeline `match_started.time`, not merely the schedule slot;
7. verify stable event identity and canonical-match crosswalk behavior;
8. record licensing/access constraints and the exact provider access level used;
9. fingerprint the retained source bundle and resulting exact-time population.

No minimum coverage threshold should be invented after observing the results. Any promotion threshold or required-use rule must be frozen before a protected comparison uses this panel.

## Relationship to the long-history panel

The intended architecture, if the provider audit succeeds, is:

- **Sackmann-style 2000–2025 panel:** long-history development with conservative prior-date chronology;
- **Sportradar recent exact-time panel:** shorter, separately fingerprinted research panel using retained timeline `match_started` timestamps;
- no silent merging of chronology semantics;
- no claim that a result on one panel automatically transfers to the other.

A recent exact-time panel can answer whether same-day ordering materially changes dynamic-state conclusions without rewriting the evidentiary status of the long-history source.

## Current decision

Sportradar Tennis v3 is **identified as the leading exact-time source candidate but is not yet admitted**.

Public documentation establishes the relevant fields and the rolling historical-window constraint. It does not establish this account's real accessible season set, actual ATP/WTA timeline coverage, or canonical crosswalk quality. Those require retained provider-backed evidence.

No historical result, model, protected-data state, prospective count, or production protocol changes from this document.
