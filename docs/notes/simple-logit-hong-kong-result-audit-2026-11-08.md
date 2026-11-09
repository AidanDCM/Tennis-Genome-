# Hong Kong simple-logit paper result audit

The frozen Hong Kong final challenger records remain unchanged:
`research/forward/simple_logit_001/hong-kong-2026-f-ls001-base.json` and
`research/forward/simple_logit_001/hong-kong-2026-f-ls001-rank.json`.
[PR #420](https://github.com/AidanDCM/Tennis-Genome-/pull/420) merged at
`2026-11-07T21:21:38Z`. Its merge commit is
`83b2eb2a7216139826180f5ccba26389ac37b543`.

The [official WTA result source](https://api.wtatennis.com/tennis/tournaments/1074/2026/matches)
for match `LS001` identifies Claire Liu and Alexandra Eala, terminal state `F`,
winner code `2` for Liu, and result `6-3,6-0`. The retained source is
`web-shadow/result-evidence/wta-results-20261108t104527z/sources/hong-kong-matches.json`
with file SHA-256
`8355ca3b614f82e6b8fe1248af00a386d553ad333d3158b464f593982f4a45fc`.
The bound Web Shadow result and settlement were merged and scored in
[PR #425](https://github.com/AidanDCM/Tennis-Genome-/pull/425).

The official feed's `MatchTimeStamp` is
`2026-11-08T07:48:47.867Z`, well after the challenger GitHub merge. However,
the repository's source audit does **not** certify this field as actual start,
and it precedes the earlier advertised 08:00 UTC start. The exact-start
condition for challenger settlement is therefore **unverified**. The BASE and
RANK records remain **pending and unscored as a challenger cohort**. Neither
may enter formal FULL-STACK-FORWARD evidence.

For inspection only, the following are the deterministic scores *conditional*
on Liu being the outcome and on a future chronology check passing. Player A is
Liu, so binary Brier is `(1 - p_Liu)^2`, log loss is `-ln(p_Liu)`, and the
calibration residual is `1 - p_Liu`.

| Paper forecast | p(Liu) | Brier | Log loss | Residual |
| --- | ---: | ---: | ---: | ---: |
| Existing Web Shadow | 0.391436 | 0.370350 | 0.937934 | +0.608564 |
| Simple-logit BASE | 0.345127 | 0.428858 | 1.063842 | +0.654873 |
| Simple-logit RANK | 0.284078 | 0.512544 | 1.258505 | +0.715922 |

Relative to Web Shadow on this same match, BASE would have +0.058508 Brier
and +0.125908 log loss; RANK would have +0.142193 Brier and +0.320571 log
loss. Lower is better. All three favored Eala and missed. This single match
does not select a model or warrant any adjustment.

Next: obtain a separately qualified actual-start event, such as a retained
Sportradar timeline `match_started.time` with verified match identity. Only
then may the frozen challenger records receive a final paper settlement.
