# API-Tennis trial backfill: retained evidence and admission status

Captured on 2026-10-30 with the trial credential in the GitHub Actions secret
`API_TENNIS_KEY`. The capture used two filtered `get_fixtures` requests per
window, one ATP singles and one WTA singles. No secret value is retained in the
artifacts. The raw provider responses, audits, SHA-256 manifests, and GitHub run
receipts are in the linked Actions artifacts; identical local copies were
downloaded under ignored `outputs/api-tennis-backfill-*` directories. The
separately retained August 17–September 16 capture is run `35306853901`.

| UTC fixture dates | Run | Fixtures | Finished |
| --- | ---: | ---: | ---: |
| May 3–June 2, overlap sample | [41118342871](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41118342871) | 910 | 874 |
| June 3–July 3 | [41117636190](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41117636190) | 997 | 933 |
| July 4–August 3 | [41117811328](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41117811328) | 695 | 649 |
| August 4–16 | [41117946047](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41117946047) | 354 | 334 |
| August 17–September 16, previously retained | [35306853901](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/35306853901) | 728 | 690 |
| September 17–October 17 | [41118077334](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41118077334) | 843 | 744 |
| October 18–29 | [41118204455](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41118204455) | 342 | 308 |

The six June 3–October 29 windows contain **3,959 unique event IDs** and
**3,658** `Finished` rows (2,014 ATP and 1,945 WTA fixtures). Every calendar
date in that period has at least one returned fixture, but this does not prove
complete tour coverage against an independent official schedule. **3,611 of
3,658** finished rows have both players' exact first/second serve and return
point counts and internally agree on service/return totals. The 47 exceptions
include 38 ATP Davis Cup World Group II rows and nine other matches. All six
raw-response hash pairs match their manifests; IDs are unique across windows.

The overlap window adds 910 fixtures and 874 finished rows; 873 finished rows
have exact point counts. It supplies a direct source-comparison sample, not new
prospective forecasts.

## Source-comparison warning

An offline diagnostic joined overlap records to the locally retained pinned
2026 CSV by tour, a unique normalized player pair, tournament name (including
explicit Rome/French Open aliases), winner, and plausible tournament-date
offset. This is a research join, not a production identity mapping. It yielded
232 ATP and 235 WTA unique matches. Both sources had all eight core serve
counts on 139 ATP and 143 WTA matches. All eight agreed on 120 ATP and 113 WTA
matches; **49 of 282** comparable matches had at least one disagreement.
Service-point totals disagreed in 6/139 ATP winner lines, 10/139 ATP loser
lines, and 16/143 on each WTA side. Some differences exceed 20 points despite
matching players, event, winner, and set result. The raw diagnostic is retained
locally as `outputs/api-tennis-overlap-vs-pinned-2026-10-30.json`.

The fixture payload does not contain a separate verified actual-start field,
surface, match duration, player seed, or historical ranking. Its `event_time`
is scheduled/display time. Historical records captured now cannot be turned
into untouched pre-match predictions. ATP/WTA `get_fixtures` also includes
Davis Cup rows under the ATP singles event type, so event type alone does not
enforce the frozen model's population.

**Admission decision:** retain API-Tennis as research source evidence. Do not
silently substitute it into production player state or claim FULL-STACK-FORWARD
eligibility. Next, adjudicate the mismatched overlap rows against official
match statistics, measure feature and probability changes from any proposed
source substitution, resolve surface and player identity, and establish a
verified start-time source for prospective use. October 30 should be captured
separately after its UTC date finishes. Raw provider responses remain outside
the public repository pending license review; the Actions artifacts expire on
2027-01-28, so the local copies need durable retention before then.

## Current standings snapshot

A separate [2026-10-30 standings run](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41119915519)
used two additional calls, one per tour. Its raw files and receipt are retained
locally under ignored `outputs/api-tennis-trial-standings-2026-10-30`. The
response contained 2,418 unique ATP player keys and 1,658 unique WTA keys;
every returned place and points value was numeric. The receipt and raw hashes
were independently rechecked after download. Among October 1–29 finished
fixtures, both players matched current standings keys in 354/356 ATP and
294/309 WTA matches. These are *current snapshot* ranks and points, not
historical ranks or a provider-certified rank-effective date. They cannot be
retroactively inserted into prior pre-match states.

## Bounded tournament metadata probes

Two further one-call probes used tournament key `3076`, Tokyo WTA 2026:
[player profiles](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41121283915)
and [draw](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41121400377).
Both raw responses and GitHub receipts were downloaded and hash-verified.
`get_players` returned 47 unique player keys, each with a full name, birthdate,
and season-stat list; these keys covered all 47 distinct players in the 42
retained Tokyo fixtures. `get_draw` returned `source=draw_feed`, a provider-labeled
bracket with 27 nonempty seed/entry fields among 56 seed fields, and the
tournament surface `Hard (Indoor)`. The provider's player-profile fields did
not include height or handedness. Neither response supplied match duration or
verified actual start. These results show that one profile call and one draw
call per tournament can fill identity, birthdate, surface, indoor context, and
seed gaps, subject to source identity and T0 checks. Season aggregates captured
after a match cannot be used as that match's pre-match state. The probes remain
research-only; their data is not admitted into the frozen production path.
