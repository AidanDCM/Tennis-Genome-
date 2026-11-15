# Iteration 33 — retained WTA provider pair reconciliation (2026-11-10)

## Prespecified audit
Hypothesis: some of the 13 unresolved legacy-ID predictions have exactly one pair-consistent match in retained WTA tournament rows despite lacking numeric provider MatchIDs. Baseline: 0/13 resolved by the existing exact-ID intake. Population: all 13 IDs from iteration 32 (9 Seoul, 4 Singapore). Success: at least one unique main-draw singles participant-pair match; failure: zero. **Pair matching is discovery only, not a settlement permission.** Round, pre-start timestamp, original prediction names and source integrity still require independent validation.

## Source and executable comparison
Main SHA `8af76720a6291b166263fa1cd8191504f84ed6b6` at audit. Result proposal PR #428 head `e676c961d674ffd32d254bb96f738ae7242e211f`. Retained raw provider blobs:
- `web-shadow/result-evidence/wta-results-20261109t083951z/sources/seoul-matches.json` blob `bcc4cc0dc4216d749c4cea78cb915a68a0fb4063`; manifest provider SHA-256 `57ae18a34df4ae9a8f542694dc3c9dcc3bd736c259022f3c3bb4b71102615ccc`; 58 raw rows, 31 main-draw singles rows.
- `web-shadow/result-evidence/wta-results-20261109t083951z/sources/singapore-matches.json` blob `2d5c6a7248175c2a4be68c33fb32be59fc5c95d1`; manifest provider SHA-256 `0b0ffb70b17a299c0691d23be692206976771b223b794d9d5e51c92f16e1d234`; 53 raw rows, 26 main-draw singles rows.

Executed JavaScript over actual JSON returned by GitHub fetch_file, filtering `DrawMatchType === "S" && DrawLevelType !== "Q"` and requiring exact unordered lowercase surnames against legacy IDs. **12/13 have exactly one pair match; 1/13 has none.** No match had more than one pair candidate. 9/9 Seoul; 3/4 Singapore. All 12 matched provider rows have `MatchState="F"` (finished state; not permission to score). Counts were inspected from execution output.

| Legacy ID suffix | Provider ID | Provider round ID | Provider match timestamp (UTC) |
|---|---|---|---|
| seoul:r32:sakatsume-preston | LS017 | 1 | 2026-09-22T02:54:21.597Z |
| seoul:r32:ruse-lys | LS027 | 1 | 2026-09-22T02:31:04.970Z |
| seoul:r32:montgomery-park | LS021 | 1 | 2026-09-22T03:14:43.223Z |
| seoul:r32:zarazua-bondar | LS024 | 1 | 2026-09-22T04:18:49.800Z |
| seoul:r32:ma-jones | LS030 | 1 | 2026-09-22T05:14:03.960Z |
| seoul:r32:ku-ibragimova | LS026 | 1 | 2026-09-22T05:23:29.823Z |
| seoul:r32:birrell-zidansek | LS031 | 1 | 2026-09-22T06:33:19.510Z |
| seoul:r32:zakharova-ostapenko | LS016 | 1 | 2026-09-22T07:09:06.573Z |
| seoul:r32:kenin-charaeva | LS025 | 1 | 2026-09-22T09:06:46.423Z |
| singapore:r32:oliynykova-wolff | LS022 | 1 | 2026-09-22T02:48:01.607Z |
| singapore:r32:parks-yamaguchi | LS018 | 1 | 2026-09-22T04:54:01.940Z |
| singapore:r16:sasnovich-andreeva | LS008 | 2 | 2026-09-23T10:20:39.233Z |
| singapore:r16:anisimova-gibson | **NONE** | — | — |

Contrary finding: Singapore source contains Talia Gibson against Fiona Ferro (LS030), Viktoria Morvayova (LS015), Maria Sakkari (LS007) and Leylah Fernandez (LS001), **not Amanda Anisimova**. Reject this prediction for automatic matching. Do not infer replacement, winner, or eligibility.

Reproduce in read-only local checkout of PR #428:
```python
import json
base="web-shadow/result-evidence/wta-results-20261109t083951z/sources/"
targets={"seoul":["sakatsume-preston","ruse-lys","montgomery-park","zarazua-bondar","ma-jones","ku-ibragimova","birrell-zidansek","zakharova-ostapenko","kenin-charaeva"],"singapore":["oliynykova-wolff","parks-yamaguchi","sasnovich-andreeva","anisimova-gibson"]}
counts=[]
for slug,pairs in targets.items():
    rows=json.load(open(base+slug+"-matches.json"))["matches"]
    singles=[r for r in rows if r["DrawMatchType"]=="S" and r["DrawLevelType"]!="Q"]
    for pair in pairs:
        surnames=set(pair.split("-"))
        hits=[r for r in singles if {r["PlayerNameLastA"].lower(),r["PlayerNameLastB"].lower()}==surnames]
        counts.append(len(hits))
assert len(counts)==13 and counts.count(1)==12 and counts.count(0)==1 and max(counts)==1
print({"unique_pair_matches":12,"unmatched":1})
```
This script is diagnostic, not production matching logic. Last-name collisions, changed participants, ambiguous round mappings, and timing remain explicit risks.

## Research comparison
- [Unified Benchmark (2026)](https://www.mdpi.com/2813-2203/5/3/22): shared temporal train/validation/test ATP comparison across Elo, classical and neural methods. Contrary result: complexity produced small gains over Elo. Data/license and WTA transfer not independently established; no external code used.
- [Bunker et al. (first online 2023)](https://doi.org/10.1177/17543371231212235): expanding annual ATP test windows; illustrates strict chronological evaluation. Includes disallowed market-derived features in some experiments; **do not import those inputs**.
- [Rui et al. (2024)](https://proceedings.mlr.press/v245/rui24b.html): point-level Wimbledon study with in-match variables. Not valid pre-match input; avoid leakage. Code license not verified.

## Evidence and queue
Non-production WTA Web Shadow main: 85 scored, 46 correct, 54.12%, Brier 0.251461, log loss 0.696908. Previously verified qualified forward N=0; not independently refreshed in this run. PR #428 still open and blocks new result acquisition; PR #430 unmerged. No champion change, no new settlement, no predictive improvement. CI for this documentation commit not yet verified.

Next: (1) inspect immutable prediction files and compare full names, event, round, pre-start lock timestamps for all 12; fail closed on ambiguity; (2) determine why Anisimova–Gibson was proposed but absent in retained official draw; (3) human-review existing result PR and unblock acquisition without bypassing gate; (4) add regression tests for legacy ID translation only after full identity validation; (5) obtain qualified forward N before paired calibration model assessment.
