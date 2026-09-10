# Tennis Genome Discovery Ledger

Status: **ACTIVE GOVERNANCE RECORD**

## Purpose

Track the full research program, including failed, redundant, conditional, and promoted ideas, so the project cannot judge evidence only from surviving factors.

This file is not a claim that early experiments were globally multiplicity-controlled. Historical entries below are reconstructed from committed protocols/findings. From this point forward, every new factor or market hypothesis must be entered here before its first outcome-bearing result is inspected.

## Rules

Each entry must record:

- experiment / hypothesis ID;
- first preregistration commit where applicable;
- signal family;
- tours tested;
- confirmatory vs exploratory status;
- primary metrics;
- result classification;
- whether a forward/independent confirmation exists;
- whether the result has been used to tune another experiment;
- multiplicity family, if any;
- current allowed use.

A failed or rejected experiment is never deleted from the ledger.

A later reformulation receives a new ID rather than overwriting the original failure.

Program-wide counts of tested/promoted/rejected ideas must be reported periodically. Individual p-values are not interpreted as if each experiment were the only hypothesis ever tested.

## Historical program inventory

| Experiment / family | Tours | Role | Outcome / current status |
| --- | --- | --- | --- |
| EXP-001 ranking vs overall Elo | ATP/WTA | baseline | Overall Elo promoted over ranking |
| EXP-002 pure surface Elo | ATP/WTA | factor test | Rejected as general replacement; ATP clay diagnostic only |
| EXP-003 opponent-adjusted serve/return | ATP/WTA | factor test | ATP A/Core; WTA B/conditional |
| Foundational Family Lab — recent form | ATP/WTA | factor test | A/Core both tours |
| Foundational Family Lab — workload/rest | ATP/WTA | factor test | A/Core both tours |
| Foundational Family Lab — age/career/physical | ATP/WTA | factor test | ATP A/Core; WTA demoted after modern-regime failure |
| Foundational Family Lab — age×fatigue | ATP/WTA | factor test | Conditional/redundant |
| Foundational Family Lab — H2H | ATP/WTA | factor test | Weak/conditional; outside strict core |
| Foundational Family Lab — handedness | ATP/WTA | factor test | Rejected |
| Foundational Family Lab — surface/tournament context | ATP/WTA | factor test | A/Core both tours |
| CORE-V1-SEALED-HOLDOUT-001 | ATP/WTA | forward confirmation | Strict Core v1 improved Brier/log loss on partial-2026 sealed holdout; holdout now spent |
| CAL-SEL-001 | ATP/WTA | calibration/selective prediction | Historical calibration/selective-prediction research; must not reuse 2026 for tuning |
| Profile Gap experiment | ATP/WTA | independent signal discovery | Survived historical tests; market incrementality not yet established |
| Genome neighborhood experiment | ATP/WTA | historical similarity | Historical residual signal tested; market incrementality not yet established |
| Genome adversarial controls | ATP/WTA | falsification | Adversarial controls retained as governing evidence |
| POINTSIM-001 | ATP/WTA | mechanistic probability module | Historically interesting; market incrementality not established |
| POINTSIM adversarial | ATP/WTA | falsification | Adversarial result constrains use; no market claim |
| Fusion calibration | ATP/WTA | probability combination | Historical-only unless separately forward confirmed |
| Uncertainty / OOD | ATP/WTA | abstention/confidence | Historical diagnostics; no market edge claim |
| MARKET-HIST-001 | ATP/WTA | market data gate | Preregistered; blocked until licensed Betfair historical files are supplied |
| MARKET-EDGE-001 | ATP/WTA | market incrementality | Preregistered; blocked on MARKET-HIST-001 |

## Multiplicity policy going forward

### Confirmatory families

Before results, each experiment must declare the finite family of confirmatory claims and the adjustment rule.

Default choices:

- Holm family-wise correction for small, named confirmatory families;
- Benjamini-Hochberg FDR for larger exploratory screening families when discovery rather than confirmation is the purpose;
- no promotion from unadjusted subgroup fishing.

### Hierarchy

Primary claims are tested first. Secondary signals, checkpoints, surfaces, tiers, and probability bins remain exploratory unless their own confirmatory protocol is registered before inspection.

### Replication

A statistically attractive historical result does not become production evidence solely because it survives multiplicity correction. Important signals should also survive chronological stability checks and a genuinely later confirmation when practical.

## Current market-era confirmatory family

MARKET-EDGE-001 defines the first explicit market-era multiplicity family:

1. ATP Profile Gap incremental value vs closing market;
2. WTA Profile Gap incremental value vs closing market;
3. ATP Genome incremental value vs closing market;
4. WTA Genome incremental value vs closing market.

Holm correction is preregistered for that family. Checkpoint/tier/probability-bin analyses are exploratory unless separately frozen before results.
