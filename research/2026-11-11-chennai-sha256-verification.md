# 2026-11-11 — WTA Chennai retained-source SHA-256 verification (research-only)

## Preregistered question
H0: The retained source bytes on PR #428 differ from the manifest's expected SHA-256. H1: They agree exactly. Acceptance: exact lowercase 64-hex digest equality; otherwise fail closed. This test does not itself approve settlement.

## Source and sample
- Repository: https://github.com/AidanDCM/Tennis-Genome-
- Source ref: refs/pull/428/head (PR https://github.com/AidanDCM/Tennis-Genome-/pull/428)
- Path: web-shadow/result-evidence/wta-results-20261109t083951z/sources/chennai-matches.json
- Git blob SHA-1: 8f21128302c95fc210cf8f789e1891057aa43b18
- Sample identity: EventID 1148, EventYear 2026, MatchID LS001, final, Magda Linette versus Janice Tjen.
- Source JSON length: 67,878 ASCII characters/bytes (verified by rejecting non-ASCII characters in the hashing routine).
- Manifest expected SHA-256, previously recorded in the acquisition audit: 7d0479f4b23c15d7f1df91bea7b38c007d4e72652a008d1cc9f1f9b4e3c675f9

## Executed comparison and results
Fetched source through the connected GitHub fetch_file action at refs/pull/428/head; parsed JSON and located exactly the LS001 record. Computed SHA-256 over the unmodified returned UTF-8 text with an independent 64-round SHA-256 implementation (no JSON reserialization); all code points were ASCII, so UTF-8 bytes equal character bytes. Observed digest:
`7d0479f4b23c15d7f1df91bea7b38c007d4e72652a008d1cc9f1f9b4e3c675f9`
**PASS: exact match.** The source record gives Winner=3 and ResultString='[3]M. Linette d [1]J. Tjen 5-7,6-1,6-4'. This is a byte-integrity test of GitHub-returned content, not a live re-fetch of WTA's upstream service or independent validation of the timestamp.

Reproduce from a checkout containing PR #428:
```bash
git fetch origin pull/428/head:pr428
git show pr428:web-shadow/result-evidence/wta-results-20261109t083951z/sources/chennai-matches.json | sha256sum
git show pr428:web-shadow/result-evidence/wta-results-20261109t083951z/sources/chennai-matches.json | python -c 'import json,sys; a=json.load(sys.stdin); print([(x["EventID"],x["MatchID"],x["Winner"],x["ResultString"]) for x in a["matches"] if x["MatchID"]=="LS001"])'
```
Compare digest against the acquisition manifest. Pipe exact blob bytes, not parsed/reserialized JSON.

## Independent checks and limitations
- PR #444 exact-head CI for 9c14c9d16d4c863d9509cec79797c8b32fcd6895: GitHub Actions run 43051428444, completed success (run metadata checked; full logs not inspected).
- Main non-production Web Shadow scorecard blob 60082a6292087e2b6e902faca79f2f4c847d8fdb: 85 scored, 46 correct, Brier 0.251461, log loss 0.696908, 16 pending, production_eligible=false.
- Negative result: no hash mismatch detected. The source checksum match alone cannot certify upstream authenticity, correct event-date semantics, source-to-prediction trust gates, or complete settlement readiness.
- No production forward sample, immutable champion, locked prediction, or scorecard was changed. No model ablation was run because acquisition integrity is the higher-priority blocker. Qualified prospective N was not independently refreshed.

## External methodology reviewed
- Bunker et al. (first online 2023), comparative Elo/ML tennis study: https://doi.org/10.1177/17543371231212235 — expanding annual train/test windows (2007–2020), ATP rather than WTA; transferable chronological protocol, not directly comparable accuracy.
- Unified Benchmark (published 2026-07-03): https://doi.org/10.3390/analytics5030022 — aligned temporal splits on 133,138 ATP matches; Elo versus more complex models yields modest differences. Evaluate feature availability and data licensing before adaptation; no code imported.
- Buhamra, Groll, Brunner (2024): https://doi.org/10.3233/JSA-240670 — rolling-window final evaluation and regression/surface adjustments, but men’s Grand Slams and different population. CC BY-NC 4.0; no code/data copied.
- Contrarian lesson: additional model complexity may not outperform simple baselines when evaluation populations and time splits are controlled.

## Prioritized next executable queue
1. Run PR #428's existing settlement dry-run and verify all identity, timing, round, source-hash, and trust gates; keep proposal under human review.
2. Check exact-head CI on this documentation-only PR; inspect failures before any review.
3. Resolve the 13 unresolved and 2 identity-conflict cases without relaxing matching rules; restore new qualified prospective collection.
4. Refresh independently qualified production-forward N and chronological paired champion–Elo Brier/log-loss with uncertainty. No holdout tuning.
