# Tennis Genome historical-neighborhood status

Current milestone: **GENOME-NN-001 completed as historical development research**.

## Supported candidate

Transparent strictly historical neighborhood residual signal (H-011) receives provisional support on ATP and WTA under the frozen 2000–2025 protocol.

The primary implementation uses:
- canonical Elo-favorite orientation;
- strict Core v1 matchup/context features;
- absolute means from strict Player Profile v1 fields;
- historical-fold-only median imputation and standardization;
- Euclidean distance;
- unweighted k=100 neighbor Core residual mean;
- nested chronological meta-control/challenger comparison.

This signal remains a B / conditional development candidate until genuinely forward-confirmed.

## Rejected uncertainty coordinate

Raw mean k=100 neighborhood distance (`D100`) failed H-012 on both tours and must not be used as an OOD, uncertainty, or abstention score.

Any future density work must be registered as a new experiment rather than modifying GENOME-NN-001 after the result.

## Accepted provenance

- workflow run: `34429137547`
- accepted code head: `04701329baf0c314bf3542f58c9068b7d01c94be`
- artifact digest: `sha256:082e9aff6f679054681b1dbda3d1160c9c6597e9246b9cff5854d211778bd9fa`
- historical source: research-only CC BY-NC-SA 4.0

See `research/installment_01/genome_neighborhood_protocol.md` and `genome_neighborhood_findings.md` for the complete protocol and result.
