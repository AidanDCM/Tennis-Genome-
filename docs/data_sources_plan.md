# Data Sources Plan

This document defines what evidence the engine needs before locking in specific providers. Provider names, licensing, and coverage must be proof-checked before implementation.

## Source priorities

Prefer sources that are:
- legally usable for the intended research/deployment context;
- reproducible;
- timestamped;
- historically deep;
- stable in identifiers;
- explicit about match status and data corrections;
- rich enough to reconstruct information available before T0.

## Required source families

### 1. Match results
Need:
- canonical players
- event
- date/time where available
- round
- surface
- score
- winner/loser
- completion/retirement/walkover/default status

### 2. Rankings
Need historical publication snapshots:
- ranking
- ranking points
- date available

### 3. Match statistics
Prefer:
- aces
- double faults
- first serves in
- first/second serve points won
- service points
- return points
- break points
- total points where available

Point-level histories are especially valuable for opponent-adjusted serve/return and mechanistic simulation research.

### 4. Tournament metadata
Need:
- location
- level
- surface
- indoor/outdoor where available
- draw/round format
- best-of rules
- date ranges

Later:
- altitude
- court identity/pace proxies
- balls/equipment

### 5. Scheduling/workload
Derived primarily from match chronology, but accurate start/finish timestamps improve:
- rest hours
- turnaround
- local time
- double-day effects

### 6. Player attributes
Need stable/source-tracked:
- DOB
- handedness
- height
- country
- turned-pro year where available

Later:
- reach
- backhand type
- style/tracking metrics

### 7. Health/injury/context
Deferred until a trustworthy evidence pipeline exists.

Requirements:
- source URL/reference
- first-known timestamp
- event type
- certainty
- severity
- affected body part/context
- source reliability
- explicit distinction between pre-match evidence and post-hoc explanation

### 8. Market odds
Completely separate from independent tennis features.

Need:
- book/source
- market type
- selections
- odds
- capture timestamp
- open/current/close status if known

Later:
- consensus
- line movement
- exchange/liquidity

## Source evaluation scorecard

For every candidate source record:

| Criterion | Score/notes |
|---|---|
| historical depth | |
| ATP coverage | |
| WTA coverage | |
| point/stat detail | |
| timestamps | |
| stable IDs | |
| corrections/versioning | |
| reproducibility | |
| licensing | |
| rate/access limits | |
| cost | |
| permitted storage | |
| permitted redistribution | |

## Multi-source reconciliation

Do not silently choose whichever source agrees with expectations.

Pipeline should:
1. map source IDs to canonical IDs;
2. detect exact/near duplicate matches;
3. surface conflicting dates/scores/statuses;
4. define precedence rules based on source reliability;
5. preserve conflict flags and source records;
6. never use post-hoc corrections in a historical T0 simulation unless the corrected fact was knowable at that historical time.

## Data acquisition stages

### Stage A
One reproducible core match-results/rankings dataset for baseline Elo.

### Stage B
Match stats sufficient for serve/return and form experiments.

### Stage C
Better timestamps/workload/tournament metadata.

### Stage D
Richer environment/injury/context feeds.

### Stage E
Market history for paper betting evaluation.

This staged approach prevents data acquisition complexity from delaying the first falsifiable models.

## Legal/reproducibility note

Do not build a production dependency around scraped data until terms, rate limits, storage permissions, and reproducibility are reviewed. Research source convenience is not the same as production licensing.
