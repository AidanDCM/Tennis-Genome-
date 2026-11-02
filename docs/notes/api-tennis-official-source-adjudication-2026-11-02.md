# API-Tennis versus official WTA point totals: first source adjudication

The retained May 3–June 2 API-Tennis capture was compared against three official
WTA match pages after the matches. The local capture's receipt, manifest, audit,
and raw hashes were verified by `verify_capture` before comparison. This is a
small, deliberately selected engineering sample, **not** an error-rate estimate,
historical pre-match evidence, or approval of API-Tennis as a production source.

| Match (provider event) | Official service points won/played, first/second | API-Tennis | Internal gate | Exact official agreement |
| --- | --- | --- | --- | --- |
| [Gauff–Andreeva, Rome](https://www.wtatennis.com/tournaments/709/rome/2026/scores/LS005) (`12126507`) | 51/93, 53/104 | 40/69, 36/66 | Fails | No |
| [Tjen–Osorio, Rabat](https://www.wtatennis.com/tournaments/1005/rabat/2026/scores/LS008) (`12129073`) | 49/96, 49/85 | 41/78, 61/109 | Fails | No |
| [Kalinina–Bondar, Rabat](https://www.wtatennis.com/tournaments/1005/rabat/2026/scores/LS005) (`12129626`) | 43/80, 36/76 | 43/80, 36/76 | Passes | Yes |

The official WTA pages identify the same players, tournaments, dates, scores,
and finished matches. API-Tennis's two disagreements concern exact point counts,
not merely percentages or rounding. Their cause is **not established**. A stale
partial statistic state, feed assembly, or another provider issue is possible;
none has been proven. The existing internal point-consistency gate excludes
both discrepant records from player-stat updates. The agreeing record shows
the gate can allow exact official agreement; it does not certify all rows that
pass it. Outcome-only use of a rejected statistics row remains a separate
source-admission question.

The curated reference is
`research/source_adjudication/wta_official_2026_cases.json`. Reproduce offline
with no provider requests:

```text
python -m scripts.adjudicate_api_tennis_official_stats \
  --capture-dir <retained-May3-June2-capture> \
  --reference research/source_adjudication/wta_official_2026_cases.json \
  --output <new-local-output.json>
```

The output binds the compared provider counts to the verified capture receipt
and the reference-file SHA-256. It refuses duplicate event IDs, mismatched
player IDs, duplicate service statistics, and overwriting an existing report.
Official values are a manually curated research reference linked to the WTA
pages; the tool does not independently authenticate those pages at run time.
Raw provider files and generated comparison reports remain local pending rights
review. The frozen predictor and existing forecasts were not changed.

**Admission decision:** retain API-Tennis statistics as research evidence. Do
not advance its point-count rows wholesale into the current production state.
Next sample randomly selected internally consistent rows against independent
official records, quantify agreement by tour/tournament/data availability,
then address canonical player identity, duration, surface, and actual-start
evidence before building a production continuation.
