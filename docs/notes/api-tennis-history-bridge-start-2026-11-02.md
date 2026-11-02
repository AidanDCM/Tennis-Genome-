# API-Tennis current-state bridge: first admission gates

The frozen engine already has chronological feature builders. The missing
integration is a reviewed canonical history stream after the pinned 2026
archive, not another probability formula. This change starts that integration
without admitting the retained provider data wholesale.

`scripts/propose_api_tennis_player_crosswalk.py` compares retained API-Tennis
player profiles against the pinned Sackmann player registry using **both
normalized full name and exact birthdate**. It verifies each profile response
against its raw hash, manifest and GitHub receipt. The November 3 fixture
context report is also hashed into the output. Matches with fixture/draw ID
conflicts or a status other than `1` receive no proposed player mapping.

The retained November 3 slate produced:

| Status | Matches |
| --- | ---: |
| Exact two-player registry candidate | 29 |
| Fixture/draw player-ID conflict | 2 |
| Non-scheduled or canceled status | 3 |
| No exact registry match | 2 |

The two unmatched profile names are `Martin Etcheverry Tomas` (source order
differs from the pinned registry) and `Sahaja Yamalapalli` (no exact registry
name/birthdate pair). Neither is silently rewritten or attached to another
person. The local candidate file is
`outputs/api-tennis-crosswalk-proposals-2026-11-03.json`; it is research-only
and remains outside the public repository with the raw provider files.

`api_tennis_history_bridge.build_candidate_historical_match` accepts only an
explicit reviewed player-ID map and surface, a point-consistent enrichment
record, source observation before the target cutoff, and a historical event
date strictly before the target's UTC date. It orients outcome and every stat
field to canonical A/B IDs. Missing rankings, demographics and duration remain
unknown rather than invented. It retains raw-match and source-manifest hashes
in a candidate evidence object. The conversion is not wired into the frozen
production calculator and makes **no source-approval or forward-evidence claim**.

The next implementation gate is a reviewed player and tournament crosswalk
across the retained history, duplicate reconciliation with the pinned 2026
archive, and a source-quality policy that preserves outcome-only rows while
quarantining contradictory point statistics. Only then can the existing
chronological feature builders be replayed for a current full-stack input.
