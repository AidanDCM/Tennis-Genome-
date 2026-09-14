# Historical Ranking Availability Evidence 001

Status: **EVIDENCE REVIEWED — EXACT T0 AVAILABILITY NOT ESTABLISHED**

Audit date: 2026-09-14

## Question

Can target-match ranking and ranking-points fields from the pinned Sackmann-style historical
source be promoted from `RESEARCH_ONLY_UNVERIFIED` to canonical v2 pre-match inputs?

## Source evidence

### Sackmann ATP/WTA semantics

The upstream dataset documentation states that match-row ranking data, ranking points and
age are **as of `tourney_date`**. It also states that `tourney_date` is almost always the
Monday at or near the beginning of the event.

Relevant upstream repositories:

- https://github.com/JeffSackmann/tennis_atp
- https://github.com/JeffSackmann/tennis_wta

This establishes a weekly/event-date semantic. It does **not** establish the exact time at
which a given historical ranking snapshot became public, whether a stored row was later
revised, or whether the row is a contemporaneous snapshot rather than a retrospective
reconstruction.

### ATP publication convention

ATP's own historical news material describes the latest ATP Rankings as being **published
on Monday**. The ATP ranking interface also organizes official rankings by ranking week/date.

Relevant ATP references:

- https://www.atptour.com/en/news/federer-haase-no-1-return-rotterdam-2018-friday
- https://www.atptour.com/en/rankings/singles

This supports the weekly Monday convention. It still does not provide an exact historical
publication timestamp for every ranking snapshot represented in the research archive.

### WTA evidence boundary

The WTA historical dataset uses the same weekly ranking-date/result-row convention, but the
current audit did not locate a primary source that supplies a complete historical
publication timestamp/revision ledger for every ranking snapshot consumed by the pinned
research source.

Absence of that stronger evidence is material because the v2 availability contract asks a
narrower question than whether a weekly ranking is plausible or normally known before a
match: it asks whether exact T0 legality is reproducible from retained evidence.

## Decision

`target_ranking`, `target_ranking_points`, and any feature whose legality depends on those
retrospective row values remain:

`RESEARCH_ONLY_UNVERIFIED`

They are **not** promoted to `VERIFIED_PREMATCH`.

No synthetic intraday timestamp may be attached to these fields. The Monday/event-date
convention is useful descriptive provenance, but it is not a substitute for a retained
historical publication timestamp and revision contract.

## What would be sufficient to revisit this decision

At least one source path would need to establish the relevant historical snapshot identity
and availability strongly enough to reproduce T0 use, for example:

1. an authoritative or licensed historical ranking feed with dated/versioned snapshots and
   documented publication semantics;
2. independently archived official ranking snapshots with trustworthy capture timestamps
   and stable player/ranking identities; or
3. another retained source whose revision and publication behavior is documented strongly
   enough to distinguish contemporaneous availability from later reconstruction.

A modern API that merely reconstructs rankings for a historical Monday is not sufficient by
itself unless it also proves the historical publication/version semantics of the returned
snapshot.

## Scientific consequence

The current conservative v2 path remains centered on prior-date state derived from earlier
completed matches. This audit adds no feature, changes no coefficient, opens no protected or
prospective outcome, and does not alter TGE-Independent-v1, FULL-STACK-FORWARD-001, or
PATTERN-CONFIRM-001.
