# PATTERN-CONFIRM-001 setup record

Status: **PROSPECTIVE CONFIRMATION ARMED; ACCUMULATING; N=0 AT SETUP**

This record documents the fixed starting boundary for the future confirmation experiment. It is not a result.

## Fresh-sample audit

The repository's earlier partial-2026 holdout was already opened by prior milestones. It is therefore spent and is not reused as independent evidence here.

Prospective eligibility begins at:

`2026-09-12T00:00:00-04:00`

Matches before that timestamp cannot contribute to PATTERN-CONFIRM-001 confirmation decisions.

## Frozen family

Two ATP-only hypotheses are load-bearing:

1. `PC-ATP-PG-LOW`: `profile_gap < -0.4045998117259577`, fixed probability correction `-0.031143878674067826`, looks `524 / 1047 / 1570 / 2094`.
2. `PC-ATP-PG-ABS-HIGH`: `abs(profile_gap) >= 0.47108555150900466`, fixed correction `-0.022734415112664306`, looks `936 / 1872 / 2808 / 3744`.

The statistical design and interpretation rules are frozen in `pattern_confirm_001_protocol.md`.

## Historical Market + Core baseline seal

One final calibration object was permitted to use already-open historical outcomes. It was created before prospective accumulation from the completed bookmaker-confirmatory result bundle only.

- Freeze workflow run: `34639269141`
- Freeze workflow head SHA: `0dcbfe6c30b020821efbc80d51d1529f6947fbdf`
- Workflow artifact ID: `10279302031`
- Workflow artifact name: `pattern-confirm-001-baseline-0dcbfe6c30b020821efbc80d51d1529f6947fbdf`
- Workflow artifact ZIP SHA-256: `1580d100f534ab3d67c8b063bb9212ce80cd82ab971cc0619edf3591664a9bf3`
- Parent `market_validation_results.json` SHA-256: `6419f5fbfa24ed6399771ce9a8ed23a46aa8720406acf987498eb24ed139e88d`
- Parent Stage-B bundle SHA-256: `be097af8ff9052a1484bdc25fab861d75ada78e21252c7bdb9cfde42ab093a54`

Frozen fit:

- fit artifact SHA-256: `622d07e4a5d010b927ddf1c37900868a61d2e81d67c287f2a41dddaf4932b732`
- training-row canonical SHA-256: `65ede42d1de317214cf1a28699f9fda041d9e37df05b5adabc5a885349873383`
- training N: `22604`
- training years: `2016–2025`
- intercept: `-0.04137035601134385`
- market-logit slope: `1.0395770157643376`
- Strict-Core-logit slope: `0.007772537033422927`

The fit is the future baseline transformation:

`logit(p_market_core) = -0.04137035601134385 + 1.0395770157643376*logit(p_market) + 0.007772537033422927*logit(p_core)`

This fitted object may not be regenerated with newer outcomes or replaced during PATTERN-CONFIRM-001.

## Prospective firewall

The checked-in confirmation engine requires pre-match records with no result/winner/score fields, observation timestamps strictly before scheduled start, scheduled start on or after the cutoff, deterministic hypothesis membership, one sealed baseline-fit hash, unique canonical match IDs, and per-row digests.

Settlement is physically separate. Walkovers and retirements are counted and excluded explicitly rather than silently removed.

## Sequential design sanity check

The four O'Brien-Fleming boundaries are `4.0486417304805205`, `2.862822022035254`, `2.337484394530551`, `2.0243208652402602` at information fractions `0.25/0.50/0.75/1.00`. Under the frozen canonical joint-normal information model, the one-sided crossing probability under the null is approximately `0.025` per hypothesis. The maximum-N plans provide approximately 90% planning power at their frozen historical effects and conservative historical residual SDs.

## Starting state

At this setup record there are **zero eligible prospective matches scored** and **zero prospective outcomes inspected**. Both hypotheses are therefore `ACCUMULATING` with no completed efficacy look.
