# Retained WTA source integrity and identity audit — 2026-11-13

## Scope and immutable evidence
- Repository: AidanDCM/Tennis-Genome-, main baseline previously established as `40bb697ec786527b7ed1a4c67d6d0a92aea17782`; latest main was read via connected GitHub scorecard and workflow files in this run, but the branch's current base SHA was not independently returned by branch creation.
- Scheduled acquisition: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43395571661 (08:44 UTC, 2026-11-13).
- **Downloaded and opened raw retained source ZIP**: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43395571661/artifacts/14022921157 ; 24 entries, 10 tournament match JSONs, 10 tournament metadata JSONs, 2 index pages, manifest, compiler summary.
- Acquisition manifest `observed_at=2026-11-13T08:44:26+00:00`; production_eligible=false. Source policy explicitly states provider bytes unmodified and tournament index discovery-only.
- GitHub main scorecard `web-shadow/scorecard.json`, previous blob `c9636ac9d86c256ccf241e652b9456034c451fc3`; no prediction or settlement modified.

## Prespecified falsifiable checks and negative controls
H1: Retained source payloads agree with acquisition manifest SHA256 for **all** 10 match files, 10 tournament files and 2 index files. Failure: any mismatch. **Observed 22/22 passed**.
H2: The two exact MatchID conflicts are genuinely one-to-one source IDs with different player identities, not duplicate source IDs. Failure: zero or >1 source rows for either ID, or same predicted/source player pair. **Observed each ID has exactly one source row with different player identity; both remain disqualified**.
H3: The source uses the old assumed numeric mapping of RoundID=1 as Final in main-draw singles. Failure: main-draw singles contain textual `F` Final and numeric `1` as opening round. **Rejected**: in all ten retained tournament match files, main-draw singles contain numeric RoundID=1 and textual F; observed F appears once per event, while 1 appears 12–32 times per event. This is evidence of round convention mismatch, NOT permission to change matching or settle any legacy prediction.

## Actual executed experiment
Executed Python 3 standard-library `zipfile`, `json`, `hashlib`, `collections.Counter` against downloaded ZIP. Exact reproducible core:
```python
import zipfile, json, hashlib
z=zipfile.ZipFile("github-actions-artifact-14022921157.zip")
root="wta-result-source-43395571661/"
m=json.loads(z.read(root+"acquisition-manifest.json"))
summary=json.loads(z.read("wta-result-summary-43395571661.json"))
checks=[]
for r in m["source_records"]:
    for typ in ("matches","tournament"):
        checks.append(hashlib.sha256(z.read(root+r[typ+"_filename"])).hexdigest()==r[typ+"_sha256"])
for r in m["index_records"]:
    checks.append(hashlib.sha256(z.read(root+r["filename"])).hexdigest()==r["sha256"])
assert len(checks)==22 and all(checks)
assert summary["identity_conflict_count"]==2
assert summary["result_count"]==0
for c in summary["identity_conflicts"]:
    event=c["match_id"].split(":")[2]
    src=next(r for r in m["source_records"] if str(r["group_id"])==event)
    rows=json.loads(z.read(root+src["matches_filename"]))["matches"]
    hits=[x for x in rows if x.get("MatchID")==c["match_id"].split(":")[-1]]
    assert len(hits)==1
```
Actual manifest raw-match counts: osaka 64, beijing 162, guangzhou 64, seoul 58, tokyo 60, hong-kong 61, wuhan 106, chennai 58, singapore 53, ningbo 59. Source file SHA256 checks passed 22/22. Main-draw singles RoundID='F' observed once in every event; RoundID='1' observed 12–32 times per event. No adjudicated source-to-prediction joins were performed.

## Exact conflicting sample IDs (negative controls)
- `web:wta:1074:2026:LS031`: predicted Alycia Parks vs Alexandra Eala; source LS031 Emerson Jones vs Alexandra Eala, RoundID=1.
- `web:wta:1074:2026:LS020`: predicted Sofia Kenin vs Leylah Fernandez; source LS020 Mika Stojsavljevic vs Sofia Kenin, RoundID=1.
These are direct mismatches; **do not** relabel or settle. Source SHA `d5d1346845429fc1b591f3ca5e51cb4946ce20cd84a06934a94bfac569024f7d`.

## Forecasting status and research
- NON-PRODUCTION WTA Web Shadow, last main scorecard: 104 predictions, 89 settled, 86 completed/scored, 47 correct (54.65%), Brier 0.2513224181, log loss 0.6966212009, 15 pending. Fixed 0.5 baseline better on both proper scores. Not a production-forward performance claim.
- Latest immutable production champion checksum and qualified production-forward N **not verified** this run.
- Poudel et al. (2026), *A Unified Benchmark of Machine Learning and Deep Neural Networks for Tennis Match Prediction*, https://doi.org/10.3390/analytics5030022 ; published 2026-07-03, temporally split 133,138 ATP matches, same-feature model comparison; supports simple Elo as a strong benchmark. ATP population does not transfer directly to WTA, and implementation license not checked.
- Clegg & Cartlidge (2025), *Tennis match outcome prediction using temporal directed graph neural networks*, https://research-information.bris.ac.uk/en/publications/tennis-match-outcome-prediction-using-temporal-directed-graph-neu/ ; out-of-sample ATP comparisons yield modest gains over weighted Elo, providing contrary evidence to automatic complexity gains; code license not checked. No external code imported.
- Neither paper's reported accuracy is comparable to this WTA shadow population. No odds, markets, or gambling features used.

## Highest-value next executable queue
1. For all 15 pending immutable prediction IDs, fetch the locked prediction JSONs and independently crosswalk player IDs, event, main/qualifying draw, round, source timestamps and pre-start feature provenance against this SHA-verified ZIP. Include wrong-player and duplicate-row negative controls; do not backfill or settle.
2. Investigate historical compiler round convention as a diagnostic-only, reviewable test, preserving all trust and identity gates.
3. Independently refresh frozen production champion checksum, forward qualified N and immutable forward settlements from main; do not infer from shadow.
4. Extract chronological locked match-level paired probabilities and outcomes for a prespecified simple Elo/calibration comparison; preserve final holdout, report Brier, log loss, calibration, coverage and uncertainty.

No code change, CI execution, settlement, promotion or merge in this run; artifact verification and diagnostic Python assertions were actually executed.
