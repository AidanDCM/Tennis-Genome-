# Historical Target Age Availability Evidence 001

Status: **REVIEWED — reference date established, canonical historical T0 availability not established**

Audit date: 2026-09-14

## Question

Can `winner_age` / `loser_age` in the pinned Sackmann-style historical match rows be treated as canonical point-in-time target features?

## Evidence reviewed

Primary upstream references:

- https://github.com/JeffSackmann/tennis_atp
- https://github.com/JeffSackmann/tennis_wta

The upstream documentation explicitly says that **age is as of `tourney_date`**, and that `tourney_date` is almost always the Monday at or near the beginning of the event.

The same source family also maintains master player files containing date of birth and explicitly invites contributions that fill in or correct missing biographical data, including date of birth.

## What is established

- The semantic reference date for the match-row age field is documented: `tourney_date`.
- Age is not a post-match outcome and does not depend on the target match result.
- Once a correct DOB and reference date are known, age is deterministic.

## What is not established

The current historical source contract does not provide a version-effective history for the DOB values underlying the retained ages. It therefore does not establish, for every historical target match:

- when the DOB value first became available to the dataset;
- whether the DOB was missing at the historical T0 and filled in later;
- whether the DOB was corrected after the historical target match;
- whether an old match-row age was immutable at the time or regenerated/maintained from later-corrected biography.

This is a point-in-time provenance problem, not an argument that age itself is unknowable. A retrospectively corrected birth date can produce a scientifically accurate age while still failing a strict historical-information-set test.

There is also a smaller chronology issue: the documented age is as of the tournament date, not necessarily exact match start. That is acceptable as a clearly defined feature reference date, but it should not be misrepresented as exact match-time age.

## Decision

When sourced only from the pinned retrospective Sackmann-style rows, target age remains:

- `TimestampSemantics.EVENT_DATE_ONLY`;
- `RevisionSemantics.LATEST_ONLY_UNKNOWN_HISTORY`;
- `T0Policy.RESEARCH_ONLY_UNVERIFIED`;
- unavailable for canonical protected-v2 target use.

No synthetic DOB publication timestamp is introduced and no feature is promoted.

A future canonical age feature can be admitted if its DOB source is either:

1. versioned with trustworthy effective/publication timestamps, or
2. independently retained before the target match and bound to the historical T0 evidence set.

## Scientific consequence

This closes the current target-row availability review without weakening the standard. Ranking, event context, player-reference fields, and age each remain blocked for different provenance reasons unless stronger point-in-time evidence is supplied.

This review does not alter TGE-Independent-v1, the frozen historical candidate search, `FULL-STACK-FORWARD-001`, `PATTERN-CONFIRM-001`, or any prospective count.
