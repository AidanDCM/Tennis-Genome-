# Bookmaker Market Confirmatory Findings

Status: **CONFIRMATORY RUN COMPLETE — RECORDED WITHOUT POST-RESULT RETUNING**

## Immutable execution

The sealed bookmaker confirmation was executed once on branch commit:

- confirmatory code SHA: `6d62014eeb1549c0bda09cb5987695ac7c2be2a1`
- workflow run: `34623630174`
- Stage-A seal SHA-256: `b9260e9ab398dc10bdf358e99d5ca26f61ba3ef0970eca1abc48568ed0508b84`
- outcomes SHA-256: `c509dff1bbe4b1e10944f5b361138790f85ccdb21b7d12aafb03ddc0b1e8c63d`
- POWER-MDE artifact SHA-256: `a8ec4df7313ac3127265ee0edc214851e1386fa8a479a69768d4374c7b722479`
- validation bundle SHA-256: `be097af8ff9052a1484bdc25fab861d75ada78e21252c7bdb9cfde42ab093a54`
- primary MARKET-EDGE-001 SHA-256: `d834edefc6b8b37365c2aebc8fe38dd6ab47bb97f6654c39445795fc6261ea26`
- adversarial MARKET-EDGE-ADV-001 SHA-256: `ca9a4f652e00f0cf8e48d8e49a271eff92543aaa5c0da90b54b9b86bfd0bedad`
- combined decision artifact SHA-256: `1655b461aabacedec0a9983d0fe91e48f5a4211319a3ce3ae6a5a7040f78f547`

All frozen input hashes, QA gates, signal projections, POWER-MDE claims, and the Stage-A outcome lock were verified before outcomes were opened.

## Frozen decision rule

A claim could enter the stack only if both were true:

1. `MARKET-EDGE-001`: signal adds information beyond the recalibrated bookmaker market; and
2. `MARKET-EDGE-ADV-001`: signal still adds information beyond Market + frozen Strict Core.

No claim may be promoted by passing only one arm.

## Confirmatory results

| Claim | Primary market-incremental | Market+Core incremental | Stack promotion |
|---|---:|---:|---:|
| ATP × Profile Gap | FAIL | FAIL | **FAIL** |
| WTA × Profile Gap | FAIL | FAIL | **FAIL** |
| ATP × Genome | FAIL | FAIL | **FAIL** |
| WTA × Genome | FAIL | FAIL | **FAIL** |

### ATP × Profile Gap

This was the closest claim, but it did not satisfy the frozen inference bar.

Primary MARKET-EDGE-001:

- N = `22,604`
- Brier improvement vs market control = `0.0001515942298970785`
- log-loss improvement vs market control = `0.00033482672874751707`
- Brier sign-flip p = `0.07294635268236588`
- log-loss sign-flip p = `0.09789510524473777`
- Holm-adjusted Brier p = `0.2917854107294635`
- Holm-adjusted log-loss p = `0.39158042097895107`
- bootstrap lower-bound-positive tests = FAIL
- final `market_incremental_pass = false`

Adversarial MARKET-EDGE-ADV-001:

- N = `22,604`
- Brier sign-flip p = `0.06544672766361682`
- log-loss sign-flip p = `0.087895605219739`
- Holm-adjusted Brier p = `0.2617869106544673`
- Holm-adjusted log-loss p = `0.351582420878956`
- final `market_core_incremental_pass = false`

The positive point estimates are therefore retained only as diagnostic evidence, not a confirmed edge.

### WTA × Profile Gap

Primary:

- N = `19,603`
- Brier improvement = `0.000003984200205281452`
- log-loss improvement = `0.000008000576637190449`
- Brier p = `0.8773561321933904`
- log-loss p = `0.9016049197540122`
- final `market_incremental_pass = false`

Adversarial:

- Brier p = `0.7894105294735263`
- log-loss p = `0.8199090045497726`
- final `market_core_incremental_pass = false`

### ATP × Genome

Primary:

- N = `22,604`
- Brier improvement = `0.00000341734096459545`
- log-loss improvement = `0.0000020694427784739844`
- Brier p = `0.87965601719914`
- log-loss p = `0.9697015149242538`
- final `market_incremental_pass = false`

Adversarial:

- Brier p = `0.8835058247087646`
- log-loss p = `0.9704014799260037`
- trailing-three-year robustness had a direction conflict
- final `market_core_incremental_pass = false`

### WTA × Genome

Primary:

- N = `19,603`
- Brier improvement = `-0.000010618672703244236`
- log-loss improvement = `-0.000034403389274184626`
- Brier p = `0.6286685665716714`
- log-loss p = `0.4806759662016899`
- yearly stability = FAIL
- final `market_incremental_pass = false`

Adversarial:

- Brier p = `0.6252187390630468`
- log-loss p = `0.47237638118094094`
- yearly stability = FAIL
- final `market_core_incremental_pass = false`

## Interpretation

Under the preregistered family and the frozen bookmaker latest-preplay benchmark, the project did **not** establish that Profile Gap or Genome supplies reliable broad incremental predictive information beyond the mature market. The null result is load-bearing and must not be reversed by post-result threshold changes, tour filtering, year filtering, or alternate multiplicity choices.

ATP Profile Gap remains a useful diagnostic lead because its proper-score point estimates were positive and relatively stable, but the confirmatory evidence was insufficient and it is **not promoted**.

## Next research phase

The next phase is the separately preregistered `PATTERN-DISCOVERY-001` program. It searches for repeatable residual structure beyond the frozen `Market + Strict Core` baseline using historical discovery years through 2022 and internal validation on 2023-2025. Discovery candidates are hypothesis generators only and cannot be promoted without a new untouched future confirmation boundary.
