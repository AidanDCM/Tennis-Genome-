# WTA source artifact integrity and identity audit — 2026-11-12

## Preregistered question
Does the first post-fix acquisition artifact preserve all declared raw source bytes and provide unambiguous identity support for the two Hong Kong pending predictions? Baseline: compiler summary reports 15 pending, 13 unresolved, two identity conflicts and zero results. Pass integrity only if every declared SHA-256 and match count matches. Pass identity only if the official match-ID player pair matches both predicted players exactly. No retrospective relabeling or settlement.

## Pinned evidence
- Main commit: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`
- GitHub Actions run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43270738286
- Artifact ID: `13967128659`, ZIP SHA-256: `87c1a606aec15261b3a9295e767ff2e0add4db28a6ccc162d79ab9ad278ea2ce` (matches GitHub metadata).
- Source observed at `2026-11-12T17:33:49+00:00`; ten tournament match payloads and two tournament-index pages.
- Match source for both conflicts: https://api.wtatennis.com/tennis/tournaments/1074/2026/matches ; retained `hong-kong-matches.json` SHA-256 `13618b1f1ccb55a4e6c4b832134e19e20c6353eb999ac025807c4d53031241a3`.

## Executed checks and output
Downloaded artifact through connected GitHub Actions; Python `hashlib.sha256`, `zipfile.ZipFile` and `json` checked **22/22 declared file hashes** (ten match files, ten tournament files, two index files) and all ten manifest raw-match counts; **745 source match rows** across those tournaments. ZIP digest matched metadata.

Queried exact Hong Kong `MatchID` in the retained provider rows:
- `web:wta:1074:2026:LS031`: **one** provider row, Emerson Jones vs Alexandra Eala, final result Eala defeated Jones 6-4, 6-3. Locked prediction names Alycia Parks vs Alexandra Eala. Identity **FAIL**.
- `web:wta:1074:2026:LS020`: **one** provider row, Mika Stojsavljevic vs Sofia Kenin, final result Stojsavljevic defeated Kenin 6-3, 4-6, 6-4. Locked prediction names Sofia Kenin vs Leylah Fernandez. Identity **FAIL**.

Source match-ID uniqueness and source byte integrity do **not** prove locked prediction identity. Both conflicts must remain excluded. No eligible result or prediction was created. No attempt to reassign IDs to another source row.

Reproduction from downloaded ZIP:
```python
import hashlib, json, zipfile
z=zipfile.ZipFile("github-actions-artifact-13967128659.zip")
root="wta-result-source-43270738286/"
m=json.loads(z.read(root+"acquisition-manifest.json"))
checks=[]
for r in m["source_records"]:
    for t in ("matches","tournament"):
        checks.append(hashlib.sha256(z.read(root+r[t+"_filename"])).hexdigest()==r[t+"_sha256"])
    assert len(json.loads(z.read(root+r["matches_filename"]))["matches"])==r["raw_match_count"]
for r in m["index_records"]:
    checks.append(hashlib.sha256(z.read(root+r["filename"])).hexdigest()==r["sha256"])
assert len(checks)==22 and all(checks)
h=json.loads(z.read(root+"hong-kong-matches.json"))["matches"]
for mid in ("LS031","LS020"):
    rows=[r for r in h if r["MatchID"]==mid]
    assert len(rows)==1
    print(mid,[(r["PlayerNameFirstA"],r["PlayerNameLastA"],r["PlayerNameFirstB"],r["PlayerNameLastB"]) for r in rows])
```

## Research and contrary evidence
Papadakis et al. (2024), *An analysis of one-to-one matching algorithms for entity resolution*, https://openreview.net/forum?id=pHzBrl8jpa, compares eight bipartite algorithms across ten datasets; a candidate for **review-only** conflict detection, not autonomous remapping. TransClean (de Meer Pardo et al., 2025), https://arxiv.org/abs/2506.04006, proposes transitive-consistency checks against false-positive entity links. Neither is tested on tennis, neither supplies a safe retroactive settlement license, and implementation licenses were not checked. No third-party code imported.

## Evidence tier, negatives, and next executable queue
This is a **non-production acquisition-integrity audit**, not a model experiment or a new qualified prospective sample. Negative: both identity conflicts persist despite intact raw bytes. Historical WTA shadow: 47/86 correct, Brier 0.251322, log loss 0.696621, pending 15, production-ineligible; not independently recalculated in this artifact audit. Frozen champion and qualified production-forward N were not independently established.

1. Inspect all 13 unresolved predictions against source rows, report precise failure taxonomy without weakening gates.
2. Add a read-only, no-write diagnostic to emit safe candidate-match evidence and exact source IDs for manual identity review; test on known conflicts and genuine matches.
3. Exercise fail/skip/blocked/empty acquisition gate states in an isolated workflow with no settlement writes.
4. After new qualified pre-start locks, run paired chronological champion/Elo/fixed-0.5 Brier and log loss, confidence intervals, calibration, coverage, drift, untouched final holdout and multiplicity control.

No production edits, model promotion, new settlements or gate changes.
