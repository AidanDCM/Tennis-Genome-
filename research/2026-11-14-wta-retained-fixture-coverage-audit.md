# WTA retained intake fixture coverage — 2026-11-14 UTC

Evidence tier: read-only operational diagnostic, non-production. No settlements or predictions modified.

## Prespecified test
Hypothesis: the four retained official WTA match feeds contain at least one unfinished fixture whose timestamp falls in the November 14–15 eligible 8–48h lead window. Null comparator: zero qualifying rows. Success requires at least one not-final row in the window; failure is zero, with independent tournament date checks. `MatchTimeStamp` is a provider event timestamp, **not independently verified scheduled start**.

## Reproducible input
- Main SHA at source acquisition: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`
- [GitHub Actions run 43495625075](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43495625075); retained [artifact 14071382847](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43495625075/artifacts/14071382847), ZIP digest `sha256:01724efcd3c2bf7ffdc8742bb1131f9bb42eb6528ddb137b250495e45583c6c5`.
- Manifest observed_at `2026-11-13T19:48:25+00:00`; window `2026-11-14T03:48:25+00:00` to `2026-11-15T19:48:25+00:00`.
- Source config blob `0431001e2cdf48a9742fba931344ac77a975562d`.

## Executed calculation
Downloaded and opened artifact ZIP, inspected manifest, raw match JSON and tournament JSON. Verified all four raw match file SHA256 values against manifest. Reproduce after downloading ZIP:
```python
import zipfile,json,hashlib,datetime,collections
z=zipfile.ZipFile("github-actions-artifact-14071382847.zip")
m=json.loads(z.read("acquisition-manifest.json"))
t=datetime.datetime.fromisoformat(m["observed_at"])
lo,hi=t+datetime.timedelta(hours=8),t+datetime.timedelta(hours=48)
for s in m["source_records"]:
 b=z.read(s["matches_filename"])
 assert hashlib.sha256(b).hexdigest()==s["matches_sha256"]
 rows=json.loads(b)["matches"]
 stamps=[datetime.datetime.fromisoformat(x["MatchTimeStamp"]) for x in rows]
 print(s["slug"],len(rows),dict(collections.Counter(x["MatchState"] for x in rows)),min(stamps),max(stamps),sum(lo<=x<=hi for x in stamps))
```
Results:
| Event | Rows | Final state F | Timestamp max (UTC) | Timestamp within window |
|---|---:|---:|---|---:|
| Guangzhou | 64 | 64 | 2026-11-01 08:20:23.973 | 0 |
| Tokyo | 60 | 60 | 2026-11-01 05:57:22.330 | 0 |
| Hong Kong | 61 | 61 | 2026-11-08 07:48:47.867 | 0 |
| Chennai | 58 | 58 | 2026-11-09 05:16:55.047 | 0 |
| **Total** | **243** | **243** | | **0** |

Tournament metadata start/end: Guangzhou/Tokyo Oct 26–Nov 1; Hong Kong/Chennai Nov 2–8. All four events ended before observed_at. This establishes **event-universe exhaustion** for this snapshot, not a bug in the 8–48h filter. No scheduled start fields independently established; provider event timestamps should not be used as pre-start receipts.

## Negative and trust boundaries
Hypothesis rejected (0/243 timestamp-in-window; 243/243 final). Zero-selection is expected for these four finished events. Do not widen lead windows, reinterpret MatchTimeStamp as scheduled start, backfill predictions, or auto-settle 15 unresolved records. This is not a model ablation or qualified forward performance gain.

## Literature
- [Choe & Ramdas (2023), Comparing Sequential Forecasters](https://doi.org/10.1287/opre.2021.0792): anytime-valid paired forecast comparisons for bounded scores; useful once qualified prospective cohorts accrue. Not a tennis performance claim.
- [Ferro (2017), observation error](https://doi.org/10.1002/qj.3115): imperfect labels can mislead proper-score evaluation; corroborate identity and outcomes before scoring.
- [Proper Scoring Rules for Estimation and Forecast Evaluation (2025)](https://doi.org/10.1146/annurev-statistics-042424-050626): proper scoring and forecast comparison; no dataset or code license established from abstract.

## Next executable queue
1. Use retained 2026 tournament index pages to identify **future** WTA events with authoritative IDs and schedules; review a forward-only configuration PR, preserving identity/pre-start gates.
2. Independently inspect result acquisition artifact 14060013326 for 13 unresolved and two conflicts; no automatic settlement.
3. Reconcile main's immutable champion and qualified forward receipts, then preregister one paired chronological challenger using Brier/log loss and sequential uncertainty.
4. Review open PR backlog; avoid merging research-only branches without review.
