# 2026 point-stat source compatibility gate

The pinned research archive and the retained Sportradar census overlap on eight
ATP tournaments before the archive's 2026-05-25 endpoint. Run the read-only
audit with `scripts/audit_sportradar_stat_overlap.py`, the map in
`sportradar-2026-overlap-season-map.json`, the retained census `seasons/`
directory, and the pinned `atp_matches_2026.csv`. The output hashes each input
page and response header plus the canonical CSV. It never fetches provider data
or approves a mixed-source player-state history.

The retained sample has 323 player-pair joins. After excluding 12 abnormal or
nonterminal matches, there are 622 player rows with comparable statistics:

| Field | Exact agreement |
| --- | ---: |
| Aces | 613 / 622 |
| Double faults | 620 / 622 |
| Total service points | 595 / 622 |
| First serves in | 380 / 622 |
| First-serve points won | 444 / 622 |
| Second-serve points won | 448 / 622 |

These differences are not a benign naming or A/B-orientation issue: player
pairs and winners are checked separately, and ace/double-fault agreement is
near complete. They may reflect vendor definitions or later revisions; this
audit does not identify the cause. Do not silently append Sportradar point
statistics to the pinned archive and call the resulting state equivalent to
the frozen training data. The next experiment must quantify downstream feature
and probability shifts on overlapping historical matches before a source
transition can be admitted. Result-only history and sparse-stat handling are
separate options to test; neither is approved here.

The local full report is
`outputs/sportradar-vs-pinned-2026-overlap-audit-v4.json` in the task
workspace. This is retrospective research evidence, not a forward score.
