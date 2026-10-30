# API-Tennis trial backfill, October 2026

The purpose of this capture is to fill the **source-data gap** after the pinned
research history ends on 2026-06-02. It does not authorize a change to the frozen
predictor or promote API-Tennis data into production player state. The existing
2026-08-17 through 2026-09-16 ATP/WTA filtered capture is retained in GitHub
Actions run `35306853901` (artifact `10531692054`).

## Requested historical windows

| First UTC date | Last UTC date | ATP/WTA requests |
| --- | --- | ---: |
| 2026-06-03 | 2026-07-03 | 2 |
| 2026-07-04 | 2026-08-03 | 2 |
| 2026-08-04 | 2026-08-16 | 2 |
| 2026-09-17 | 2026-10-17 | 2 |
| 2026-10-18 | 2026-10-29 | 2 |

Each window uses the already tested filtered `get_fixtures` capture, with event
type keys 265 (ATP singles) and 266 (WTA singles), UTC timezone, and at most 31
calendar days. The trial workflow reads the GitHub secret `API_TENNIS_KEY` into
the existing process variable `API_TENNIS_API`. It retains exact raw responses,
their hashes, an audit, and a GitHub run receipt. A duplicate artifact for the
same window blocks another capture. Ten requests cover all currently missing
**completed historical dates** through October 29. A separate daily inventory
captures October 30 when the day is complete.

## Admission checks after capture

1. Account for every requested date and both ATP/WTA response files. A returned
   empty date is not evidence that no tour match occurred until independently
   checked against an official schedule.
2. Quantify match identity, winner, round, surface, status, and draw coverage
   against the retained official and pinned records.
3. Quantify exact serve/return point-count availability, missingness, duration,
   seeds, and player identity. Do not infer a missing count from a percentage.
4. On historical overlap, compare source statistics field by field and measure
   downstream feature and probability shifts. Previous Sportradar overlap
   showed substantial disagreement in first-serve counts despite matching
   winners, so provider substitution requires this gate.
5. Treat API-Tennis `event_time` as a scheduled/display time, not a verified
   actual match start. Historical snapshots captured now are retrospective
   source research, never untouched forward predictions.
6. Keep provider odds and any provider model predictions out of independent
   player state.

GitHub Actions artifacts expire; download and preserve the retained evidence
outside the artifact store before expiry. Raw provider responses must not be
committed to this public repository without an explicit data-license review.
