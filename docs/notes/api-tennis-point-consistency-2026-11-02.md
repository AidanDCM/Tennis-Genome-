# API-Tennis point-count admission repair, 2026-11-02

The retained source has exact numerical fields that do not always describe one
consistent point history. Availability of exact counts does not establish that
those counts can be combined into canonical player state. This repair strengthens
input admission; it changes no frozen model coefficients or registered experiment.

## Reproduced defect

API-Tennis event `12128054` (Paul–Quinn, Hamburg, May 17) reports Paul's
first/second service wins as 26 + 8 = 34, but its aggregate service wins as 22.
Its split denominators sum to 35 + 16 = 51, while aggregate service points are 38.
The previous bridge accepted this record and constructed a 34/38 canonical
service observation. This was a combination of incompatible provider fields.
The repair rejects such records rather than choosing or reconstructing a total.

Checks cover service/return split sums, aggregate wins, opponent conservation,
point ranges, total-point identities, player identity, and duplicate statistics.
Normal raw parsing preserves source evidence; model-state batch admission now
records `INCONSISTENT_POINT_COUNTS`. Direct bridge calls independently reject it.
Field-definition differences may explain some conflicts; independent source
evidence is needed before any alternative mapping is admitted.

## Retained history audit

Ten captures cover May 3–November 1 with no gap between requested date windows.
This does not establish complete tournament or match coverage. The missing
October 31 window was captured using the existing two-request workflow:
[run 41500029252](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41500029252),
artifact `13166829500`, digest
`6a9bbd97aff5dd8a6387a204f12b8ecbe56e50427073f5fab15d2b27655a90d2`.
All other inputs were already retained. Raw files, audit files and receipt
bindings were checked locally. This check is not live authentication of the
provider or an independent timestamp of a prediction.

| Tour | Fixtures | Finished | Parseable | Point-consistent | Point-conflicting | Missing/invalid enrichment |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ATP | 2,508 | 2,322 | 2,228 | 1,791 | 437 | 94 |
| WTA | 2,434 | 2,280 | 2,221 | 1,666 | 555 | 59 |

These are engineering checks on the retained captures, not a representative
provider error rate. Point consistency alone does not approve the remaining
3,457 rows for the frozen production state. Source agreement, canonical identity,
surface and player context, duration availability, and chronological state
construction remain separate gates. Rows with unusable statistics may still
have independently usable result evidence; they must not silently disappear
from a future rating/history completeness audit.

## Probability sensitivity

A fixed set of 4,449 parseable retrospective targets was evaluated under two
history scenarios: the previous bridge's admissible observations, and those
same observations after quarantining point conflicts. Each tour was processed
separately using the existing frozen serve/return component, with same-day
updates blocked, followed by standardized best-of-three PointSim. Target
outcomes were not used or scored. A quarantined row remained a target; its
statistics could not update later checked history.

| Tour | Targets | Mean absolute probability change | Largest change |
| --- | ---: | ---: | ---: |
| ATP | 2,228 | 2.884 percentage points | 21.556 percentage points |
| WTA | 2,221 | 3.663 percentage points | 24.402 percentage points |

This is component sensitivity from a cold-start research replay, not a full-stack
probability comparison, proof that quarantine improves prediction, or an amendment
to an existing forecast. It demonstrates that the input defect can propagate into
later state and component probabilities. Full-stack source substitution requires
a qualified canonical crosswalk and identical target/context inputs.

## Reproduction

Run `scripts/audit_api_tennis_retained_history.py` under the project environment:

```text
python scripts/audit_api_tennis_retained_history.py \
  --capture-dir <retained-capture-directory> \
  --capture-dir <next-retained-capture-directory> \
  --component-sensitivity --output-dir <new-output-directory>
```

Each directory contains the raw ATP/WTA fixture files, `audit.json`,
`manifest.json`, and a trial `github-receipt.json`, or the supported earlier
filtered-range receipt in its parent directory. Tampered evidence, duplicate
event IDs, inconsistent date windows and unexpected tour responses fail closed.
The output retains every quarantine reason, input hash, implementation file hash,
and runtime version. The command makes zero provider requests and refuses to
replace an existing output directory.

The local completed audit is `outputs/api-tennis-history-quality-complete-2026-11-02/audit.json`
in the operating checkout; its SHA-256 is
`604615b6e89fe502aecaf6c02645d84437f7265eb9fe8b50bd5f70dea1abfeda`.
Provider responses remain outside the public repository. Existing immutable
Web Shadow forecasts and formal prospective counts are unchanged.
