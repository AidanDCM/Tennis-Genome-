# PATTERN-CONFIRM-001 Baseline Transfer Findings

Status: **COMPATIBLE — NO CORRECTION RE-ESTIMATION**

This audit used only the already-spent 2023-2025 internal-validation block from `PATTERN-DISCOVERY-001`. No post-cutoff prospective outcome was opened or used.

Immutable execution:

- workflow run: `34648241145`
- workflow head SHA: `999c40c5a867efe2535337da6b4202df470f3107`
- Actions artifact ID: `10283041272`
- Actions artifact ZIP SHA-256: `b9f1315ddc6c4c0bb500daee2fb31a4e6476a1734fce4238d3d3ad77a1a5ce98`
- audit artifact self SHA-256: `0a1e7c86c4ed5b2bb7fdc611baf0118dc7ae3ec1f4727b97dfe64d504329c279`
- frozen prospective Market+Core fit SHA-256: `622d07e4a5d010b927ddf1c37900868a61d2e81d67c287f2a41dddaf4932b732`

## PC-ATP-PG-LOW

- validation N: `1,248`
- original walk-forward Market+Core residual: `-0.032693723911114525`
- pooled prospective-baseline residual: `-0.031888418972228896`
- change: `+0.0008053049388856287` (about `+0.081` percentage points)
- original bootstrap interval: `[-0.05681102102883317, -0.008650407417183465]`
- pooled residual remains inside the original interval: **yes**
- direction preserved: **yes**
- frozen correction Brier improvement under pooled baseline: `0.0010163703683405967`
- frozen correction log-loss improvement under pooled baseline: `0.002469770404102012`
- transfer-compatible: **yes**

## PC-ATP-PG-ABS-HIGH

- validation N: `1,325`
- original walk-forward Market+Core residual: `-0.02322507294705072`
- pooled prospective-baseline residual: `-0.02246327692821227`
- change: `+0.0007617960188384468` (about `+0.076` percentage points)
- original bootstrap interval: `[-0.04493696598158437, -0.0009699301362726131]`
- pooled residual remains inside the original interval: **yes**
- direction preserved: **yes**
- frozen correction Brier improvement under pooled baseline: `0.0005045682223999981`
- frozen correction log-loss improvement under pooled baseline: `0.002155809126772934`
- transfer-compatible: **yes**

## Decision

The pooled production baseline changes the validation residuals by less than one tenth of one percentage point for both selected regimes. Both effects remain in the original discovery direction, remain inside the previously reported validation uncertainty intervals, and the already-frozen corrections still improve both proper scores.

Therefore the discovery-era corrections transfer to the prospective pooled Market+Core definition without re-estimation. The thresholds and corrections in `PATTERN-CONFIRM-001` remain unchanged.
