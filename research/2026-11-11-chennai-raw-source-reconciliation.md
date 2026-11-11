# Iteration 47 — Chennai official-source row reconciliation (2026-11-11)

## Prespecified hypothesis and scope
H1: The retained WTA provider match row for Chennai 2026 final has the same event, players, round, winner and score as PR #428's proposed non-production result. H0: any mismatch; reject proposed result. No settlement, model change or promotion authorized. This is a source-to-derived-record audit, not a live re-fetch or SHA-256 recomputation.

## Sources / exact identifiers
- Main baseline: 8af76720a6291b166263fa1cd8191504f84ed6b6 (recheck before review).
- PR #428 head: e676c961d674ffd32d254bb96f738ae7242e211f, https://github.com/AidanDCM/Tennis-Genome-/pull/428
- Retained raw file: web-shadow/result-evidence/wta-results-20261109t083951z/sources/chennai-matches.json (Git blob 8f21128302c95fc210cf8f789e1891057aa43b18).
- Acquisition manifest reports raw bytes SHA-256: 7d0479f4b23c15d7f1df91bea7b38c007d4e72652a008d1cc9f1f9b4e3c675f9; **not independently recomputed**.
- Proposed result: web-shadow/results/2026-11-09-chennai-2026-f-ls001-janice-tjen-magda-linette-42775ef387.json (blob 8693ebd69e6acb4158721251809fedb046abba18).
- Frozen prediction path: web-shadow/slates/2026-11-07-run-42418376306/predictions/chennai-2026-f-ls001-janice-tjen-magda-linette.json; claimed SHA-256 42775ef387a985d5c68af2d4d349c7ce45e21d9c5304dccfd1886a381a44b929.

## Executed checks and results
Fetched raw WTA JSON from PR head through connected GitHub fetch_file, parsed JSON and filtered by MatchID == LS001. Exactly one row found. Row: EventID 1148; EventYear 2026; MatchID LS001; RoundID F; PlayerNameFirstA/LastA Janice/Tjen; PlayerNameFirstB/LastB Magda/Linette; PlayerIDA 328818; PlayerIDB 315130; MatchState F; Winner 3; ResultString '[3]M. Linette d [1]J. Tjen 5-7,6-1,6-4'; MatchTimeStamp 2026-11-09T05:16:55.047+00:00; LastUpdated 2026-11-09T08:30:37.727+00:00.
Compared against proposed result: web:wta:1148:2026:LS001, winner Magda Linette, score 5-7 6-1 6-4, COMPLETED, observed 2026-11-09T08:39:51+00:00. Event, player pair, winner and score agree. Result observation occurs 9m13.273s after raw LastUpdated.
Independent published outcome cross-check: Reuters November 9, 2026 (https://www.reuters.com/sports/tennis/wta-roundup-coco-gauff-takes-down-jessica-pegula-wta-finals--flm-2026-11-09/) and Tennis.com match page (https://www.tennis.com/tournaments/chennai-open/matches/j-tjen-vs-m-linette-2026-11-09) both report Linette defeating Tjen 5-7, 6-1, 6-4 in the Chennai final. These do not authenticate provider byte hashes.
PR #443 exact-head CI #43041003718: completed success, Ruff success, Pytest success; job 130592443718 (https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43041003718).
Main WTA Web Shadow (non-production, production_eligible=false): 88 settled, 85 scored, 46 correct, Brier 0.2514610585, log loss 0.6969082733, 16 pending. No new canonical settlement; qualified production-forward N not refreshed.

## Negative findings and limits
No live official API byte-for-byte retrieval, no independent recomputation of retained SHA-256, no verification of all raw source files, no current qualified forward aggregate, and no direct application of settlement publisher. The event's scheduled final was delayed to November 9 (Reuters and contemporaneous reports); preserve the frozen prediction's original time and never rewrite it. Existing two Hong Kong MatchID/player conflicts and 13 unresolved predictions remain excluded. PR #428 remains open. This check must not be construed as settlement approval.

## Reproducibility
At PR #428 head, load JSON file above; traverse its match records and assert exactly one MatchID == 'LS001'; compare EventID, EventYear, player names, RoundID, Winner and ScoreString against proposed result. Independently validate SHA-256 of exact raw file bytes against acquisition manifest before approval (do not hash reserialized JSON). Run repository's existing dry-run settlement and pre-start gates; require human review.

## Research / evaluation design
Ferro (2017), https://doi.org/10.1002/qj.3115 (published July 7, 2017): proper scores may rank observation quality rather than underlying forecast quality when outcomes contain errors. Different domain (weather); mathematical method relevant but correction assumptions unverified here. Reuters and Tennis.com are independent outcome corroboration, not alternative raw-source authorities. No external code copied, no license dependency introduced.

## Prioritized executable queue
1. Independently compute SHA-256 of exact retained chennai-matches.json bytes; reconcile manifest and source row, and inspect raw provider completion semantics.
2. Run strict dry-run settlement of PR #428 on isolated checkout, verify immutable prediction SHA and timestamps; require human review before any merge.
3. Resolve blocked acquisition gate without bypassing identity conflicts; verify workflow freshness and qualified forward aggregate.
4. On new locked prospective paired observations, evaluate unchanged champion against predeclared simple Elo challenger using Brier/log loss, accuracy Wilson interval, and drift by surface/time. Do not use the historical 85 as a final holdout.
