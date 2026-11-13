# WTA retained-source coverage reconciliation — 2026-11-13

## Scope, provenance, and hypothesis
Baseline main SHA: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`. Read PR #486 and its exact-head ledger `72b2c79f89b285fd85cbc45aebe5102b4b653b7a`, PR #478, open PR inventory, and GitHub Actions job #131785529846 (run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43395571661). The earlier SHA-verified artifact is https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43395571661/artifacts/14022921157. The current iteration did **not** redownload that ZIP; raw counts below were independently transcribed from the previously committed exact-head artifact audit and reconciled locally. This is a consistency check, not new row-level adjudication.

Prespecified H1: 10 per-event raw-row counts sum to 745. Failure if unequal, missing event, or nonpositive count. H2: 13 legacy unresolved plus two exact-ID conflicts account for all 15 pending; 12 plausible legacy source-row candidates plus one absent pair account for 13 legacy cases. Failure if either sum differs. Baseline: acquisition's zero qualified selections; no candidate should be promoted from aggregate arithmetic.

## Executed test (Python 3, standard library)
```python
counts={'osaka':64,'beijing':162,'guangzhou':64,'seoul':58,'tokyo':60,'hong-kong':61,'wuhan':106,'chennai':58,'singapore':53,'ningbo':59}
assert len(counts)==10
assert sum(counts.values())==745
assert all(v>0 for v in counts.values())
assert 13+2==15
assert 12+1==13
print('PASS: 10 tournaments, 745 retained raw rows, 13 legacy unresolved (12 candidate, 1 absent), 2 identity conflicts; zero newly qualified')
print('per-tournament:',counts)
```
Actual local output: `PASS: 10 tournaments, 745 retained raw rows, 13 legacy unresolved (12 candidate, 1 absent), 2 identity conflicts; zero newly qualified`. The printed dictionary exactly matches the input. Five assertions passed. No repository pytest or Ruff run, no workflow dispatched.

## Operational interpretation and negative evidence
Latest **inspected** acquisition run #43395571661 succeeded with source fetch, compiler and artifact upload, but zero selected results; this does not establish that it is the most recent run. The two exact-MatchID wrong-player controls remain `web:wta:1074:2026:LS031` and `web:wta:1074:2026:LS020`. Numeric source round 1 is not the source final; textual F is. Do not weaken identity, event, round, timing, provenance or pre-start checks, and do not retroactively settle any of the 15.

Non-production WTA Web Shadow last verified: 104 predictions, 89 settled, 86 scored, 47 correct, Brier 0.2513224181, log loss 0.6966212009, 15 pending. Fixed 0.5 benchmark is better on both proper scores. This run did not independently refresh production champion digest, production forward qualified N, or individual source-to-prediction crosswalk; no performance gain is claimed.

## External methodological research (not a tennis benchmark)
Pavani et al., *Entity Resolution in Practice: Lessons from a Self-Serve Pipeline* (2026-07-28), https://arxiv.org/abs/2607.26298 : six benchmark datasets, separate precision hard vetoes from recall-oriented candidate generation. Relevance: retain strict wrong-player veto while expanding read-only candidate diagnostics; cannot transfer benchmark numbers to tennis. License of executable implementation unverified; no code imported.
Astappiev et al., *SMBench* (2026-07), https://doi.org/10.1016/j.is.2026.102711 : compares 3 filters and 7 verification methods on 9 datasets, CC BY 4.0 article, public code repository but implementation license not checked. Contradiction to one-matcher assumptions: compare matching components independently, not just aggregate acceptance rates. No outcome leakage or external code used.

## Prioritized next executable experiments
1. Download and parse the artifact again and read all 15 locked prediction JSONs; generate exact immutable-ID crosswalk including event, draw, source RoundID, player IDs, source timestamps, and pre-start feature provenance. Include both wrong-player controls and duplicated-row synthetic controls. Read-only; human adjudication only.
2. Inspect latest acquisition workflow run and scheduling gaps; distinguish a stale pipeline from a healthy pipeline with zero eligible source matches.
3. Independently verify champion SHA/checksum and qualified forward N from immutable production manifests.
4. Only with newly locked qualified observations: preregister chronological paired Elo/champion versus shrinkage challenger, proper scores, calibration, selective coverage, uncertainty and final untouched holdout.

No model code, settlements, workflow or champion changed. Documentation-only research branch; do not merge without review.
